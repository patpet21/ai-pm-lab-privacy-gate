from __future__ import annotations

import base64
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .provider_oauth import ProviderOAuthError, _callback_page, _run_code_flow


def connect_monday() -> dict:
    return _run_code_flow(
        auth_url="https://auth.monday.com/oauth2/authorize",
        token_url="https://auth.monday.com/oauth2/token",
        client_id=os.environ.get("PRIVACY_GATE_MONDAY_CLIENT_ID", "").strip(),
        client_secret=os.environ.get("PRIVACY_GATE_MONDAY_CLIENT_SECRET", "").strip(),
        redirect_uri=os.environ.get("PRIVACY_GATE_MONDAY_REDIRECT_URI", "http://127.0.0.1:8771/monday").strip(),
    )


def connect_notion() -> dict:
    client_id = os.environ.get("PRIVACY_GATE_NOTION_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PRIVACY_GATE_NOTION_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get("PRIVACY_GATE_NOTION_REDIRECT_URI", "http://127.0.0.1:8770/notion").strip()
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
    params = {
        "client_id": client_id,
        "response_type": "code",
        "owner": "user",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    webbrowser.open(f"https://api.notion.com/v1/oauth/authorize?{urlencode(params)}")
    deadline = time.monotonic() + 180
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
        raise ProviderOAuthError("Notion did not return an authorization code.")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    response = httpx.post(
        "https://api.notion.com/v1/oauth/token",
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/json"},
        json={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        timeout=25.0,
    )
    if response.status_code >= 400:
        raise ProviderOAuthError(f"Notion token exchange failed (HTTP {response.status_code}).")
    payload = response.json()
    if not payload.get("access_token"):
        raise ProviderOAuthError("Notion did not return an access token.")
    payload["obtained_at"] = int(time.time())
    return payload


def connect_jira() -> dict:
    """Connect Jira Cloud using Atlassian OAuth 2.0 (3LO).

    Atlassian redirects to the registered HTTPS PrivacyGate callback. The static
    Netlify relay forwards the short-lived authorization response to a local
    loopback listener on this device, while token exchange and storage stay in
    the desktop app.
    """
    client_id = os.environ.get("PRIVACY_GATE_JIRA_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PRIVACY_GATE_JIRA_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get(
        "PRIVACY_GATE_JIRA_REDIRECT_URI",
        "https://privacygate.propertydex.xyz/oauth/jira/callback",
    ).strip()
    if not client_id or not client_secret:
        raise ProviderOAuthError("OAuth client ID/secret is not configured for this provider.")
    parsed_redirect = urlparse(redirect_uri)
    if parsed_redirect.scheme != "https" or not parsed_redirect.netloc:
        raise ProviderOAuthError("Jira redirect URI must be the registered HTTPS PrivacyGate callback URL.")

    state = secrets.token_urlsafe(28)
    result: dict[str, str] = {}
    ready = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/jira":
                self.send_response(404)
                self.end_headers()
                return
            query = parse_qs(parsed.query)
            result["code"] = query.get("code", [""])[0]
            result["state"] = query.get("state", [""])[0]
            result["error"] = query.get("error", [""])[0]
            body = _callback_page("Jira connection received")
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
        server = HTTPServer(("127.0.0.1", 8772), Handler)
    except OSError as exc:
        raise ProviderOAuthError(
            "PrivacyGate could not open its local Jira callback on port 8772. Close any other PrivacyGate test window and try again."
        ) from exc
    server.timeout = 0.5

    scopes = os.environ.get(
        "PRIVACY_GATE_JIRA_SCOPES",
        "read:jira-work read:jira-user offline_access",
    ).strip()
    params = {
        "audience": "api.atlassian.com",
        "client_id": client_id,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    webbrowser.open(f"https://auth.atlassian.com/authorize?{urlencode(params)}")

    deadline = time.monotonic() + 180
    try:
        while time.monotonic() < deadline and not ready.is_set():
            server.handle_request()
    finally:
        server.server_close()
    if not ready.is_set():
        raise ProviderOAuthError(
            "Jira sign-in timed out. Keep PrivacyGate open while approving access in the browser and try Connect again."
        )
    if result.get("state") != state:
        raise ProviderOAuthError("OAuth security check failed (state mismatch).")
    if result.get("error"):
        raise ProviderOAuthError(f"Authorization was not completed: {result['error']}")
    code = result.get("code", "")
    if not code:
        raise ProviderOAuthError("Jira did not return an authorization code to PrivacyGate.")

    response = httpx.post(
        "https://auth.atlassian.com/oauth/token",
        headers={"Content-Type": "application/json"},
        json={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=25.0,
    )
    if response.status_code >= 400:
        detail = ""
        try:
            error_payload = response.json()
            detail = str(error_payload.get("error_description") or error_payload.get("error") or "")
        except Exception:
            pass
        raise ProviderOAuthError(
            f"Jira token exchange failed (HTTP {response.status_code})" + (f" — {detail}" if detail else "")
        )
    payload = response.json()
    if not payload.get("access_token"):
        raise ProviderOAuthError("Jira did not return an access token.")
    payload["obtained_at"] = int(time.time())
    return payload
