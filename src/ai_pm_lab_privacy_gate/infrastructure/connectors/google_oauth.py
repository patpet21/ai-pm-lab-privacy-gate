from __future__ import annotations

import base64
import ctypes
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

from .google_tls import google_ssl_context


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.readonly",
)
GMAIL_SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
)
_RETURN_SERVER_SECONDS = 90


class GoogleOAuthError(RuntimeError):
    pass


def configured_client_id() -> str:
    return os.environ.get("PRIVACY_GATE_GOOGLE_CLIENT_ID", "").strip()


def configured_client_secret() -> str:
    return os.environ.get("PRIVACY_GATE_GOOGLE_CLIENT_SECRET", "").strip()


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _oauth_error(response: httpx.Response, prefix: str) -> GoogleOAuthError:
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


def _resolved_secret(client_secret: str | None) -> str:
    if client_secret is None:
        return configured_client_secret()
    return client_secret.strip()


def _send_html(handler: BaseHTTPRequestHandler, body: str, *, status: int = 200) -> None:
    encoded = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header(
        "Content-Security-Policy",
        "default-src 'none'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
    )
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)
    handler.wfile.flush()


def _handoff_page(
    *,
    success: bool,
    return_url: str,
    status_title: str,
    status_text: str,
) -> str:
    safe_title = html.escape(status_title)
    safe_text = html.escape(status_text)
    safe_return = html.escape(return_url, quote=True)
    mark = "✓" if success else "!"
    badge = "SECURE GOOGLE HANDOFF" if success else "GOOGLE HANDOFF"
    mark_bg = "#E7F5F4" if success else "#FFF3E3"
    mark_color = "#087A7E" if success else "#A96005"
    note = (
        "PrivacyGate is reopening automatically. If your browser stays in front, "
        "use the button below."
        if success
        else "Return to PrivacyGate to review the connection and try again."
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PrivacyGate — {safe_title}</title>
<style>
*{{box-sizing:border-box}}:root{{color-scheme:light}}
body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:28px;background:radial-gradient(circle at 20% 10%,rgba(11,113,128,.08),transparent 34%),linear-gradient(145deg,#F7FAFC,#EDF3F6);color:#062B4F;font-family:"Segoe UI",Inter,Arial,sans-serif}}
.card{{width:min(650px,100%);overflow:hidden;background:#fff;border:1px solid #D8E3EA;border-radius:24px;box-shadow:0 24px 65px rgba(6,43,79,.14)}}.accent{{height:5px;background:linear-gradient(90deg,#062B4F,#0B7180 62%,#3BA7AD)}}.content{{padding:34px 38px 30px}}
.brandrow,.footer,.actions{{display:flex;align-items:center;gap:14px;flex-wrap:wrap}}.brandrow{{justify-content:space-between;margin-bottom:30px}}.brand{{display:flex;align-items:center;gap:12px;font-size:17px;font-weight:850}}.logo{{width:42px;height:42px;display:grid;place-items:center;border-radius:12px;background:#062B4F;color:#fff;font-weight:900;box-shadow:0 7px 16px rgba(6,43,79,.16)}}.badge{{border:1px solid #C9DDE1;background:#F2F9F9;color:#0B7180;border-radius:999px;padding:7px 10px;font-size:10px;font-weight:850;letter-spacing:.9px}}
.status{{display:flex;gap:18px;align-items:flex-start}}.mark{{flex:0 0 54px;width:54px;height:54px;display:grid;place-items:center;border-radius:16px;background:{mark_bg};color:{mark_color};font-size:28px;font-weight:900}}h1{{margin:2px 0 8px;font-size:29px;line-height:1.18;letter-spacing:-.55px}}p{{margin:0;color:#506D80;font-size:15px;line-height:1.58}}
.notice{{margin-top:25px;padding:14px 16px;border:1px solid #E0E8ED;border-radius:12px;background:#F8FAFB;color:#557184;font-size:13px;line-height:1.5}}.actions{{margin-top:22px}}.primary{{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 18px;border-radius:10px;background:#0B7180;color:#fff;text-decoration:none;font-size:14px;font-weight:850;box-shadow:0 7px 16px rgba(11,113,128,.18)}}.primary:hover{{background:#096674}}.hint{{color:#718796;font-size:12px}}
.footer{{justify-content:space-between;margin-top:28px;padding-top:19px;border-top:1px solid #E5EBEF;color:#7C909D;font-size:11px}}.footer strong{{color:#D39A2F;letter-spacing:.65px}}@media(max-width:560px){{.content{{padding:27px 23px 24px}}.brandrow{{align-items:flex-start;flex-direction:column}}h1{{font-size:25px}}}}
</style></head><body><main class="card"><div class="accent"></div><div class="content">
<div class="brandrow"><div class="brand"><div class="logo">PG</div>PrivacyGate</div><div class="badge">{html.escape(badge)}</div></div>
<div class="status"><div class="mark">{mark}</div><div><h1>{safe_title}</h1><p>{safe_text}</p></div></div>
<div class="notice">{html.escape(note)}</div><div class="actions"><a class="primary" href="{safe_return}">Return to PrivacyGate</a><span class="hint">You can safely close this tab afterwards.</span></div>
<div class="footer"><strong>AI PM LAB · PRIVACYGATE</strong><span>Local-first privacy protection</span></div>
</div></main></body></html>"""


def _returned_to_app_page() -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PrivacyGate — Returned to app</title><style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:28px;background:#F3F7F9;color:#062B4F;font-family:"Segoe UI",Inter,Arial,sans-serif}.card{width:min(520px,100%);background:#fff;border:1px solid #D8E3EA;border-radius:22px;padding:34px;box-shadow:0 20px 55px rgba(6,43,79,.12)}.mark{width:50px;height:50px;display:grid;place-items:center;border-radius:15px;background:#E7F5F4;color:#087A7E;font-size:25px;font-weight:900;margin-bottom:18px}h1{margin:0 0 9px;font-size:26px}p{margin:0;color:#557184;line-height:1.55;font-size:14px}.brand{margin-top:24px;padding-top:17px;border-top:1px solid #E5EBEF;color:#D39A2F;font-size:11px;font-weight:850;letter-spacing:.65px}
</style></head><body><main class="card"><div class="mark">✓</div><h1>PrivacyGate is reopening</h1><p>The desktop app has been asked to return to the foreground. You can close this tab.</p><div class="brand">AI PM LAB · PRIVACYGATE</div></main></body></html>"""


def _win32_api():
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetLastActivePopup.argtypes = [wintypes.HWND]
    user32.GetLastActivePopup.restype = wintypes.HWND
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetActiveWindow.argtypes = [wintypes.HWND]
    user32.SetFocus.argtypes = [wintypes.HWND]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.AttachThreadInput.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.BOOL,
    ]
    user32.AttachThreadInput.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    kernel32.GetCurrentProcessId.restype = wintypes.DWORD
    return user32, kernel32, wintypes


def _native_privacygate_windows() -> tuple[int, int]:
    """Find this process' main window and its last active popup on Windows."""
    if os.name != "nt":
        return 0, 0
    try:
        user32, kernel32, wintypes = _win32_api()
        process_id = int(kernel32.GetCurrentProcessId())
        candidates: list[tuple[int, int, int]] = []
        enum_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        @enum_type
        def collect(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            owner_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
            if owner_pid.value != process_id:
                return True
            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True
            area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
            owner = int(user32.GetWindow(hwnd, 4) or 0)  # GW_OWNER
            candidates.append((int(hwnd), area, owner))
            return True

        user32.EnumWindows(collect, 0)
        if not candidates:
            return 0, 0
        ownerless = [row for row in candidates if row[2] == 0]
        main = max(ownerless or candidates, key=lambda row: row[1])[0]
        target = int(user32.GetLastActivePopup(main) or main)
        return main, target if user32.IsWindowVisible(target) else main
    except Exception:
        return 0, 0


def _activate_privacygate_native_once() -> None:
    """Reclaim Windows foreground focus without calling Qt from the HTTP thread."""
    if os.name != "nt":
        return
    try:
        user32, kernel32, wintypes = _win32_api()
        main, target = _native_privacygate_windows()
        if not main:
            return

        foreground = int(user32.GetForegroundWindow() or 0)
        current_thread = int(kernel32.GetCurrentThreadId())
        foreground_thread = (
            int(user32.GetWindowThreadProcessId(foreground, None))
            if foreground
            else 0
        )
        target_thread = int(user32.GetWindowThreadProcessId(target, None))
        attached: list[int] = []
        for thread_id in {foreground_thread, target_thread}:
            if (
                thread_id
                and thread_id != current_thread
                and user32.AttachThreadInput(current_thread, thread_id, True)
            ):
                attached.append(thread_id)

        try:
            main_hwnd = wintypes.HWND(main)
            target_hwnd = wintypes.HWND(target)
            user32.ShowWindowAsync(main_hwnd, 3)  # SW_MAXIMIZE
            user32.ShowWindow(main_hwnd, 3)
            if target != main:
                user32.ShowWindowAsync(target_hwnd, 9)  # SW_RESTORE
                user32.ShowWindow(target_hwnd, 9)

            # Chrome/Edge can keep Windows' foreground lock briefly after OAuth.
            # Sharing the input queue plus an Alt transition makes the explicit
            # browser -> desktop handoff substantially more reliable.
            user32.keybd_event(0x12, 0, 0, 0)  # VK_MENU / Alt
            user32.keybd_event(0x12, 0, 0x0002, 0)  # KEYEVENTF_KEYUP
            flags = 0x0002 | 0x0001 | 0x0040
            user32.BringWindowToTop(main_hwnd)
            user32.BringWindowToTop(target_hwnd)
            user32.SetWindowPos(target_hwnd, wintypes.HWND(-1), 0, 0, 0, 0, flags)
            user32.SetWindowPos(target_hwnd, wintypes.HWND(-2), 0, 0, 0, 0, flags)
            user32.SetForegroundWindow(target_hwnd)
            user32.SetActiveWindow(target_hwnd)
            user32.SetFocus(target_hwnd)
        finally:
            for thread_id in reversed(attached):
                user32.AttachThreadInput(current_thread, thread_id, False)
    except Exception:
        return


def _request_privacygate_foreground() -> None:
    _activate_privacygate_native_once()
    for delay in (0.18, 0.55, 1.05):
        timer = threading.Timer(delay, _activate_privacygate_native_once)
        timer.daemon = True
        timer.start()


def _shutdown_server(server: HTTPServer) -> None:
    try:
        server.shutdown()
    except Exception:
        pass
    try:
        server.server_close()
    except Exception:
        pass


def authorize_desktop(
    client_id: str,
    timeout_seconds: int = 180,
    scopes: tuple[str, ...] | None = None,
    client_secret: str | None = None,
    *,
    include_granted_scopes: bool = True,
    login_hint: str = "",
    extra_auth_parameters: dict[str, str] | None = None,
) -> dict:
    """Run Google's installed-app OAuth flow with PKCE and a loopback callback.

    ``client_secret`` is optional because native/desktop OAuth clients are public
    clients. Some existing PrivacyGate Google credentials, however, were created
    from a client configuration whose token endpoint requires the matching
    secret. Callers may therefore provide the locally encrypted app credential
    without coupling it to an individual connected account.
    """
    client_id = client_id.strip()
    if not client_id:
        raise GoogleOAuthError("Google OAuth client ID is not configured for this build.")
    requested_scopes = scopes or DRIVE_SCOPES

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)
    result: dict[str, str] = {}
    ready = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/return-to-app":
                _request_privacygate_foreground()
                _send_html(self, _returned_to_app_page())
                return
            if parsed.path not in {"", "/"}:
                self.send_error(404)
                return

            query = parse_qs(parsed.query)
            returned = {
                "code": query.get("code", [""])[0],
                "state": query.get("state", [""])[0],
                "error": query.get("error", [""])[0],
                "picked_file_ids": query.get("picked_file_ids", [""])[0],
            }
            if not ready.is_set():
                result.update(returned)

            success = (
                bool(returned.get("code"))
                and not returned.get("error")
                and returned.get("state") == state
            )
            title = "Connection received" if success else "Connection not completed"
            text = (
                "Google returned securely to PrivacyGate. Your connection is being "
                "finished locally on this PC."
                if success
                else "Google did not complete the authorization. Return to PrivacyGate "
                "to review the connection and try again."
            )
            origin = f"http://127.0.0.1:{self.server.server_port}"
            _send_html(
                self,
                _handoff_page(
                    success=success,
                    return_url=f"{origin}/return-to-app",
                    status_title=title,
                    status_text=text,
                ),
            )
            if not ready.is_set():
                ready.set()
                if success:
                    _request_privacygate_foreground()

        def log_message(self, _format, *_args):
            return

    server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}"
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    auth_parameters = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(requested_scopes),
        "access_type": "offline",
        "prompt": "select_account consent",
        "include_granted_scopes": "true" if include_granted_scopes else "false",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if login_hint.strip():
        auth_parameters["login_hint"] = login_hint.strip()
    if extra_auth_parameters:
        auth_parameters.update(
            {str(key): str(value) for key, value in extra_auth_parameters.items()}
        )
    webbrowser.open(f"{AUTH_URL}?{urlencode(auth_parameters)}")

    if not ready.wait(timeout_seconds):
        _shutdown_server(server)
        raise GoogleOAuthError("Google sign-in timed out. Try Connect again.")

    # Keep localhost alive briefly so the callback page's explicit fallback
    # button still works after the OAuth token exchange has started.
    shutdown_timer = threading.Timer(
        _RETURN_SERVER_SECONDS,
        lambda current_server=server: _shutdown_server(current_server),
    )
    shutdown_timer.daemon = True
    shutdown_timer.start()

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
    secret = _resolved_secret(client_secret)
    if secret:
        token_data["client_secret"] = secret
    response = httpx.post(
        TOKEN_URL,
        data=token_data,
        timeout=20.0,
        verify=google_ssl_context(),
    )
    if response.status_code >= 400:
        raise _oauth_error(response, "Google token exchange failed")
    payload = response.json()
    if not payload.get("access_token"):
        raise GoogleOAuthError("Google did not return an access token.")
    payload["obtained_at"] = int(time.time())
    payload["picked_file_ids"] = result.get("picked_file_ids", "")
    return payload


def refresh_access_token(
    client_id: str,
    refresh_token: str,
    client_secret: str | None = None,
) -> dict:
    if not client_id or not refresh_token:
        raise GoogleOAuthError(
            "Google connection cannot be refreshed because local OAuth credentials are incomplete."
        )
    token_data = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    secret = _resolved_secret(client_secret)
    if secret:
        token_data["client_secret"] = secret
    response = httpx.post(
        TOKEN_URL,
        data=token_data,
        timeout=20.0,
        verify=google_ssl_context(),
    )
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
