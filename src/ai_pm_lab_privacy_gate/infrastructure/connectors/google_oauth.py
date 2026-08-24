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


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def authorize_desktop(client_id: str, timeout_seconds: int = 180) -> dict:
    """Run Google's installed-app OAuth flow with PKCE and a loopback callback.

    The browser receives only the public client id + PKCE challenge. The code
    verifier stays inside PrivacyGate. No database is involved.
    """
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
            body = (
                "<!doctype html><html><body style='font-family:Segoe UI,Arial;padding:40px'>"
                "<h2>PrivacyGate connection completed</h2>"
                "<p>You can close this browser tab and return to PrivacyGate.</p>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
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

    response = httpx.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=20.0,
    )
    if response.status_code >= 400:
        raise GoogleOAuthError(f"Google token exchange failed (HTTP {response.status_code}).")
    payload = response.json()
    if not payload.get("access_token"):
        raise GoogleOAuthError("Google did not return an access token.")
    payload["obtained_at"] = int(time.time())
    return payload


def refresh_access_token(client_id: str, refresh_token: str) -> dict:
    if not client_id or not refresh_token:
        raise GoogleOAuthError("Google connection cannot be refreshed because local OAuth credentials are incomplete.")
    response = httpx.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=20.0,
    )
    if response.status_code >= 400:
        raise GoogleOAuthError(f"Google connection refresh failed (HTTP {response.status_code}). Reconnect Google Drive.")
    payload = response.json()
    if not payload.get("access_token"):
        raise GoogleOAuthError("Google did not return a refreshed access token.")
    payload["obtained_at"] = int(time.time())
    return payload


def token_expiry_timestamp(token_payload: dict) -> int:
    obtained = int(token_payload.get("obtained_at") or time.time())
    expires_in = int(token_payload.get("expires_in") or 3600)
    return obtained + expires_in
