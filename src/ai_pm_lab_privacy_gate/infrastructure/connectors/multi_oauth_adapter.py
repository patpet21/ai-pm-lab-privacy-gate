from __future__ import annotations

import os
import time

import httpx

from .google_oauth import GMAIL_SCOPES, authorize_desktop, configured_client_id, refresh_access_token
from .provider_oauth import connect_asana, connect_clickup, connect_trello, refresh_asana
from .service import ConnectedAppsService, ConnectionTestResult, RemoteItem


_PREV_TOKEN = ConnectedAppsService._token
_PREV_DISCONNECT = ConnectedAppsService.disconnect
_PREV_TEST = ConnectedAppsService.test_connection
_PREV_LIST = ConnectedAppsService.list_root_items


def _store_token_payload(self: ConnectedAppsService, provider: str, payload: dict, *, client_id: str = "") -> None:
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError(f"{self.provider_name(provider)} did not return an access token")
    self.secret_store.set(f"connected.{provider}.token", token)
    if client_id:
        self.secret_store.set(f"connected.{provider}.client_id", client_id)
    expires_in = int(payload.get("expires_in") or 0)
    if expires_in:
        obtained = int(payload.get("obtained_at") or time.time())
        self.secret_store.set(f"connected.{provider}.expires_at", str(obtained + expires_in))
    refresh_token = str(payload.get("refresh_token") or "")
    if refresh_token:
        self.secret_store.set(f"connected.{provider}.refresh_token", refresh_token)


def _connect_gmail_oauth(self: ConnectedAppsService) -> None:
    client_id = configured_client_id()
    payload = authorize_desktop(client_id, scopes=GMAIL_SCOPES)
    _store_token_payload(self, "gmail", payload, client_id=client_id)


def _connect_clickup_oauth(self: ConnectedAppsService) -> None:
    payload = connect_clickup()
    _store_token_payload(self, "clickup", payload, client_id=os.environ.get("PRIVACY_GATE_CLICKUP_CLIENT_ID", "").strip())


def _connect_asana_oauth(self: ConnectedAppsService) -> None:
    payload = connect_asana()
    _store_token_payload(self, "asana", payload, client_id=os.environ.get("PRIVACY_GATE_ASANA_CLIENT_ID", "").strip())


def _connect_trello_oauth(self: ConnectedAppsService) -> None:
    key, token = connect_trello()
    self.secret_store.set("connected.trello.key", key)
    self.secret_store.set("connected.trello.token", token)


def _oauth_token(self: ConnectedAppsService, provider: str) -> str:
    if provider not in {"gmail", "asana"}:
        return _PREV_TOKEN(self, provider)
    token = self.secret_store.get(f"connected.{provider}.token") or ""
    if not token:
        raise RuntimeError(f"{self.provider_name(provider)} is not connected")
    expires_raw = self.secret_store.get(f"connected.{provider}.expires_at") or "0"
    try:
        expires_at = int(expires_raw)
    except ValueError:
        expires_at = 0
    if not expires_at or time.time() < expires_at - 120:
        return token
    refresh_token = self.secret_store.get(f"connected.{provider}.refresh_token") or ""
    if not refresh_token:
        return token
    if provider == "gmail":
        client_id = self.secret_store.get("connected.gmail.client_id") or configured_client_id()
        payload = refresh_access_token(client_id, refresh_token)
    else:
        payload = refresh_asana(refresh_token)
    refreshed = str(payload.get("access_token") or "")
    if not refreshed:
        raise RuntimeError(f"{self.provider_name(provider)} refresh did not return an access token")
    self.secret_store.set(f"connected.{provider}.token", refreshed)
    expires_in = int(payload.get("expires_in") or 3600)
    self.secret_store.set(f"connected.{provider}.expires_at", str(int(time.time()) + expires_in))
    new_refresh = str(payload.get("refresh_token") or "")
    if new_refresh:
        self.secret_store.set(f"connected.{provider}.refresh_token", new_refresh)
    return refreshed


