from __future__ import annotations

import time

from .google_oauth import (
    authorize_desktop,
    configured_client_id,
    refresh_access_token,
    token_expiry_timestamp,
)
from .service import ConnectedAppsService


_ORIGINAL_TOKEN = ConnectedAppsService._token
_ORIGINAL_DISCONNECT = ConnectedAppsService.disconnect


def _connect_google_oauth(self: ConnectedAppsService, client_id: str | None = None) -> None:
    resolved_client_id = (client_id or configured_client_id()).strip()
    payload = authorize_desktop(resolved_client_id)
    access_token = payload.get("access_token", "")
    refresh_token = payload.get("refresh_token", "")
    if not access_token:
        raise RuntimeError("Google OAuth did not return an access token.")
    self.secret_store.set("connected.google_drive.token", access_token)
    self.secret_store.set("connected.google_drive.client_id", resolved_client_id)
    self.secret_store.set("connected.google_drive.expires_at", str(token_expiry_timestamp(payload)))
    if refresh_token:
        self.secret_store.set("connected.google_drive.refresh_token", refresh_token)


def _google_token(self: ConnectedAppsService) -> str:
    token = self.secret_store.get("connected.google_drive.token") or ""
    if not token:
        raise RuntimeError("Google Drive is not connected")

    expires_raw = self.secret_store.get("connected.google_drive.expires_at") or "0"
    try:
        expires_at = int(expires_raw)
    except ValueError:
        expires_at = 0

    # Refresh slightly before expiry to avoid a request racing the expiry time.
    if expires_at and time.time() < expires_at - 120:
        return token

    refresh_token = self.secret_store.get("connected.google_drive.refresh_token") or ""
    client_id = self.secret_store.get("connected.google_drive.client_id") or configured_client_id()
    if not refresh_token:
        # Legacy/manual-token connection: keep using it until provider rejects it.
        return token

    payload = refresh_access_token(client_id, refresh_token)
    refreshed = payload.get("access_token", "")
    if not refreshed:
        raise RuntimeError("Google Drive refresh did not return an access token")
    self.secret_store.set("connected.google_drive.token", refreshed)
    self.secret_store.set("connected.google_drive.expires_at", str(token_expiry_timestamp(payload)))
    return refreshed


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


def install_google_oauth_adapter() -> None:
    if getattr(ConnectedAppsService, "_google_oauth_installed", False):
        return
    ConnectedAppsService.connect_google_oauth = _connect_google_oauth  # type: ignore[attr-defined]
    ConnectedAppsService._token = _token  # type: ignore[method-assign]
    ConnectedAppsService.disconnect = _disconnect  # type: ignore[method-assign]
    ConnectedAppsService._google_oauth_installed = True  # type: ignore[attr-defined]
