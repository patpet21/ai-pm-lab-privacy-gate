from __future__ import annotations

import time

import httpx

from .google_drive_picker import authorize_drive_file_desktop, authorize_drive_picker_desktop
from .google_oauth import (
    configured_client_id,
    configured_client_secret,
    refresh_access_token,
    token_expiry_timestamp,
)
from .service import ConnectedAppsService, RemoteItem


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
    payload = authorize_drive_file_desktop(
        resolved_client_id,
        client_secret=client_secret,
    )
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


def _drive_identity(self: ConnectedAppsService, token: str) -> tuple[str, str]:
    response = httpx.get(
        "https://www.googleapis.com/drive/v3/about",
        headers={"Authorization": f"Bearer {token}"},
        params={"fields": "user(displayName,emailAddress,permissionId)"},
        timeout=self.timeout,
    )
    response.raise_for_status()
    user = response.json().get("user") or {}
    identity = str(user.get("emailAddress") or user.get("permissionId") or "").strip()
    label = str(user.get("emailAddress") or user.get("displayName") or "Google Drive account").strip()
    return identity, label


def _sync_active_drive_alias(self: ConnectedAppsService) -> None:
    registry = getattr(self, "_multi_account_registry", None)
    if registry is not None and hasattr(registry, "sync_active_from_legacy"):
        registry.sync_active_from_legacy("google_drive")


def _pick_google_drive_items(self: ConnectedAppsService) -> tuple[RemoteItem, ...]:
    """Open Google Picker for the active Drive account and return selected files.

    Picker authorization is intentionally separate from the persistent Drive
    connection. It grants per-file access only, verifies that the Picker account
    matches the active PrivacyGate account, then refreshes that account's local
    token before the existing import pipeline downloads the selected file.
    """
    current_token = self._token("google_drive")
    expected_identity = ""
    expected_label = ""
    try:
        expected_identity, expected_label = _drive_identity(self, current_token)
    except Exception:
        expected_identity = ""
        expected_label = ""

    resolved_client_id = _stored_google_client_id(self, "google_drive").strip()
    client_secret = _stored_google_client_secret(self)
    payload = authorize_drive_picker_desktop(
        resolved_client_id,
        client_secret=client_secret,
        login_hint=expected_identity or expected_label,
    )
    picked_ids = tuple(payload.get("picked_file_ids") or ())
    if not picked_ids:
        return ()

    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("Google Drive Picker did not return an access token.")

    actual_identity, actual_label = _drive_identity(self, access_token)
    if (
        expected_identity
        and actual_identity
        and expected_identity.casefold() != actual_identity.casefold()
    ):
        raise RuntimeError(
            "Google Picker used a different Google account. "
            f"Choose the active Drive account ({expected_label or expected_identity}) and try again."
        )

    self.secret_store.set("oauth.google.client_id", resolved_client_id)
    if client_secret:
        self.secret_store.set("oauth.google.client_secret", client_secret)
    self.secret_store.set("connected.google_drive.token", access_token)
    self.secret_store.set("connected.google_drive.client_id", resolved_client_id)
    self.secret_store.set("connected.google_drive.expires_at", str(token_expiry_timestamp(payload)))
    refresh_token = str(payload.get("refresh_token") or "").strip()
    if refresh_token:
        self.secret_store.set("connected.google_drive.refresh_token", refresh_token)
    _sync_active_drive_alias(self)

    headers = {"Authorization": f"Bearer {access_token}"}
    rows: list[RemoteItem] = []
    for file_id in picked_ids:
        response = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers=headers,
            params={
                "fields": "id,name,mimeType,modifiedTime,webViewLink",
                "supportsAllDrives": "true",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        item = response.json()
        rows.append(
            RemoteItem(
                "google_drive",
                str(item.get("id") or file_id),
                str(item.get("name") or "Google Drive document"),
                str(item.get("modifiedTime") or ""),
                str(item.get("mimeType") or "file"),
                str(item.get("webViewLink") or ""),
            )
        )
    return tuple(rows)


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
    ConnectedAppsService.pick_google_drive_items = _pick_google_drive_items  # type: ignore[attr-defined]
    ConnectedAppsService.force_google_refresh = _force_google_refresh  # type: ignore[attr-defined]
    ConnectedAppsService.google_oauth_client_id = _stored_google_client_id  # type: ignore[attr-defined]
    ConnectedAppsService.google_oauth_client_secret = _stored_google_client_secret  # type: ignore[attr-defined]
    ConnectedAppsService._token = _token  # type: ignore[method-assign]
    ConnectedAppsService.disconnect = _disconnect  # type: ignore[method-assign]
    ConnectedAppsService._google_oauth_installed = True  # type: ignore[attr-defined]