def _disconnect(self: ConnectedAppsService, provider: str) -> None:
    _PREV_DISCONNECT(self, provider)
    if provider in {"gmail", "clickup", "asana", "trello"}:
        for suffix in ("refresh_token", "client_id", "expires_at"):
            self.secret_store.delete(f"connected.{provider}.{suffix}")


def _test_connection(self: ConnectedAppsService, provider: str) -> ConnectionTestResult:
    if provider != "gmail":
        return _PREV_TEST(self, provider)
    try:
        token = self._token("gmail")
        response = httpx.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        email = str(response.json().get("emailAddress") or "Google account")
        return ConnectionTestResult(True, provider, email, "Gmail is connected read-only.")
    except Exception as exc:
        return ConnectionTestResult(False, provider, detail=self._safe_error(exc))


def _header(headers: list[dict], name: str) -> str:
    name = name.lower()
    for item in headers:
        if str(item.get("name") or "").lower() == name:
            return str(item.get("value") or "")
    return ""


def _list_gmail_page(
    self: ConnectedAppsService,
    page_token: str = "",
    limit: int = 30,
    query: str = "",
    label_id: str = "",
) -> tuple[tuple[RemoteItem, ...], str]:
    token = self._token("gmail")
    limit = max(1, min(int(limit), 50))
    headers = {"Authorization": f"Bearer {token}"}
    params: dict[str, object] = {"maxResults": str(limit)}
    if page_token:
        params["pageToken"] = page_token
    if query.strip():
        params["q"] = query.strip()
    if label_id.strip():
        params["labelIds"] = label_id.strip()
    response = httpx.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers=headers,
        params=params,
        timeout=self.timeout,
    )
    response.raise_for_status()
    payload = response.json()
    rows: list[RemoteItem] = []
    for entry in payload.get("messages", [])[:limit]:
        message_id = str(entry.get("id") or "")
        if not message_id:
            continue
        detail = httpx.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            headers=headers,
            params={"format": "metadata", "metadataHeaders": ["Subject", "From", "To", "Date"]},
            timeout=self.timeout,
        )
        detail.raise_for_status()
        message = detail.json()
        msg_headers = message.get("payload", {}).get("headers", [])
        subject = _header(msg_headers, "Subject") or "(No subject)"
        sender = _header(msg_headers, "From")
        date = _header(msg_headers, "Date")
        snippet = str(message.get("snippet") or "").replace("\n", " ").strip()
        subtitle = " • ".join(part for part in (sender, date) if part)
        rows.append(RemoteItem("gmail", message_id, subject, subtitle, "email", snippet))
    return tuple(rows), str(payload.get("nextPageToken") or "")


def _list_root_items(self: ConnectedAppsService, provider: str, limit: int = 30) -> tuple[RemoteItem, ...]:
    if provider != "gmail":
        return _PREV_LIST(self, provider, limit)
    rows, _next_page = _list_gmail_page(self, "", min(limit, 30))
    return rows


def install_multi_oauth_adapter() -> None:
    if getattr(ConnectedAppsService, "_multi_oauth_installed", False):
        return
    ConnectedAppsService.PROVIDERS.update({"gmail": "Gmail"})
    ConnectedAppsService.connect_gmail_oauth = _connect_gmail_oauth  # type: ignore[attr-defined]
    ConnectedAppsService.connect_clickup_oauth = _connect_clickup_oauth  # type: ignore[attr-defined]
    ConnectedAppsService.connect_asana_oauth = _connect_asana_oauth  # type: ignore[attr-defined]
    ConnectedAppsService.connect_trello_oauth = _connect_trello_oauth  # type: ignore[attr-defined]
    ConnectedAppsService.list_gmail_page = _list_gmail_page  # type: ignore[attr-defined]
    ConnectedAppsService._token = _oauth_token  # type: ignore[method-assign]
    ConnectedAppsService.disconnect = _disconnect  # type: ignore[method-assign]
    ConnectedAppsService.test_connection = _test_connection  # type: ignore[method-assign]
    ConnectedAppsService.list_root_items = _list_root_items  # type: ignore[method-assign]
    ConnectedAppsService._multi_oauth_installed = True  # type: ignore[attr-defined]
