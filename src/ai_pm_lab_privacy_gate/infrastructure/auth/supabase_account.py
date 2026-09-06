from __future__ import annotations

import hashlib
import platform
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import truststore

from ai_pm_lab_privacy_gate import __version__
from ai_pm_lab_privacy_gate.infrastructure.mcp.identity import ConnectionIdentityStore


SUPABASE_URL = "https://miihsvfvklwvwvvgeboh.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_b4Eb9zJqAba3m-cMCARx0Q_x0A-gICT"
SUPABASE_ISSUER = f"{SUPABASE_URL}/auth/v1"
SUPABASE_JWKS_URL = f"{SUPABASE_ISSUER}/.well-known/jwks.json"
SUPABASE_AUTHORIZATION_SERVER = SUPABASE_ISSUER
SUPABASE_TOKEN_AUDIENCE = "authenticated"

REFRESH_TOKEN_SECRET = "account.supabase_refresh_token"
USER_ID_SECRET = "account.supabase_user_id"
USER_EMAIL_SECRET = "account.supabase_email"


class AccountError(RuntimeError):
    pass


@dataclass(frozen=True)
class AccountSession:
    user_id: str
    email: str
    access_token: str
    refresh_token: str
    expires_at: int


@dataclass(frozen=True)
class RegistrationResult:
    session: AccountSession | None
    confirmation_required: bool


@dataclass(frozen=True)
class DeviceSummary:
    id: str
    display_name: str
    platform: str
    app_version: str
    status: str
    created_at: str
    updated_at: str
    is_current: bool


