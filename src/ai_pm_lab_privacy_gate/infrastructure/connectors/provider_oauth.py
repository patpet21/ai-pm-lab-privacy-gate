from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from PySide6.QtWidgets import QInputDialog, QLineEdit


class ProviderOAuthError(RuntimeError):
    pass


def _callback_page(message: str = "Connection received") -> bytes:
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><style>*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#F7FAFC;color:#062B4F;font-family:Segoe UI,Arial,sans-serif}}main{{width:min(540px,calc(100% - 40px));background:#fff;border:1px solid #D7E2EA;border-radius:20px;padding:36px;box-shadow:0 18px 48px rgba(6,43,79,.1)}}b{{display:inline-grid;place-items:center;width:50px;height:50px;border-radius:15px;background:#E8F6F6;color:#0B7180;font-size:24px}}h1{{font-size:25px;margin:18px 0 8px}}p{{color:#557184;line-height:1.55}}small{{display:block;margin-top:24px;padding-top:18px;border-top:1px solid #E4EBF0;color:#D3A13B;font-weight:800;letter-spacing:.7px}}</style></head><body><main><b>✓</b><h1>{message}</h1><p>You can close this tab and return to PrivacyGate. The connection is being stored securely on this device.</p><small>AI PM LAB · PRIVACYGATE</small></main></body></html>""".encode("utf-8")


def _exchange_code(*, token_url: str, client_id: str, client_secret: str, code: str, redirect_uri: str, token_extra: dict[str, str] | None = None) -> dict:
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    data.update(token_extra or {})
    response = httpx.post(token_url, data=data, timeout=25.0)
    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            detail = str(payload.get("error_description") or payload.get("error") or payload.get("message") or "")
        except Exception:
            pass
        raise ProviderOAuthError(
            f"Token exchange failed (HTTP {response.status_code})" + (f" — {detail}" if detail else "")
        )
    payload = response.json()
    if not payload.get("access_token"):
        raise ProviderOAuthError("The provider did not return an access token.")
    payload["obtained_at"] = int(time.time())
    return payload


def _run_code_flow(*, auth_url: str, token_url: str, client_id: str, client_secret: str, redirect_uri: str, extra_auth: dict[str, str] | None = None, token_extra: dict[str, str] | None = None, timeout_seconds: int = 180) -> dict:
    if not client_id or not client_secret:
        raise ProviderOAuthError("OAuth client ID/secret is not configured for this provider.")
    parsed = urlparse(redirect_uri)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.port:
        raise ProviderOAuthError("For desktop testing, the OAuth redirect must be a localhost URL with a fixed port.")

    state = secrets.token_urlsafe(28)
    result: dict[str, str] = {}
    ready = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            result["code"] = query.get("code", [""])[0]
            result["state"] = query.get("state", [""])[0]
            result["error"] = query.get("error", [""])[0]
            body = _callback_page("Connection received" if result.get("code") else "Connection not completed")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            ready.set()

        def log_message(self, _format, *_args):
            return

    server = HTTPServer((parsed.hostname or "127.0.0.1", parsed.port), Handler)
    server.timeout = 0.5
    params = {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "state": state}
    params.update(extra_auth or {})
    webbrowser.open(f"{auth_url}?{urlencode(params)}")

    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline and not ready.is_set():
            server.handle_request()
    finally:
        server.server_close()
    if not ready.is_set():
        raise ProviderOAuthError("Sign-in timed out. Try Connect again.")
    if result.get("state") and result.get("state") != state:
        raise ProviderOAuthError("OAuth security check failed (state mismatch).")
    if result.get("error"):
        raise ProviderOAuthError(f"Authorization was not completed: {result['error']}")
    code = result.get("code", "")
    if not code:
        raise ProviderOAuthError("The provider did not return an authorization code.")

    return _exchange_code(
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
        token_extra=token_extra,
    )


def connect_clickup() -> dict:
    return _run_code_flow(
        auth_url="https://app.clickup.com/api",
        token_url="https://api.clickup.com/api/v2/oauth/token",
        client_id=os.environ.get("PRIVACY_GATE_CLICKUP_CLIENT_ID", "").strip(),
        client_secret=os.environ.get("PRIVACY_GATE_CLICKUP_CLIENT_SECRET", "").strip(),
        redirect_uri=os.environ.get("PRIVACY_GATE_CLICKUP_REDIRECT_URI", "http://127.0.0.1:8767/clickup").strip(),
    )


