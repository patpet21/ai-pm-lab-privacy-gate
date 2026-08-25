from __future__ import annotations

import base64
import hashlib
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


ASANA_AUTH_URL = "https://app.asana.com/-/oauth_authorize"
ASANA_TOKEN_URL = "https://app.asana.com/-/oauth_token"
DEFAULT_PUBLIC_REDIRECT = "https://privacygate.propertydex.xyz/oauth/asana/callback"
DEFAULT_LOCAL_CALLBACK = "http://127.0.0.1:8768/asana"


def _exchange_code(*, client_id: str, client_secret: str, code: str, redirect_uri: str, verifier: str) -> dict:
    response = httpx.post(
        ASANA_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
        timeout=25.0,
    )
    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            detail = str(payload.get("error_description") or payload.get("error") or payload.get("message") or "")
        except Exception:
            pass
        raise ProviderOAuthError(
            f"Asana token exchange failed (HTTP {response.status_code})" + (f" — {detail}" if detail else "")
        )
    payload = response.json()
    if not payload.get("access_token"):
        raise ProviderOAuthError("Asana did not return an access token.")
    payload["obtained_at"] = int(time.time())
    return payload


def _connect_asana_automatic() -> dict:
    client_id = os.environ.get("PRIVACY_GATE_ASANA_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PRIVACY_GATE_ASANA_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ProviderOAuthError("OAuth client ID/secret is not configured for this provider.")

    public_redirect = os.environ.get("PRIVACY_GATE_ASANA_REDIRECT_URI", DEFAULT_PUBLIC_REDIRECT).strip()
    local_callback = os.environ.get("PRIVACY_GATE_ASANA_LOCAL_CALLBACK", DEFAULT_LOCAL_CALLBACK).strip()

    public = urlparse(public_redirect)
    if public.scheme != "https" or not public.hostname:
        raise ProviderOAuthError("Asana public redirect must be an HTTPS URL.")
    local = urlparse(local_callback)
    if local.hostname not in {"127.0.0.1", "localhost"} or not local.port:
        raise ProviderOAuthError("Asana local callback must use localhost with a fixed port.")

    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")

    result: dict[str, str] = {}
    ready = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            result["code"] = query.get("code", [""])[0]
            result["state"] = query.get("state", [""])[0]
            result["error"] = query.get("error", [""])[0]
            body = (
                "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<style>body{font-family:Segoe UI,Arial;background:#f7fafc;color:#062b4f;display:grid;place-items:center;min-height:100vh;margin:0}"
                "main{background:white;border:1px solid #d7e2ea;border-radius:18px;padding:32px;max-width:520px;box-shadow:0 18px 48px rgba(6,43,79,.12)}"
                "h1{margin:0 0 10px;font-size:24px}p{color:#557184;line-height:1.5}</style></head><body><main>"
                "<h1>Asana connected</h1><p>You can close this tab and return to PrivacyGate.</p></main></body></html>"
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

    server = HTTPServer((local.hostname or "127.0.0.1", local.port), Handler)
    server.timeout = 0.5

    params = {
        "client_id": client_id,
        "redirect_uri": public_redirect,
        "response_type": "code",
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    }
    scopes = os.environ.get("PRIVACY_GATE_ASANA_SCOPES", "").strip()
    if scopes:
        params["scope"] = scopes

    webbrowser.open(f"{ASANA_AUTH_URL}?{urlencode(params)}")

    deadline = time.monotonic() + 180
    try:
        while time.monotonic() < deadline and not ready.is_set():
            server.handle_request()
    finally:
        server.server_close()

    if not ready.is_set():
        raise ProviderOAuthError("Asana sign-in timed out. Try Connect again.")
    if result.get("state") != state:
        raise ProviderOAuthError("Asana OAuth security check failed (state mismatch).")
    if result.get("error"):
        raise ProviderOAuthError(f"Asana authorization was not completed: {result['error']}")
    code = result.get("code", "")
    if not code:
        raise ProviderOAuthError("Asana did not return an authorization code.")

    return _exchange_code(
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=public_redirect,
        verifier=verifier,
    )


def install_asana_auto_oauth() -> None:
    """Replace the temporary copy/paste OOB flow with automatic browser return."""
    if getattr(ConnectedAppsService, "_asana_auto_oauth_installed", False):
        return

    def connect(self: ConnectedAppsService) -> None:
        payload = _connect_asana_automatic()
        token = str(payload.get("access_token") or "")
        if not token:
            raise RuntimeError("Asana did not return an access token")
        self.secret_store.set("connected.asana.token", token)
        client_id = os.environ.get("PRIVACY_GATE_ASANA_CLIENT_ID", "").strip()
        if client_id:
            self.secret_store.set("connected.asana.client_id", client_id)
        expires_in = int(payload.get("expires_in") or 0)
        if expires_in:
            self.secret_store.set("connected.asana.expires_at", str(int(time.time()) + expires_in))
        refresh_token = str(payload.get("refresh_token") or "")
        if refresh_token:
            self.secret_store.set("connected.asana.refresh_token", refresh_token)

    ConnectedAppsService.connect_asana_oauth = connect  # type: ignore[attr-defined]
    ConnectedAppsService._asana_auto_oauth_installed = True  # type: ignore[attr-defined]
