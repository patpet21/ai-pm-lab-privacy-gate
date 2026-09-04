from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

import httpx

from .google_oauth import authorize_desktop, refresh_access_token, token_expiry_timestamp
from .google_tls import google_ssl_context
from .service import ConnectedAppsService, RemoteItem


DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"

_INDEX_KEY = "connected.google_drive.drive_file.accounts"
_ACTIVE_KEY = "connected.google_drive.drive_file.active"
_ACCOUNT_PREFIX = "connected.google_drive.drive_file.account"
_ACCOUNT_SUFFIXES = (
    "token",
    "refresh_token",
    "expires_at",
    "file_ids",
    "label",
    "email",
    "display_name",
    "permission_id",
)


@dataclass(frozen=True)
class DriveFileAccount:
    account_id: str
    label: str
    email: str = ""
    is_active: bool = False


def _delete(service: ConnectedAppsService, key: str) -> None:
    delete = getattr(service.secret_store, "delete", None)
    if callable(delete):
        delete(key)


def _account_key(account_id: str, suffix: str) -> str:
    return f"{_ACCOUNT_PREFIX}.{account_id}.{suffix}"


def _load_account_ids(service: ConnectedAppsService) -> list[str]:
    raw = str(service.secret_store.get(_INDEX_KEY) or "").strip()
    if not raw:
        return []
    try:
        values = json.loads(raw)
    except Exception:
        return []
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        account_id = str(value or "").strip()
        if account_id and account_id not in result:
            result.append(account_id)
    return result


def _save_account_ids(service: ConnectedAppsService, values: list[str]) -> None:
    values = list(dict.fromkeys(value for value in values if value))
    if values:
        service.secret_store.set(_INDEX_KEY, json.dumps(values, separators=(",", ":")))
    else:
        _delete(service, _INDEX_KEY)


def _legacy_candidates(service: ConnectedAppsService) -> list[tuple[str, str]]:
    """Return POC-era drive.file key suffixes that may need one-time migration."""

    candidates: list[tuple[str, str]] = [("standalone", "Selected-file account")]
    active_full = ""
    if hasattr(service, "active_account_id"):
        try:
            active_full = str(service.active_account_id("google_drive") or "").strip()
        except Exception:
            active_full = ""
    if active_full:
        candidates.append((active_full, "Selected-file account"))

    if hasattr(service, "list_connected_accounts"):
        try:
            for record in service.list_connected_accounts("google_drive"):
                candidate = str(record.account_id or "").strip()
                if not candidate:
                    continue
                label = str(record.label or "").strip() or "Selected-file account"
                candidates.append((candidate, f"{label} · selected files"))
        except Exception:
            pass

    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for candidate, label in candidates:
        if candidate and candidate not in seen:
            deduped.append((candidate, label))
            seen.add(candidate)
    return deduped


def _migrate_legacy(service: ConnectedAppsService) -> None:
    """Move the original POC keys away from the Full Drive account namespace.

    The 8d451c POC stored drive.file state under the currently active
    drive.readonly account id (or ``standalone``). Keep those grants usable, but
    copy them into an independent selected-file registry so future Picker
    authorizations never depend on the Full Drive account selection.
    """

    if _load_account_ids(service):
        return

    migrated: list[str] = []
    preferred = ""
    active_full = ""
    if hasattr(service, "active_account_id"):
        try:
            active_full = str(service.active_account_id("google_drive") or "").strip()
        except Exception:
            active_full = ""

    for legacy_id, label in _legacy_candidates(service):
        old_prefix = f"connected.google_drive.drive_file.{legacy_id}"
        token = str(service.secret_store.get(f"{old_prefix}.token") or "").strip()
        file_ids = str(service.secret_store.get(f"{old_prefix}.file_ids") or "").strip()
        if not token and not file_ids:
            continue

        digest = hashlib.sha256(f"legacy:{legacy_id}".encode("utf-8")).hexdigest()[:12]
        account_id = f"legacy-{digest}"
        for suffix in ("token", "refresh_token", "expires_at", "file_ids"):
            value = service.secret_store.get(f"{old_prefix}.{suffix}")
            if value not in (None, ""):
                service.secret_store.set(_account_key(account_id, suffix), str(value))
        service.secret_store.set(_account_key(account_id, "label"), label)
        migrated.append(account_id)
        if legacy_id == active_full:
            preferred = account_id

    if migrated:
        _save_account_ids(service, migrated)
        service.secret_store.set(_ACTIVE_KEY, preferred or migrated[0])


