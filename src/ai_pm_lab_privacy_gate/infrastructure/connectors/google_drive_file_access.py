from __future__ import annotations

import json
import time

import httpx

from .google_oauth import authorize_desktop, refresh_access_token, token_expiry_timestamp
from .google_tls import google_ssl_context
from .service import ConnectedAppsService, RemoteItem


DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def _account_id(service: ConnectedAppsService) -> str:
    if hasattr(service, "active_account_id"):
        value = str(service.active_account_id("google_drive") or "").strip()
        if value:
            return value
    return "standalone"


def _key(service: ConnectedAppsService, suffix: str) -> str:
    return f"connected.google_drive.drive_file.{_account_id(service)}.{suffix}"


def _account_login_hint(service: ConnectedAppsService) -> str:
    if not hasattr(service, "list_connected_accounts"):
        return ""
    active = _account_id(service)
    for record in service.list_connected_accounts("google_drive"):
        if str(record.account_id) == active and "@" in str(record.label):
            return str(record.label).strip()
    return ""


def _store_payload(service: ConnectedAppsService, payload: dict) -> str:
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Google did not return a drive.file access token.")
    service.secret_store.set(_key(service, "token"), token)
    service.secret_store.set(_key(service, "expires_at"), str(token_expiry_timestamp(payload)))
    refresh = str(payload.get("refresh_token") or "").strip()
    if refresh:
        service.secret_store.set(_key(service, "refresh_token"), refresh)
    return token


def _client(service: ConnectedAppsService) -> tuple[str, str]:
    client_id = str(service.google_oauth_client_id() or "").strip()
    client_secret = str(service.google_oauth_client_secret() or "").strip()
    if not client_id:
        raise RuntimeError("Google OAuth client ID is not configured for this build.")
    return client_id, client_secret


def selected_file_access_token(service: ConnectedAppsService) -> str:
    token = str(service.secret_store.get(_key(service, "token")) or "").strip()
    try:
        expires_at = int(service.secret_store.get(_key(service, "expires_at")) or "0")
    except ValueError:
        expires_at = 0
    if token and (not expires_at or time.time() < expires_at - 120):
        return token
    refresh = str(service.secret_store.get(_key(service, "refresh_token")) or "").strip()
    if not refresh:
        return ""
    client_id, client_secret = _client(service)
    return _store_payload(
        service,
        refresh_access_token(client_id, refresh, client_secret=client_secret),
    )


def stored_file_ids(service: ConnectedAppsService) -> tuple[str, ...]:
    raw = str(service.secret_store.get(_key(service, "file_ids")) or "").strip()
    if not raw:
        return ()
    try:
        values = json.loads(raw)
    except Exception:
        return ()
    if not isinstance(values, list):
        return ()
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def pick_additional_files(service: ConnectedAppsService) -> tuple[str, ...]:
    """Run Google's official desktop Picker in the system browser.

    Google permits only drive.file in this desktop Picker request and returns
    the selected IDs alongside the OAuth authorization code.
    """
    client_id, client_secret = _client(service)
    payload = authorize_desktop(
        client_id,
        scopes=(DRIVE_FILE_SCOPE,),
        client_secret=client_secret,
        include_granted_scopes=False,
        login_hint=_account_login_hint(service),
        extra_auth_parameters={
            "prompt": "consent",
            "trigger_onepick": "true",
            "allow_multiple": "true",
        },
    )
    _store_payload(service, payload)
    picked = tuple(
        value.strip()
        for value in str(payload.get("picked_file_ids") or "").split(",")
        if value.strip()
    )
    if not picked:
        raise RuntimeError("Google returned to PrivacyGate without any selected file IDs.")
    merged = tuple(dict.fromkeys((*stored_file_ids(service), *picked)))
    service.secret_store.set(_key(service, "file_ids"), json.dumps(merged, separators=(",", ":")))
    return picked


def authorized_files(service: ConnectedAppsService) -> tuple[RemoteItem, ...]:
    """Resolve metadata only for IDs that the user previously granted."""
    ids = stored_file_ids(service)
    if not ids:
        return ()
    token = selected_file_access_token(service)
    if not token:
        raise RuntimeError("Selected-file access has expired. Add a file with Google Picker to reconnect it.")
    headers = {"Authorization": f"Bearer {token}"}
    rows: list[RemoteItem] = []
    for file_id in ids:
        response = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers=headers,
            params={"fields": "id,name,mimeType,modifiedTime,webViewLink"},
            timeout=service.timeout,
            verify=google_ssl_context(),
        )
        if response.status_code in {403, 404}:
            continue
        response.raise_for_status()
        item = response.json()
        rows.append(
            RemoteItem(
                provider="google_drive",
                item_id=str(item.get("id") or file_id),
                title=str(item.get("name") or "Untitled"),
                subtitle=str(item.get("modifiedTime") or ""),
                kind=str(item.get("mimeType") or "file"),
                url=str(item.get("webViewLink") or ""),
            )
        )
    return tuple(rows)


def authorized_files(service: ConnectedAppsService) -> tuple[RemoteItem, ...]:
    ids = stored_file_ids(service)
    if not ids:
        return ()
    token = selected_file_access_token(service)
    if not token:
        return ()
    headers = {"Authorization": f"Bearer {token}"}
    rows: list[RemoteItem] = []
    for file_id in ids:
        response = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers=headers,
            params={"fields": "id,name,mimeType,modifiedTime,webViewLink"},
            timeout=service.timeout,
            verify=google_ssl_context(),
        )
        if response.status_code in {403, 404}:
            continue
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
