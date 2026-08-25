from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.auth.supabase_account import AccountSession
from ai_pm_lab_privacy_gate.infrastructure.policy.supabase_team import SupabaseTeamClient


def set_member_role(
    client: SupabaseTeamClient,
    session: AccountSession,
    organization_id: str,
    user_id: str,
    role: str,
) -> None:
    client._request(
        "POST",
        "/rest/v1/rpc/privacy_gate_set_member_role",
        session,
        json={
            "p_organization_id": organization_id,
            "p_user_id": user_id,
            "p_role": role,
        },
    )


def set_member_status(
    client: SupabaseTeamClient,
    session: AccountSession,
    organization_id: str,
    user_id: str,
    status: str,
) -> None:
    client._request(
        "POST",
        "/rest/v1/rpc/privacy_gate_set_member_status",
        session,
        json={
            "p_organization_id": organization_id,
            "p_user_id": user_id,
            "p_status": status,
        },
    )


def set_device_status(
    client: SupabaseTeamClient,
    session: AccountSession,
    organization_id: str,
    installation_hash: str,
    status: str,
) -> None:
    client._request(
        "POST",
        "/rest/v1/rpc/privacy_gate_set_device_status",
        session,
        json={
            "p_organization_id": organization_id,
            "p_installation_hash": installation_hash,
            "p_status": status,
        },
    )
