from __future__ import annotations

from dataclasses import dataclass

from ai_pm_lab_privacy_gate.infrastructure.auth.supabase_account import (
    AccountError,
    AccountSession,
    SUPABASE_URL,
    SupabaseAccountClient,
)


@dataclass(frozen=True, slots=True)
class AccountProfile:
    user_id: str
    customer_code: str
    display_name: str


class AccountProfileClient:
    """Read and update the minimal PrivacyGate cloud profile.

    Email continues to come from Supabase Auth. This table stores only a
    human-readable display name and the existing non-secret customer code.
    Documents, connector tokens, Library contents and restore mappings are never
    part of this profile.
    """

    def __init__(self, account_client: SupabaseAccountClient) -> None:
        self.account_client = account_client

    @staticmethod
    def _rows(response) -> list[dict[str, object]]:
        try:
            payload = response.json() if response.content else []
        except ValueError as error:
            raise AccountError("The account profile service returned invalid data.") from error
        if response.status_code >= 400:
            message = ""
            if isinstance(payload, dict):
                message = str(payload.get("message") or payload.get("details") or "")
            raise AccountError(message or f"Account profile request failed ({response.status_code}).")
        if not isinstance(payload, list):
            raise AccountError("The account profile service returned an unexpected response.")
        return [dict(row) for row in payload if isinstance(row, dict)]

    def fetch(self, session: AccountSession) -> AccountProfile | None:
        response = self.account_client._http.get(
            f"{SUPABASE_URL}/rest/v1/privacy_gate_profiles",
            params={
                "select": "user_id,customer_code,display_name",
                "user_id": f"eq.{session.user_id}",
                "limit": "1",
            },
            headers={"Authorization": f"Bearer {session.access_token}"},
        )
        rows = self._rows(response)
        if not rows:
            return None
        row = rows[0]
        return AccountProfile(
            user_id=str(row.get("user_id") or session.user_id),
            customer_code=str(row.get("customer_code") or ""),
            display_name=str(row.get("display_name") or "").strip(),
        )

    def update_display_name(
        self,
        session: AccountSession,
        display_name: str,
    ) -> AccountProfile:
        name = " ".join(display_name.strip().split())
        if len(name) < 2:
            raise ValueError("Enter at least 2 characters for your display name.")
        if len(name) > 80:
            raise ValueError("Display name must be 80 characters or fewer.")
        response = self.account_client._http.patch(
            f"{SUPABASE_URL}/rest/v1/privacy_gate_profiles",
            params={"user_id": f"eq.{session.user_id}"},
            headers={
                "Authorization": f"Bearer {session.access_token}",
                "Prefer": "return=representation",
            },
            json={"display_name": name},
        )
        rows = self._rows(response)
        if not rows:
            raise AccountError("PrivacyGate profile could not be updated.")
        row = rows[0]
        return AccountProfile(
            user_id=str(row.get("user_id") or session.user_id),
            customer_code=str(row.get("customer_code") or ""),
            display_name=str(row.get("display_name") or name).strip(),
        )
