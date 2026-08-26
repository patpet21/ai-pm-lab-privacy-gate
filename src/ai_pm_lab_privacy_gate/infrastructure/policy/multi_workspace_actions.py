from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.policy.supabase_team import (
    SupabaseTeamClient,
    TeamServiceError,
)

_INSTALLED = False


def _rpc_uuid(payload: object, function_name: str) -> str:
    if isinstance(payload, str) and payload:
        return payload
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            value = first.get(function_name) or first.get("id") or first.get("organization_id")
            if value:
                return str(value)
    if isinstance(payload, dict):
        value = payload.get(function_name) or payload.get("id") or payload.get("organization_id")
        if value:
            return str(value)
    raise TeamServiceError("The organization service did not return a workspace ID.")


def _create_business_workspace(self, session, name: str, *, seat_limit: int = 5):
    payload = self._request(
        "POST",
        "/rest/v1/rpc/privacy_gate_create_business_workspace",
        session,
        json={
            "p_name": name.strip(),
            "p_seat_limit": max(2, min(int(seat_limit), 100)),
        },
    )
    organization_id = _rpc_uuid(payload, "privacy_gate_create_business_workspace")
    return self.fetch_workspace_state(session, organization_id)


def _accept_invitation(self, session, code: str):
    import hashlib
    import platform
    from ai_pm_lab_privacy_gate import __version__

    identity = self.identity_store.load_or_create()
    installation_hash = hashlib.sha256(identity.installation_id.encode("ascii")).hexdigest()
    payload = self._request(
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
    organization_id = _rpc_uuid(payload, "privacy_gate_accept_invitation")
    return self.fetch_workspace_state(session, organization_id)


def install_multi_workspace_actions() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    SupabaseTeamClient.create_business_workspace = _create_business_workspace
    SupabaseTeamClient.accept_invitation = _accept_invitation
