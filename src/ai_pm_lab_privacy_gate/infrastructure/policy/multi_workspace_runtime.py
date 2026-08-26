from __future__ import annotations

from datetime import datetime, timezone

from ai_pm_lab_privacy_gate.domain.company_policy import CompanyPolicy
from ai_pm_lab_privacy_gate.domain.plans import PlanCode, normalize_plan
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.infrastructure.policy.supabase_team import (
    SupabaseTeamClient,
    TeamServiceError,
)
from ai_pm_lab_privacy_gate.infrastructure.policy.workspace_context import WorkspaceDescriptor

_INSTALLED = False


def _workspace_descriptors(self: SupabaseTeamClient, session):
    memberships = self._request(
        "GET",
        "/rest/v1/privacy_gate_memberships",
        session,
        params={
            "user_id": f"eq.{session.user_id}",
            "status": "eq.active",
            "select": "organization_id,role,status,joined_at",
            "order": "joined_at.asc",
        },
    )
    result: list[WorkspaceDescriptor] = []
    if not isinstance(memberships, list):
        return result

    for membership in memberships:
        if not isinstance(membership, dict):
            continue
        organization_id = str(membership.get("organization_id") or "")
        if not organization_id:
            continue
        organization = self._first(
            "privacy_gate_organizations",
            session,
            {
                "id": f"eq.{organization_id}",
                "status": "eq.active",
                "select": "id,name,status",
            },
        )
        entitlement = self._first(
            "privacy_gate_org_entitlements",
            session,
            {
                "organization_id": f"eq.{organization_id}",
                "status": "in.(trialing,active)",
                "select": "plan_code,status",
            },
        )
        if not organization or not entitlement:
            continue
        plan = normalize_plan(str(entitlement.get("plan_code") or "business"))
        if plan not in {PlanCode.BUSINESS, PlanCode.ENTERPRISE}:
            continue
        result.append(
            WorkspaceDescriptor(
                key=f"org:{organization_id}",
                name=str(organization.get("name") or "Organization"),
                plan=plan,
                role=str(membership.get("role") or "member"),
                organization_id=organization_id,
                personal=False,
            )
        )
    return result


def _workspace_state(
    self: SupabaseTeamClient,
    session,
    organization_id: str,
) -> TeamState:
    membership = self._first(
        "privacy_gate_memberships",
        session,
        {
            "user_id": f"eq.{session.user_id}",
            "organization_id": f"eq.{organization_id}",
            "status": "eq.active",
            "select": "organization_id,role,status",
        },
    )
    if not membership:
        raise TeamServiceError("This account is not an active member of that workspace.")

    organization = self._first(
        "privacy_gate_organizations",
        session,
        {
            "id": f"eq.{organization_id}",
            "status": "eq.active",
            "select": "id,name,status",
        },
    )
    if not organization:
        raise TeamServiceError("The selected organization is unavailable.")

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
            "The selected workspace does not have an active Business or Enterprise entitlement."
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
        raise TeamServiceError("The selected workspace has no active privacy policy.")

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
        raise TeamServiceError("The active workspace policy version is unavailable.")

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
        entitlement_status=str(entitlement.get("status") if entitlement else "active"),
    )


def install_multi_workspace_client() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    SupabaseTeamClient.list_workspace_descriptors = _workspace_descriptors
    SupabaseTeamClient.fetch_workspace_state = _workspace_state
