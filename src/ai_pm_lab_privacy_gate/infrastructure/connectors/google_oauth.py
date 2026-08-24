from __future__ import annotations

import base64
import hashlib
import html
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.readonly",
)


class GoogleOAuthError(RuntimeError):
    pass


def configured_client_id() -> str:
    return os.environ.get("PRIVACY_GATE_GOOGLE_CLIENT_ID", "").strip()


def configured_client_secret() -> str:
    # Optional for Google's installed-app flow. Supported for compatibility
    # with Desktop clients whose downloaded credential contains a client secret.
    return os.environ.get("PRIVACY_GATE_GOOGLE_CLIENT_SECRET", "").strip()


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _oauth_error(response: httpx.Response, prefix: str) -> GoogleOAuthError:
    """Return provider diagnostics without ever exposing tokens or auth codes."""
    detail = ""
    try:
        payload = response.json()
        error = str(payload.get("error") or "").strip()
        description = str(payload.get("error_description") or "").strip()
        if error and description:
            detail = f"{error}: {description}"
        elif error:
            detail = error
    except Exception:
        detail = ""
    suffix = f" — {detail}" if detail else ""
    return GoogleOAuthError(f"{prefix} (HTTP {response.status_code}){suffix}")


def authorize_desktop(client_id: str, timeout_seconds: int = 180) -> dict:
    """Run Google's installed-app OAuth flow with PKCE and a loopback callback."""
    client_id = client_id.strip()
    if not client_id:
        raise GoogleOAuthError("Google OAuth client ID is not configured for this build.")

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)
    result: dict[str, str] = {}
    ready = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib API
            query = parse_qs(urlparse(self.path).query)
            result["code"] = query.get("code", [""])[0]
            result["state"] = query.get("state", [""])[0]
            result["error"] = query.get("error", [""])[0]
            success = bool(result.get("code")) and not result.get("error")
            status_title = "Connection received" if success else "Connection not completed"
            status_text = (
                "Google returned securely to PrivacyGate. You can close this tab; PrivacyGate is finishing the connection on this PC."
                if success
                else "Google did not complete the authorization. You can close this tab and return to PrivacyGate."
            )
            body = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>PrivacyGate — {html.escape(status_title)}</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#F7FAFC;color:#062B4F;font-family:Segoe UI,Inter,Arial,sans-serif}}
.card{{width:min(560px,calc(100% - 40px));background:#fff;border:1px solid #D7E2EA;border-radius:20px;padding:38px;box-shadow:0 18px 50px rgba(6,43,79,.10)}}
.mark{{width:54px;height:54px;border-radius:16px;display:grid;place-items:center;background:#E8F6F6;color:#0B7180;font-size:28px;font-weight:800;margin-bottom:22px}}
h1{{margin:0 0 10px;font-size:28px;letter-spacing:-.4px}} p{{margin:0;color:#557184;line-height:1.55;font-size:15px}} .brand{{margin-top:28px;padding-top:20px;border-top:1px solid #E4EBF0;color:#D3A13B;font-size:12px;font-weight:800;letter-spacing:.8px;text-transform:uppercase}}
</style>
</head>
<body><main class='card'><div class='mark'>{'✓' if success else '!'}</div><h1>{html.escape(status_title)}</h1><p>{html.escape(status_text)}</p><div class='brand'>AI PM LAB · PrivacyGate</div></main></body></html>""".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            ready.set()

        def log_message(self, _format, *_args):
            return

    server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
    server.timeout = 0.5
    port = server.server_port
    redirect_uri = f"http://127.0.0.1:{port}"

    auth_query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    webbrowser.open(f"{AUTH_URL}?{auth_query}")

    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline and not ready.is_set():
            server.handle_request()
    finally:
        server.server_close()

    if not ready.is_set():
        raise GoogleOAuthError("Google sign-in timed out. Try Connect again.")
    if result.get("state") != state:
        raise GoogleOAuthError("Google sign-in security check failed (state mismatch).")
    if result.get("error"):
        raise GoogleOAuthError(f"Google authorization was not completed: {result['error']}")
    code = result.get("code", "")
    if not code:
        raise GoogleOAuthError("Google did not return an authorization code.")

    token_data = {
        "client_id": client_id,
        "code": code,
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    client_secret = configured_client_secret()
    if client_secret:
        token_data["client_secret"] = client_secret

    response = httpx.post(TOKEN_URL, data=token_data, timeout=20.0)
    if response.status_code >= 400:
        raise _oauth_error(response, "Google token exchange failed")
    payload = response.json()
    if not payload.get("access_token"):
        raise GoogleOAuthError("Google did not return an access token.")
    payload["obtained_at"] = int(time.time())
    return payload


def refresh_access_token(client_id: str, refresh_token: str) -> dict:
    if not client_id or not refresh_token:
        raise GoogleOAuthError("Google connection cannot be refreshed because local OAuth credentials are incomplete.")
    token_data = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    client_secret = configured_client_secret()
    if client_secret:
        token_data["client_secret"] = client_secret
    response = httpx.post(TOKEN_URL, data=token_data, timeout=20.0)
    if response.status_code >= 400:
        raise _oauth_error(response, "Google connection refresh failed")
    payload = response.json()
    if not payload.get("access_token"):
        raise GoogleOAuthError("Google did not return a refreshed access token.")
    payload["obtained_at"] = int(time.time())
    return payload


def token_expiry_timestamp(token_payload: dict) -> int:
    obtained = int(token_payload.get("obtained_at") or time.time())
    expires_in = int(token_payload.get("expires_in") or 3600)
    return obtained + expires_in