def _active_account_id(service: ConnectedAppsService) -> str:
    _migrate_legacy(service)
    ids = _load_account_ids(service)
    if not ids:
        return ""
    active = str(service.secret_store.get(_ACTIVE_KEY) or "").strip()
    if active not in ids:
        active = ids[0]
        service.secret_store.set(_ACTIVE_KEY, active)
    return active


def list_selected_file_accounts(service: ConnectedAppsService) -> tuple[DriveFileAccount, ...]:
    _migrate_legacy(service)
    ids = _load_account_ids(service)
    active = _active_account_id(service) if ids else ""
    rows: list[DriveFileAccount] = []
    for account_id in ids:
        email = str(service.secret_store.get(_account_key(account_id, "email")) or "").strip()
        label = (
            str(service.secret_store.get(_account_key(account_id, "label")) or "").strip()
            or email
            or "Google Drive selected-file account"
        )
        rows.append(
            DriveFileAccount(
                account_id=account_id,
                label=label,
                email=email,
                is_active=account_id == active,
            )
        )
    return tuple(rows)


def selected_file_active_account(service: ConnectedAppsService) -> DriveFileAccount | None:
    active = _active_account_id(service)
    if not active:
        return None
    for record in list_selected_file_accounts(service):
        if record.account_id == active:
            return record
    return None


def activate_selected_file_account(service: ConnectedAppsService, account_id: str) -> None:
    _migrate_legacy(service)
    account_id = str(account_id or "").strip()
    if account_id not in _load_account_ids(service):
        raise ValueError("Selected-file Google Drive account was not found.")
    service.secret_store.set(_ACTIVE_KEY, account_id)


def disconnect_selected_file_account(service: ConnectedAppsService, account_id: str = "") -> None:
    _migrate_legacy(service)
    ids = _load_account_ids(service)
    target = str(account_id or "").strip() or _active_account_id(service)
    if not target or target not in ids:
        return

    for suffix in _ACCOUNT_SUFFIXES:
        _delete(service, _account_key(target, suffix))

    remaining = [value for value in ids if value != target]
    _save_account_ids(service, remaining)
    if remaining:
        current = str(service.secret_store.get(_ACTIVE_KEY) or "").strip()
        service.secret_store.set(_ACTIVE_KEY, current if current in remaining else remaining[0])
    else:
        _delete(service, _ACTIVE_KEY)


def _client(service: ConnectedAppsService) -> tuple[str, str]:
    client_id = str(service.google_oauth_client_id() or "").strip()
    client_secret = str(service.google_oauth_client_secret() or "").strip()
    if not client_id:
        raise RuntimeError("Google OAuth client ID is not configured for this build.")
    return client_id, client_secret


def _store_payload(service: ConnectedAppsService, payload: dict, account_id: str) -> str:
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Google did not return a drive.file access token.")
    service.secret_store.set(_account_key(account_id, "token"), token)
    service.secret_store.set(
        _account_key(account_id, "expires_at"),
        str(token_expiry_timestamp(payload)),
    )
    refresh = str(payload.get("refresh_token") or "").strip()
    if refresh:
        service.secret_store.set(_account_key(account_id, "refresh_token"), refresh)
    return token


def _about_user(service: ConnectedAppsService, token: str) -> dict:
    response = httpx.get(
        "https://www.googleapis.com/drive/v3/about",
        headers={"Authorization": f"Bearer {token}"},
        params={"fields": "user(displayName,emailAddress,permissionId)"},
        timeout=service.timeout,
        verify=google_ssl_context(),
    )
    response.raise_for_status()
    payload = response.json()
    user = payload.get("user") if isinstance(payload, dict) else None
    if not isinstance(user, dict):
        raise RuntimeError("Google Drive did not return the selected account identity.")
    return user


def _identity_account_id(user: dict) -> str:
    permission_id = str(user.get("permissionId") or "").strip()
    email = str(user.get("emailAddress") or "").strip().lower()
    identity = permission_id or email
    if not identity:
        raise RuntimeError(
            "Google Drive did not return a stable identity for the selected-file account."
        )
    digest = hashlib.sha256(f"drive.file:{identity}".encode("utf-8")).hexdigest()[:16]
    return digest


