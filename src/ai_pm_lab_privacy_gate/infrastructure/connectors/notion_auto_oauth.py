from __future__ import annotations

import base64
import json
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .provider_oauth import ProviderOAuthError
from .service import ConnectedAppsService


NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
DEFAULT_PUBLIC_REDIRECT = "https://privacygate.propertydex.xyz/oauth/notion/callback"
DEFAULT_LOCAL_CALLBACK = "http://127.0.0.1:8770/notion"


def _exchange_code(*, client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    response = httpx.post(
        NOTION_TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Notion-Version": "2026-03-11",
        },
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=25.0,
    )
    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            detail = str(payload.get("message") or payload.get("error_description") or payload.get("error") or "")
        except Exception:
            pass
        raise ProviderOAuthError(
            f"Notion token exchange failed (HTTP {response.status_code})" + (f" — {detail}" if detail else "")
        )
    payload = response.json()
    if not payload.get("access_token"):
        raise ProviderOAuthError("Notion did not return an access token.")
    payload["obtained_at"] = int(time.time())
    return payload


def refresh_notion(refresh_token: str) -> dict:
    client_id = os.environ.get("PRIVACY_GATE_NOTION_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PRIVACY_GATE_NOTION_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ProviderOAuthError("Notion OAuth client ID/secret is not configured.")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    response = httpx.post(
        NOTION_TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Notion-Version": "2026-03-11",
        },
        json={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=25.0,
    )
    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            detail = str(payload.get("message") or payload.get("error_description") or payload.get("error") or "")
        except Exception:
            pass
        raise ProviderOAuthError(
            f"Notion token refresh failed (HTTP {response.status_code})" + (f" — {detail}" if detail else "")
        )
    payload = response.json()
    if not payload.get("access_token"):
        raise ProviderOAuthError("Notion refresh did not return an access token.")
    payload["obtained_at"] = int(time.time())
    return payload


def _connect_notion_automatic() -> dict:
    client_id = os.environ.get("PRIVACY_GATE_NOTION_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PRIVACY_GATE_NOTION_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ProviderOAuthError("OAuth client ID/secret is not configured for Notion.")

    public_redirect = os.environ.get("PRIVACY_GATE_NOTION_REDIRECT_URI", DEFAULT_PUBLIC_REDIRECT).strip()
    local_callback = os.environ.get("PRIVACY_GATE_NOTION_LOCAL_CALLBACK", DEFAULT_LOCAL_CALLBACK).strip()

    public = urlparse(public_redirect)
    if public.scheme != "https" or not public.hostname:
        raise ProviderOAuthError("Notion public redirect must be an HTTPS URL.")
    local = urlparse(local_callback)
    if local.hostname not in {"127.0.0.1", "localhost"} or not local.port:
        raise ProviderOAuthError("Notion local callback must use localhost with a fixed port.")

    state = secrets.token_urlsafe(32)
    result: dict[str, str] = {}
    ready = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/notion":
                self.send_response(404)
                self.end_headers()
                return
            query = parse_qs(parsed.query)
            result["code"] = query.get("code", [""])[0]
            result["state"] = query.get("state", [""])[0]
            result["error"] = query.get("error", [""])[0]
            body = (
                "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<style>body{font-family:Segoe UI,Arial;background:#f7fafc;color:#062b4f;display:grid;place-items:center;min-height:100vh;margin:0}"
                "main{background:white;border:1px solid #d7e2ea;border-radius:18px;padding:32px;max-width:520px;box-shadow:0 18px 48px rgba(6,43,79,.12)}"
                "h1{margin:0 0 10px;font-size:24px}p{color:#557184;line-height:1.5}</style></head><body><main>"
                "<h1>Notion connected</h1><p>You can close this tab and return to PrivacyGate.</p></main></body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            ready.set()

        def log_message(self, _format, *_args):
            return

    try:
        server = HTTPServer((local.hostname or "127.0.0.1", local.port), Handler)
    except OSError as exc:
        raise ProviderOAuthError(
            "PrivacyGate could not open its local Notion callback on port 8770. Close any other PrivacyGate test window and try again."
        ) from exc
    server.timeout = 0.5

    params = {
        "client_id": client_id,
        "redirect_uri": public_redirect,
        "response_type": "code",
        "owner": "user",
        "state": state,
    }
    webbrowser.open(f"{NOTION_AUTH_URL}?{urlencode(params)}")

    deadline = time.monotonic() + 180
    try:
        while time.monotonic() < deadline and not ready.is_set():
            server.handle_request()
    finally:
        server.server_close()

    if not ready.is_set():
        raise ProviderOAuthError("Notion sign-in timed out. Try Connect again.")
    if result.get("state") != state:
        raise ProviderOAuthError("Notion OAuth security check failed (state mismatch).")
    if result.get("error"):
        raise ProviderOAuthError(f"Notion authorization was not completed: {result['error']}")
    code = result.get("code", "")
    if not code:
        raise ProviderOAuthError("Notion did not return an authorization code.")

    return _exchange_code(
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=public_redirect,
    )


def install_notion_auto_oauth() -> None:
    """Use an HTTPS relay plus local loopback for a customer-friendly Notion OAuth flow."""
    if getattr(ConnectedAppsService, "_notion_auto_oauth_installed", False):
        return

    previous_disconnect = ConnectedAppsService.disconnect

    def connect(self: ConnectedAppsService) -> None:
        payload = _connect_notion_automatic()
        token = str(payload.get("access_token") or "")
        if not token:
            raise RuntimeError("Notion did not return an access token")
        self.secret_store.set("connected.notion.token", token)
        client_id = os.environ.get("PRIVACY_GATE_NOTION_CLIENT_ID", "").strip()
        if client_id:
            self.secret_store.set("connected.notion.client_id", client_id)
        refresh_token = str(payload.get("refresh_token") or "")
        if refresh_token:
            self.secret_store.set("connected.notion.refresh_token", refresh_token)
        for key in ("workspace_id", "workspace_name", "workspace_icon", "bot_id", "owner"):
            value = payload.get(key)
            if value not in (None, ""):
                self.secret_store.set(
                    f"connected.notion.{key}",
                    json.dumps(value) if isinstance(value, (dict, list)) else str(value),
                )

    def disconnect(self: ConnectedAppsService, provider: str) -> None:
        previous_disconnect(self, provider)
        if provider == "notion":
            for suffix in (
                "refresh_token",
                "client_id",
                "workspace_id",
                "workspace_name",
                "workspace_icon",
                "bot_id",
                "owner",
            ):
                self.secret_store.delete(f"connected.notion.{suffix}")

    ConnectedAppsService.connect_notion_oauth = connect  # type: ignore[attr-defined]
    ConnectedAppsService.disconnect = disconnect  # type: ignore[method-assign]
    ConnectedAppsService._notion_auto_oauth_installed = True  # type: ignore[attr-defined]
