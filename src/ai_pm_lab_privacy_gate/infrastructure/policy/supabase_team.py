from __future__ import annotations

import hashlib
import platform
import ssl
from datetime import datetime, timezone
from typing import Any

import httpx
import truststore

from ai_pm_lab_privacy_gate import __version__
from ai_pm_lab_privacy_gate.domain.company_policy import CompanyPolicy
from ai_pm_lab_privacy_gate.domain.plans import PlanCode, normalize_plan
from ai_pm_lab_privacy_gate.infrastructure.auth.supabase_account import (
    SUPABASE_PUBLISHABLE_KEY,
    SUPABASE_URL,
    AccountSession,
)
from ai_pm_lab_privacy_gate.infrastructure.mcp.identity import ConnectionIdentityStore
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState


class TeamServiceError(RuntimeError):
    pass


class SupabaseTeamClient:
    """Control-plane client. It sends identity/policy metadata only, never documents."""

    def __init__(self, identity_store: ConnectionIdentityStore) -> None:
        self.identity_store = identity_store
        self._http = httpx.Client(
            timeout=20,
            verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            headers={
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "User-Agent": f"AI-PM-LAB-Privacy-Gate/{__version__}",
            },
        )

    @staticmethod
    def _auth(session: AccountSession) -> dict[str, str]:
        return {"Authorization": f"Bearer {session.access_token}"}

    def _request(
        self,
        method: str,
        path: str,
        session: AccountSession,
        *,
        params: dict[str, str] | None = None,
        json: object | None = None,
        prefer: str = "",
    ) -> Any:
        headers = self._auth(session)
        if prefer:
            headers["Prefer"] = prefer
        response = self._http.request(
            method,
            f"{SUPABASE_URL}{path}",
            params=params,
            json=json,
            headers=headers,
        )
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            message = ""
            if isinstance(payload, dict):
                message = str(
                    payload.get("message")
                    or payload.get("error_description")
                    or payload.get("hint")
                    or ""
                )
            raise TeamServiceError(
                message or f"Team service request failed ({response.status_code})."
            )
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise TeamServiceError("The Team service returned an invalid response.") from error

    def _first(
        self,
        table: str,
        session: AccountSession,
        params: dict[str, str],
    ) -> dict[str, object] | None:
        query = dict(params)
        query.setdefault("limit", "1")
        payload = self._request(
            "GET",
            f"/rest/v1/{table}",
            session,
            params=query,
        )
        if not isinstance(payload, list) or not payload:
            return None
        row = payload[0]
        return dict(row) if isinstance(row, dict) else None

    def _sync_device(
        self,
        session: AccountSession,
        organization_id: str,
        policy_version: int,
    ) -> None:
        identity = self.identity_store.load_or_create()
        installation_hash = hashlib.sha256(
            identity.installation_id.encode("ascii")
        ).hexdigest()
        self._request(
            "POST",
            "/rest/v1/rpc/privacy_gate_sync_team_device",
            session,
            json={
                "p_organization_id": organization_id,
                "p_installation_hash": installation_hash,
                "p_display_name": identity.display_name,
                "p_platform": platform.system().lower(),
                "p_app_version": __version__,
                "p_policy_version": policy_version,
            },
        )

    def _individual_state(self, session: AccountSession) -> TeamState:
        entitlement = self._first(
            "privacy_gate_entitlements",
            session,
            {
                "user_id": f"eq.{session.user_id}",
                "status": "in.(trialing,active)",
                "select": "plan_code,status,valid_until",
            },
        )
        return TeamState(
            plan=normalize_plan(
                str(entitlement.get("plan_code"))
                if entitlement
                else PlanCode.BASIC.value
            ),
            entitlement_status=(
                str(entitlement.get("status") or "active")
                if entitlement
                else "active"
            ),
            synced_at=datetime.now(timezone.utc).isoformat(),
        )

    def fetch_team_state(self, session: AccountSession) -> TeamState:
        identity = self.identity_store.load_or_create()
        installation_hash = hashlib.sha256(
            identity.installation_id.encode("ascii")
        ).hexdigest()
        device = self._first(
            "privacy_gate_devices",
            session,
            {
                "user_id": f"eq.{session.user_id}",
                "installation_hash": f"eq.{installation_hash}",
                "select": "status",
            },
        )
        if device and str(device.get("status") or "active") in {"disabled", "revoked"}:
            return self._individual_state(session)

        membership = self._first(
            "privacy_gate_memberships",
            session,
            {
                "user_id": f"eq.{session.user_id}",
                "status": "eq.active",
                "select": "organization_id,role,status",
            },
        )
        if not membership:
            return self._individual_state(session)

        organization_id = str(membership.get("organization_id") or "")
        organization = self._first(
            "privacy_gate_organizations",
            session,
            {
                "id": f"eq.{organization_id}",
                "select": "id,name,status",
            },
        )
        if not organization:
            raise TeamServiceError("The organization attached to this account is unavailable.")

        entitlement = self._first(
            "privacy_gate_org_entitlements",
            session,
            {
                "organization_id": f"eq.{organization_id}",
                "status": "in.(trialing,active)",
                "select": "plan_code,status,seat_limit,device_limit_per_member",
            },
        )
        plan = normalize_plan(
            str(entitlement.get("plan_code")) if entitlement else PlanCode.BASIC.value
        )
        if plan not in {PlanCode.BUSINESS, PlanCode.ENTERPRISE}:
            raise TeamServiceError(
                "This organization does not have an active Business or Enterprise entitlement."
            )

        policy_row = self._first(
            "privacy_gate_policies",
            session,
            {
                "organization_id": f"eq.{organization_id}",
                "status": "eq.active",
                "select": "id,name,active_version",
            },
        )
        if not policy_row:
            raise TeamServiceError("This organization does not have an active privacy policy.")
        version = int(policy_row.get("active_version") or 0)
        version_row = self._first(
            "privacy_gate_policy_versions",
            session,
            {
                "policy_id": f"eq.{policy_row.get('id')}",
                "version": f"eq.{version}",
                "select": "version,policy_json,created_at",
            },
        )
        if not version_row or not isinstance(version_row.get("policy_json"), dict):
            raise TeamServiceError("The active company policy version is unavailable.")

        policy_payload = dict(version_row["policy_json"])
        policy_payload.update(
            {
                "organization_id": organization_id,
                "organization_name": str(organization.get("name") or "Organization"),
                "version": version,
                "plan": plan.value,
                "policy_name": str(policy_row.get("name") or "Company Privacy Policy"),
                "issued_at": str(version_row.get("created_at") or ""),
            }
        )
        policy = CompanyPolicy.from_dict(policy_payload)
        self._sync_device(session, organization_id, version)

        return TeamState(
            plan=plan,
            organization_id=organization_id,
            organization_name=policy.organization_name,
            role=str(membership.get("role") or "member"),
            membership_status=str(membership.get("status") or "active"),
            seat_limit=(
                int(entitlement["seat_limit"])
                if entitlement and entitlement.get("seat_limit") is not None
                else None
            ),
            device_limit_per_member=(
                int(entitlement["device_limit_per_member"])
                if entitlement and entitlement.get("device_limit_per_member") is not None
                else None
            ),
            policy=policy,
            synced_at=datetime.now(timezone.utc).isoformat(),
            entitlement_status=str(
                entitlement.get("status") if entitlement else "active"
            ),
        )

    def create_business_workspace(
        self,
        session: AccountSession,
        name: str,
        *,
        seat_limit: int = 5,
    ) -> TeamState:
        self._request(
            "POST",
            "/rest/v1/rpc/privacy_gate_create_business_workspace",
            session,
            json={
                "p_name": name.strip(),
                "p_seat_limit": max(2, min(int(seat_limit), 100)),
            },
        )
        return self.fetch_team_state(session)

    def accept_invitation(self, session: AccountSession, code: str) -> TeamState:
        identity = self.identity_store.load_or_create()
        installation_hash = hashlib.sha256(
            identity.installation_id.encode("ascii")
        ).hexdigest()
        self._request(
            "POST",
            "/rest/v1/rpc/privacy_gate_accept_invitation",
            session,
            json={
                "p_code": code.strip(),
                "p_installation_hash": installation_hash,
                "p_display_name": identity.display_name,
                "p_platform": platform.system().lower(),
                "p_app_version": __version__,
            },
        )
        return self.fetch_team_state(session)

    def create_invitation(
        self,
        session: AccountSession,
        organization_id: str,
        *,
        role: str = "member",
        expires_hours: int = 72,
    ) -> str:
        payload = self._request(
            "POST",
            "/rest/v1/rpc/privacy_gate_create_invitation",
            session,
            json={
                "p_organization_id": organization_id,
                "p_role": role,
                "p_expires_hours": max(1, min(int(expires_hours), 720)),
            },
        )
        if isinstance(payload, str):
            return payload
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return str(first.get("code") or first.get("privacy_gate_create_invitation") or "")
        if isinstance(payload, dict):
            return str(payload.get("code") or payload.get("privacy_gate_create_invitation") or "")
        raise TeamServiceError("The invitation service did not return a code.")

    def publish_policy(
        self,
        session: AccountSession,
        policy: CompanyPolicy,
    ) -> TeamState:
        self._request(
            "POST",
            "/rest/v1/rpc/privacy_gate_publish_policy",
            session,
            json={
                "p_organization_id": policy.organization_id,
                "p_policy": {
                    "allowed_ai": dict(policy.allowed_ai),
                    "allowed_connectors": dict(policy.allowed_connectors),
                    "protection_rules": {
                        key: value.value
                        for key, value in policy.protection_rules.items()
                    },
                },
                "p_name": policy.policy_name,
            },
        )
        return self.fetch_team_state(session)

    def list_members(
        self,
        session: AccountSession,
        organization_id: str,
    ) -> list[dict[str, object]]:
        payload = self._request(
            "POST",
            "/rest/v1/rpc/privacy_gate_list_members",
            session,
            json={"p_organization_id": organization_id},
        )
        return [dict(row) for row in payload] if isinstance(payload, list) else []

    def list_devices(
        self,
        session: AccountSession,
        organization_id: str,
    ) -> list[dict[str, object]]:
        payload = self._request(
            "POST",
            "/rest/v1/rpc/privacy_gate_list_devices",
            session,
            json={"p_organization_id": organization_id},
        )
        return [dict(row) for row in payload] if isinstance(payload, list) else []