class SupabaseAccountClient:
    """Native PrivacyGate account client; passwords are never persisted."""

    def __init__(self, identity_store: ConnectionIdentityStore) -> None:
        self.identity_store = identity_store
        self.secrets = identity_store.secrets
        self._current_session: AccountSession | None = None
        self._http = httpx.Client(
            timeout=20,
            verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            headers={
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "User-Agent": f"AI-PM-LAB-Privacy-Gate/{__version__}",
            },
        )

    @property
    def current_user_id(self) -> str | None:
        return self.secrets.get(USER_ID_SECRET)

    @property
    def current_email(self) -> str | None:
        return self.secrets.get(USER_EMAIL_SECRET)

    @property
    def current_session(self) -> AccountSession | None:
        """Return the active access-token session held only in process memory."""
        return self._current_session

    def register(self, email: str, password: str) -> RegistrationResult:
        response = self._http.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            json={"email": email.strip(), "password": password},
        )
        payload = self._payload(response)
        if payload.get("access_token"):
            session = self._session(payload)
            self._save(session)
            self.bind_device(session)
            return RegistrationResult(session=session, confirmation_required=False)
        return RegistrationResult(session=None, confirmation_required=True)

    def sign_in(self, email: str, password: str) -> AccountSession:
        response = self._http.post(
            f"{SUPABASE_URL}/auth/v1/token",
            params={"grant_type": "password"},
            json={"email": email.strip(), "password": password},
        )
        session = self._session(self._payload(response))
        self._save(session)
        self.bind_device(session)
        return session

    def restore_session(self) -> AccountSession | None:
        refresh_token = self.secrets.get(REFRESH_TOKEN_SECRET)
        if not refresh_token:
            return None
        response = self._http.post(
            f"{SUPABASE_URL}/auth/v1/token",
            params={"grant_type": "refresh_token"},
            json={"refresh_token": refresh_token},
        )
        if response.status_code >= 400:
            self.clear_local_session()
            return None
        session = self._session(response.json())
        self._save(session)
        self.bind_device(session)
        return session

    def sign_out(self) -> None:
        refresh_token = self.secrets.get(REFRESH_TOKEN_SECRET)
        if refresh_token:
            try:
                session = self.restore_session()
                if session:
                    self._http.post(
                        f"{SUPABASE_URL}/auth/v1/logout",
                        headers={"Authorization": f"Bearer {session.access_token}"},
                    )
            except (httpx.HTTPError, AccountError):
                pass
        self.clear_local_session()

    def clear_local_session(self) -> None:
        self._current_session = None
        for name in (REFRESH_TOKEN_SECRET, USER_ID_SECRET, USER_EMAIL_SECRET):
            self.secrets.delete(name)

    def current_installation_hash(self) -> str:
        identity = self.identity_store.load_or_create()
        return hashlib.sha256(identity.installation_id.encode("ascii")).hexdigest()

    def bind_device(self, session: AccountSession) -> None:
        identity = self.identity_store.load_or_create()
        response = self._http.post(
            f"{SUPABASE_URL}/rest/v1/privacy_gate_devices",
            params={"on_conflict": "installation_hash"},
            headers={
                "Authorization": f"Bearer {session.access_token}",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json={
                "user_id": session.user_id,
                "installation_hash": self.current_installation_hash(),
                "display_name": identity.display_name,
                "platform": platform.system().lower(),
                "app_version": __version__,
                # updated_at doubles as a minimal last-seen heartbeat. It is
                # refreshed only by a signed-in PrivacyGate desktop session.
                "updated_at": datetime.now(timezone.utc).isoformat(),
                # Status is intentionally omitted. New rows use the DB default
                # "active", while an admin-disabled/revoked device cannot be
                # silently reactivated just because the account refreshes.
            },
        )
        self._payload(response, allow_empty=True)

    def list_devices(self, session: AccountSession) -> list[DeviceSummary]:
        response = self._http.get(
            f"{SUPABASE_URL}/rest/v1/privacy_gate_devices",
            params={
                "select": (
                    "id,installation_hash,display_name,platform,app_version,"
                    "status,created_at,updated_at"
                ),
                "user_id": f"eq.{session.user_id}",
                "order": "updated_at.desc",
            },
            headers={"Authorization": f"Bearer {session.access_token}"},
        )
        rows = self._list_payload(response)
        current_hash = self.current_installation_hash()
        devices: list[DeviceSummary] = []
        for row in rows:
            devices.append(
                DeviceSummary(
                    id=str(row.get("id") or ""),
                    display_name=str(row.get("display_name") or "This device"),
                    platform=str(row.get("platform") or "unknown"),
                    app_version=str(row.get("app_version") or ""),
                    status=str(row.get("status") or "active"),
                    created_at=str(row.get("created_at") or ""),
                    updated_at=str(row.get("updated_at") or ""),
                    is_current=str(row.get("installation_hash") or "") == current_hash,
                )
            )
        return devices

    def _save(self, session: AccountSession) -> None:
        self._current_session = session
        self.secrets.set(REFRESH_TOKEN_SECRET, session.refresh_token)
        self.secrets.set(USER_ID_SECRET, session.user_id)
        self.secrets.set(USER_EMAIL_SECRET, session.email)

    @staticmethod
    def _session(payload: dict[str, object]) -> AccountSession:
        user = payload.get("user")
        if not isinstance(user, dict):
            raise AccountError("Supabase did not return an authenticated user.")
        user_id = str(user.get("id") or "")
        email = str(user.get("email") or "")
        access_token = str(payload.get("access_token") or "")
        refresh_token = str(payload.get("refresh_token") or "")
        if not all((user_id, email, access_token, refresh_token)):
            raise AccountError("The account session is incomplete.")
        expires_at = int(
            payload.get("expires_at")
            or (time.time() + int(payload.get("expires_in") or 3600))
        )
        return AccountSession(user_id, email, access_token, refresh_token, expires_at)

    @staticmethod
    def _payload(
        response: httpx.Response, *, allow_empty: bool = False
    ) -> dict[str, object]:
        try:
            payload = response.json() if response.content else {}
        except ValueError as error:
            raise AccountError("The account service returned an invalid response.") from error
        if response.status_code >= 400:
            message = ""
            if isinstance(payload, dict):
                message = str(
                    payload.get("msg")
                    or payload.get("message")
                    or payload.get("error_description")
                    or ""
                )
            raise AccountError(
                message or f"Account request failed ({response.status_code})."
            )
        if not payload and not allow_empty:
            raise AccountError("The account service returned an empty response.")
        return dict(payload)

    @staticmethod
    def _list_payload(response: httpx.Response) -> list[dict[str, object]]:
        try:
            payload = response.json() if response.content else []
        except ValueError as error:
            raise AccountError("The account service returned an invalid response.") from error
        if response.status_code >= 400:
            message = ""
            if isinstance(payload, dict):
                message = str(
                    payload.get("msg")
                    or payload.get("message")
                    or payload.get("error_description")
                    or ""
                )
            raise AccountError(
                message or f"Account request failed ({response.status_code})."
            )
        if not isinstance(payload, list):
            raise AccountError("The account service returned an invalid device list.")
        return [dict(item) for item in payload if isinstance(item, dict)]