def _register_picker_account(
    service: ConnectedAppsService,
    *,
    account_id: str,
    user: dict,
    payload: dict,
) -> None:
    _migrate_legacy(service)
    ids = _load_account_ids(service)
    if account_id not in ids:
        ids.append(account_id)
        _save_account_ids(service, ids)

    email = str(user.get("emailAddress") or "").strip()
    display_name = str(user.get("displayName") or "").strip()
    permission_id = str(user.get("permissionId") or "").strip()
    label = email or display_name or "Google Drive selected-file account"

    service.secret_store.set(_account_key(account_id, "label"), label)
    if email:
        service.secret_store.set(_account_key(account_id, "email"), email)
    if display_name:
        service.secret_store.set(_account_key(account_id, "display_name"), display_name)
    if permission_id:
        service.secret_store.set(_account_key(account_id, "permission_id"), permission_id)
    _store_payload(service, payload, account_id)
    service.secret_store.set(_ACTIVE_KEY, account_id)


def selected_file_access_token(
    service: ConnectedAppsService,
    account_id: str = "",
) -> str:
    resolved = str(account_id or "").strip() or _active_account_id(service)
    if not resolved:
        return ""

    token = str(service.secret_store.get(_account_key(resolved, "token")) or "").strip()
    try:
        expires_at = int(
            service.secret_store.get(_account_key(resolved, "expires_at")) or "0"
        )
    except ValueError:
        expires_at = 0
    if token and (not expires_at or time.time() < expires_at - 120):
        return token

    refresh = str(
        service.secret_store.get(_account_key(resolved, "refresh_token")) or ""
    ).strip()
    if not refresh:
        return token

    client_id, client_secret = _client(service)
    return _store_payload(
        service,
        refresh_access_token(client_id, refresh, client_secret=client_secret),
        resolved,
    )


def stored_file_ids(
    service: ConnectedAppsService,
    account_id: str = "",
) -> tuple[str, ...]:
    resolved = str(account_id or "").strip() or _active_account_id(service)
    if not resolved:
        return ()
    raw = str(service.secret_store.get(_account_key(resolved, "file_ids")) or "").strip()
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
    """Use Google's official desktop Picker with drive.file only.

    The browser handoff is intentionally independent from the Full Drive
    ``drive.readonly`` connection. Google chooses the account for this Picker
    session, then PrivacyGate identifies that account via Drive ``about.get`` and
    stores its token and selected file ids in the separate drive.file registry.
    """

    client_id, client_secret = _client(service)
    payload = authorize_desktop(
        client_id,
        scopes=(DRIVE_FILE_SCOPE,),
        client_secret=client_secret,
        include_granted_scopes=False,
        extra_auth_parameters={
            "prompt": "select_account consent",
            "trigger_onepick": "true",
            "allow_multiple": "true",
        },
    )
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Google did not return a drive.file access token.")

    picked = tuple(
        value.strip()
        for value in str(payload.get("picked_file_ids") or "").split(",")
        if value.strip()
    )
    if not picked:
        raise RuntimeError("Google returned to PrivacyGate without any selected file IDs.")

    user = _about_user(service, token)
    account_id = _identity_account_id(user)
    _register_picker_account(
        service,
        account_id=account_id,
        user=user,
        payload=payload,
    )

    merged = tuple(dict.fromkeys((*stored_file_ids(service, account_id), *picked)))
    service.secret_store.set(
        _account_key(account_id, "file_ids"),
        json.dumps(merged, separators=(",", ":")),
    )
    return picked


def authorized_files(
    service: ConnectedAppsService,
    account_id: str = "",
) -> tuple[RemoteItem, ...]:
    """Resolve metadata only for ids explicitly granted to one drive.file account."""

    resolved = str(account_id or "").strip() or _active_account_id(service)
    if not resolved:
        return ()
    ids = stored_file_ids(service, resolved)
    if not ids:
        return ()

    token = selected_file_access_token(service, resolved)
    if not token:
        raise RuntimeError(
            "Selected-file access has expired. Choose a file with Google Picker to reconnect it."
        )

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
