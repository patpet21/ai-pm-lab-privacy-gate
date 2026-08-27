from __future__ import annotations

import time

from .google_oauth import (
    authorize_desktop,
    configured_client_id,
    configured_client_secret,
    refresh_access_token,
    token_expiry_timestamp,
)
from .service import ConnectedAppsService


_ORIGINAL_TOKEN = ConnectedAppsService._token
_ORIGINAL_DISCONNECT = ConnectedAppsService.disconnect


def _stored_google_client_id(self: ConnectedAppsService, preferred_provider: str = "google_drive") -> str:
    """Resolve the app-level Google OAuth client without coupling it to one account."""
    configured = configured_client_id()
    if configured:
        self.secret_store.set("oauth.google.client_id", configured)
        return configured

    cached = self.secret_store.get("oauth.google.client_id") or ""
    if cached:
        return cached

    candidates = (
        f"connected.{preferred_provider}.client_id",
        "connected.google_drive.client_id",
        "connected.gmail.client_id",
    )
    for key in candidates:
        value = (self.secret_store.get(key) or "").strip()
        if value:
            self.secret_store.set("oauth.google.client_id", value)
            return value
    return ""


def _stored_google_client_secret(self: ConnectedAppsService) -> str:
    """Return the Google developer-client secret from encrypted app storage.

    It is application configuration, not an end-user account token. Existing
    Google clients that require it for token exchange/refresh need the value on
    every account, so store it once using the same DPAPI/Keychain SecretStore.
    """
    configured = configured_client_secret()
    if configured:
        self.secret_store.set("oauth.google.client_secret", configured)
        return configured
    return (self.secret_store.get("oauth.google.client_secret") or "").strip()


def _connect_google_oauth(self: ConnectedAppsService, client_id: str | None = None) -> None:
    resolved_client_id = (client_id or _stored_google_client_id(self, "google_drive")).strip()
    client_secret = _stored_google_client_secret(self)
    payload = authorize_desktop(resolved_client_id, client_secret=client_secret)
    access_token = payload.get("access_token", "")
    refresh_token = payload.get("refresh_token", "")
    if not access_token:
        raise RuntimeError("Google OAuth did not return an access token.")
    self.secret_store.set("oauth.google.client_id", resolved_client_id)
    if client_secret:
        self.secret_store.set("oauth.google.client_secret", client_secret)
    self.secret_store.set("connected.google_drive.token", access_token)
    self.secret_store.set("connected.google_drive.client_id", resolved_client_id)
    self.secret_store.set("connected.google_drive.expires_at", str(token_expiry_timestamp(payload)))
    if refresh_token:
        self.secret_store.set("connected.google_drive.refresh_token", refresh_token)


def _refresh_google_token(self: ConnectedAppsService) -> str:
    refresh_token = self.secret_store.get("connected.google_drive.refresh_token") or ""
    client_id = self.secret_store.get("connected.google_drive.client_id") or _stored_google_client_id(self, "google_drive")
    if not refresh_token:
        raise RuntimeError("Google Drive needs to be reconnected because no refresh token is available.")
    client_secret = _stored_google_client_secret(self)
    try:
        payload = refresh_access_token(client_id, refresh_token, client_secret=client_secret)
    except Exception as exc:
        message = str(exc)
        if "client_secret is missing" in message.lower():
            raise RuntimeError(
                "Google needs the developer OAuth client secret for this existing connection. "
                "Configure it once on this device, then retry; PrivacyGate will keep it encrypted locally for all Google accounts."
            ) from exc
        raise
    refreshed = payload.get("access_token", "")
    if not refreshed:
        raise RuntimeError("Google Drive refresh did not return an access token")
    self.secret_store.set("connected.google_drive.token", refreshed)
    self.secret_store.set("connected.google_drive.expires_at", str(token_expiry_timestamp(payload)))
    return refreshed


def _google_token(self: ConnectedAppsService) -> str:
    token = self.secret_store.get("connected.google_drive.token") or ""
    if not token:
        raise RuntimeError("Google Drive is not connected")

    expires_raw = self.secret_store.get("connected.google_drive.expires_at") or "0"
    try:
        expires_at = int(expires_raw)
    except ValueError:
        expires_at = 0

    if expires_at and time.time() < expires_at - 120:
        return token

    refresh_token = self.secret_store.get("connected.google_drive.refresh_token") or ""
    if not refresh_token:
        return token
    return _refresh_google_token(self)


def _force_google_refresh(self: ConnectedAppsService) -> str:
    return _refresh_google_token(self)


def _token(self: ConnectedAppsService, provider: str) -> str:
    if provider == "google_drive":
        return _google_token(self)
    return _ORIGINAL_TOKEN(self, provider)


def _disconnect(self: ConnectedAppsService, provider: str) -> None:
    _ORIGINAL_DISCONNECT(self, provider)
    if provider == "google_drive":
        for key in (
            "connected.google_drive.refresh_token",
            "connected.google_drive.client_id",
            "connected.google_drive.expires_at",
        ):
            self.secret_store.delete(key)
        # Keep oauth.google.client_id and oauth.google.client_secret: these
        # belong to the PrivacyGate developer OAuth client, not one user account.


def install_google_oauth_adapter() -> None:
    if getattr(ConnectedAppsService, "_google_oauth_installed", False):
        return
    ConnectedAppsService.connect_google_oauth = _connect_google_oauth  # type: ignore[attr-defined]
    ConnectedAppsService.force_google_refresh = _force_google_refresh  # type: ignore[attr-defined]
    ConnectedAppsService.google_oauth_client_id = _stored_google_client_id  # type: ignore[attr-defined]
    ConnectedAppsService.google_oauth_client_secret = _stored_google_client_secret  # type: ignore[attr-defined]
    ConnectedAppsService._token = _token  # type: ignore[method-assign]
    ConnectedAppsService.disconnect = _disconnect  # type: ignore[method-assign]
    ConnectedAppsService._google_oauth_installed = True  # type: ignore[attr-defined]
