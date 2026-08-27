from __future__ import annotations

import html
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .google_oauth import (
    AUTH_URL,
    TOKEN_URL,
    GoogleOAuthError,
    _oauth_error,
    _pkce_pair,
    _resolved_secret,
)


DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DRIVE_PICKER_MIMETYPES = (
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
)


def _authorize_drive_file_flow(
    client_id: str,
    *,
    timeout_seconds: int,
    client_secret: str | None,
    trigger_picker: bool,
    login_hint: str,
) -> dict:
    """Run a desktop OAuth flow that is strictly limited to ``drive.file``."""
    client_id = client_id.strip()
    if not client_id:
        raise GoogleOAuthError("Google OAuth client ID is not configured for this build.")

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)
    result: dict[str, str] = {}
    ready = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            result["code"] = query.get("code", [""])[0]
            result["state"] = query.get("state", [""])[0]
            result["error"] = query.get("error", [""])[0]
            result["picked_file_ids"] = query.get("picked_file_ids", [""])[0]
            success = bool(result.get("code")) and not result.get("error")
            if trigger_picker:
                title = "Drive selection received" if success else "Drive selection not completed"
                text = (
                    "Google returned securely to PrivacyGate. You can close this tab; PrivacyGate is importing only the file you selected."
                    if success
                    else "Google did not complete the file selection. You can close this tab and return to PrivacyGate."
                )
            else:
                title = "Drive connection received" if success else "Drive connection not completed"
                text = (
                    "Google returned securely to PrivacyGate. You can close this tab; PrivacyGate is finishing the selected-file connection on this PC."
                    if success
                    else "Google did not complete the Drive connection. You can close this tab and return to PrivacyGate."
                )
            body = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>PrivacyGate — {html.escape(title)}</title><style>*{{box-sizing:border-box}} body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#F7FAFC;color:#062B4F;font-family:Segoe UI,Inter,Arial,sans-serif}}.card{{width:min(560px,calc(100% - 40px));background:#fff;border:1px solid #D7E2EA;border-radius:20px;padding:38px;box-shadow:0 18px 50px rgba(6,43,79,.10)}}.mark{{width:54px;height:54px;border-radius:16px;display:grid;place-items:center;background:#E8F6F6;color:#0B7180;font-size:28px;font-weight:800;margin-bottom:22px}}h1{{margin:0 0 10px;font-size:28px}} p{{margin:0;color:#557184;line-height:1.55;font-size:15px}} .brand{{margin-top:28px;padding-top:20px;border-top:1px solid #E4EBF0;color:#D3A13B;font-size:12px;font-weight:800;letter-spacing:.8px;text-transform:uppercase}}</style></head><body><main class='card'><div class='mark'>{'✓' if success else '!'}</div><h1>{html.escape(title)}</h1><p>{html.escape(text)}</p><div class='brand'>AI PM LAB · PrivacyGate</div></main></body></html>""".encode("utf-8")
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
    redirect_uri = f"http://127.0.0.1:{server.server_port}"

    auth_query = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": DRIVE_FILE_SCOPE,
        "access_type": "offline",
        "prompt": "consent" if trigger_picker else "select_account consent",
        # Explicitly prevent an old broad Drive grant from being folded into the
        # new least-privilege token while the verification migration is tested.
        "include_granted_scopes": "false",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if trigger_picker:
        auth_query["trigger_onepick"] = "true"
        auth_query["mimetypes"] = ",".join(DRIVE_PICKER_MIMETYPES)
    if login_hint.strip():
        auth_query["login_hint"] = login_hint.strip()
    webbrowser.open(f"{AUTH_URL}?{urlencode(auth_query)}")

    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline and not ready.is_set():
            server.handle_request()
    finally:
        server.server_close()

    if not ready.is_set():
        label = "Google Drive Picker" if trigger_picker else "Google Drive connection"
        raise GoogleOAuthError(f"{label} timed out. Try again.")
    if result.get("state") != state:
        raise GoogleOAuthError("Google Drive security check failed (state mismatch).")
    if result.get("error"):
        if trigger_picker and result["error"] == "access_denied":
            return {"picked_file_ids": (), "cancelled": True}
        raise GoogleOAuthError(f"Google Drive authorization was not completed: {result['error']}")

    code = result.get("code", "")
    picked_ids = tuple(
        file_id.strip()
        for file_id in result.get("picked_file_ids", "").split(",")
        if file_id.strip()
    )
    if not code:
        if trigger_picker and not picked_ids:
            return {"picked_file_ids": (), "cancelled": True}
        raise GoogleOAuthError("Google Drive did not return an authorization code.")

    token_data = {
        "client_id": client_id,
        "code": code,
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    secret = _resolved_secret(client_secret)
    if secret:
        token_data["client_secret"] = secret
    response = httpx.post(TOKEN_URL, data=token_data, timeout=20.0)
    if response.status_code >= 400:
        prefix = "Google Drive Picker token exchange failed" if trigger_picker else "Google Drive token exchange failed"
        raise _oauth_error(response, prefix)
    payload = response.json()
    if not payload.get("access_token"):
        raise GoogleOAuthError("Google Drive did not return an access token.")
    payload["obtained_at"] = int(time.time())
    payload["picked_file_ids"] = picked_ids
    return payload


def authorize_drive_file_desktop(
    client_id: str,
    timeout_seconds: int = 180,
    client_secret: str | None = None,
) -> dict:
    """Connect a Drive account with only the non-sensitive ``drive.file`` scope."""
    return _authorize_drive_file_flow(
        client_id,
        timeout_seconds=timeout_seconds,
        client_secret=client_secret,
        trigger_picker=False,
        login_hint="",
    )


def authorize_drive_picker_desktop(
    client_id: str,
    timeout_seconds: int = 180,
    client_secret: str | None = None,
    login_hint: str = "",
) -> dict:
    """Open Google's desktop Picker with least-privilege ``drive.file`` access."""
    return _authorize_drive_file_flow(
        client_id,
        timeout_seconds=timeout_seconds,
        client_secret=client_secret,
        trigger_picker=True,
        login_hint=login_hint,
    )