def connect_asana() -> dict:
    """Asana native OAuth.

    Asana currently rejects HTTP loopback callbacks for native apps and requires
    the out-of-band redirect URI. The browser therefore displays a one-time
    authorization code that the user pastes back into PrivacyGate. PKCE protects
    the authorization-code exchange even though the callback is out-of-band.
    """
    client_id = os.environ.get("PRIVACY_GATE_ASANA_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PRIVACY_GATE_ASANA_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ProviderOAuthError("OAuth client ID/secret is not configured for this provider.")

    redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    state = secrets.token_urlsafe(28)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")

    # Keep the requested access read-only and limited to the resources used by
    # the PrivacyGate Asana browser/import flow.
    scope = os.environ.get(
        "PRIVACY_GATE_ASANA_SCOPES",
        "workspaces:read projects:read tasks:read users:read",
    ).strip()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "scope": scope,
    }
    webbrowser.open(f"https://app.asana.com/-/oauth_authorize?{urlencode(params)}")

    code, ok = QInputDialog.getText(
        None,
        "Connect Asana",
        "After you click Allow in Asana, the browser will show an authorization code.\n\nCopy that code, return to PrivacyGate, and paste it here:",
        QLineEdit.EchoMode.Normal,
    )
    code = code.strip()
    if not ok or not code:
        raise ProviderOAuthError("Asana authorization was cancelled before the code was entered.")

    return _exchange_code(
        token_url="https://app.asana.com/-/oauth_token",
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
        token_extra={"code_verifier": verifier},
    )


def refresh_asana(refresh_token: str) -> dict:
    client_id = os.environ.get("PRIVACY_GATE_ASANA_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PRIVACY_GATE_ASANA_CLIENT_SECRET", "").strip()
    response = httpx.post(
        "https://app.asana.com/-/oauth_token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id, "client_secret": client_secret},
        timeout=25.0,
    )
    if response.status_code >= 400:
        raise ProviderOAuthError(f"Asana refresh failed (HTTP {response.status_code}). Reconnect Asana.")
    payload = response.json()
    payload["obtained_at"] = int(time.time())
    return payload


def connect_trello() -> tuple[str, str]:
    api_key = os.environ.get("PRIVACY_GATE_TRELLO_API_KEY", "").strip()
    return_url = os.environ.get("PRIVACY_GATE_TRELLO_RETURN_URL", "http://localhost:8769/trello").strip()
    if not api_key:
        raise ProviderOAuthError("Trello API key is not configured for this build.")
    parsed = urlparse(return_url)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.port:
        raise ProviderOAuthError("Trello return URL must be localhost with a fixed port for desktop testing.")

    result: dict[str, str] = {}
    ready = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = b"""<!doctype html><html><head><meta charset='utf-8'></head><body><script>const p=new URLSearchParams(location.hash.slice(1));const token=p.get('token')||'';const error=p.get('error')||'';fetch('/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,error})}).then(()=>{document.body.innerHTML=`<div style=\"font-family:Segoe UI,Arial;padding:40px;color:#062B4F\"><h2>PrivacyGate connection received</h2><p>You can close this tab and return to PrivacyGate.</p></div>`;});</script></body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                payload = {}
            result["token"] = str(payload.get("token") or "")
            result["error"] = str(payload.get("error") or "")
            self.send_response(204)
            self.end_headers()
            ready.set()

        def log_message(self, _format, *_args):
            return

    server = HTTPServer((parsed.hostname or "localhost", parsed.port), Handler)
    server.timeout = 0.5
    params = {
        "expiration": "never",
        "scope": "read",
        "response_type": "token",
        "key": api_key,
        "return_url": return_url,
        "callback_method": "fragment",
        "name": "AI PM LAB PrivacyGate",
    }
    webbrowser.open(f"https://trello.com/1/authorize?{urlencode(params)}")
    deadline = time.monotonic() + 180
    try:
        while time.monotonic() < deadline and not ready.is_set():
            server.handle_request()
    finally:
        server.server_close()
    if not ready.is_set():
        raise ProviderOAuthError("Trello authorization timed out.")
    if result.get("error"):
        raise ProviderOAuthError(f"Trello authorization failed: {result['error']}")
    token = result.get("token", "")
    if not token:
        raise ProviderOAuthError("Trello did not return an authorization token.")
    return api_key, token
