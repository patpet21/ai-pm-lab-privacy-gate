from __future__ import annotations

import os
import re
import time

import httpx

from .google_oauth import (
    authorize_desktop,
    refresh_access_token,
    token_expiry_timestamp,
)
from .service import ConnectedAppsService, RemoteItem


DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
PICKER_SCOPES = ("openid", "email", "profile", DRIVE_FILE_SCOPE)


def embedded_picker_enabled() -> bool:
    """Keep the experiment opt-in until it passes the packaged-app test."""
    return os.environ.get("PRIVACY_GATE_ENABLE_EMBEDDED_DRIVE_PICKER", "").strip() == "1"


def configured_picker_api_key(service: ConnectedAppsService) -> str:
    value = os.environ.get("PRIVACY_GATE_GOOGLE_PICKER_API_KEY", "").strip()
    if value:
        try:
            service.secret_store.set("oauth.google.picker_api_key", value)
        except Exception:
            pass
        return value
    return (service.secret_store.get("oauth.google.picker_api_key") or "").strip()


def configured_google_app_id(service: ConnectedAppsService) -> str:
    value = os.environ.get("PRIVACY_GATE_GOOGLE_APP_ID", "").strip()
    if value:
        return value
    client_id = str(service.google_oauth_client_id() or "").strip()
    match = re.match(r"^(\d+)-", client_id)
    return match.group(1) if match else ""


def _active_account(service: ConnectedAppsService) -> tuple[str, str]:
    account_id = "legacy"
    if hasattr(service, "active_account_id"):
        account_id = str(service.active_account_id("google_drive") or account_id)
    label = ""
    if hasattr(service, "list_connected_accounts"):
        for account in service.list_connected_accounts("google_drive"):
            if account.account_id == account_id:
                label = str(account.label or "")
                break
    return account_id, label


def _key(service: ConnectedAppsService, suffix: str) -> str:
    account_id, _label = _active_account(service)
    return f"connected.google_drive.picker.{account_id}.{suffix}"


def _store_picker_token(service: ConnectedAppsService, payload: dict) -> str:
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError("Google did not return a selected-file access token.")
    granted = set(str(payload.get("scope") or "").split())
    if granted and DRIVE_FILE_SCOPE not in granted:
        raise RuntimeError("Google did not grant the Drive selected-file permission.")
    service.secret_store.set(_key(service, "token"), token)
    service.secret_store.set(_key(service, "expires_at"), str(token_expiry_timestamp(payload)))
    refresh = str(payload.get("refresh_token") or "")
    if refresh:
        service.secret_store.set(_key(service, "refresh_token"), refresh)
    return token


def selected_file_access_token(service: ConnectedAppsService) -> str:
    """Return a distinct drive.file token for the currently active Drive account.

    The existing drive.readonly credential is deliberately left untouched. The
    system browser is used only if this account has not granted drive.file yet.
    """
    token = (service.secret_store.get(_key(service, "token")) or "").strip()
    try:
        expires_at = int(service.secret_store.get(_key(service, "expires_at")) or "0")
    except ValueError:
        expires_at = 0
    if token and (not expires_at or time.time() < expires_at - 120):
        return token

    client_id = str(service.google_oauth_client_id() or "").strip()
    client_secret = str(service.google_oauth_client_secret() or "").strip()
    refresh = (service.secret_store.get(_key(service, "refresh_token")) or "").strip()
    if refresh:
        payload = refresh_access_token(client_id, refresh, client_secret=client_secret)
        return _store_picker_token(service, payload)

    _account_id, account_label = _active_account(service)
    payload = authorize_desktop(
        client_id,
        scopes=PICKER_SCOPES,
        client_secret=client_secret,
        include_granted_scopes=False,
        login_hint=account_label if "@" in account_label else "",
    )
    return _store_picker_token(service, payload)


def drive_items_from_ids(
    service: ConnectedAppsService,
    file_ids: tuple[str, ...],
    access_token: str,
) -> tuple[RemoteItem, ...]:
    rows: list[RemoteItem] = []
    headers = {"Authorization": f"Bearer {access_token}"}
    for file_id in file_ids:
        response = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers=headers,
            params={"fields": "id,name,mimeType,modifiedTime,webViewLink"},
            timeout=service.timeout,
        )
        response.raise_for_status()
        item = response.json()
        rows.append(
            RemoteItem(
                "google_drive",
                str(item.get("id") or ""),
                str(item.get("name") or "Untitled"),
                str(item.get("modifiedTime") or ""),
                str(item.get("mimeType") or "file"),
                str(item.get("webViewLink") or ""),
            )
        )
    return tuple(rows)
