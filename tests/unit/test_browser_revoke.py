from __future__ import annotations

import json
import threading
from http.client import HTTPConnection

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_pairing import BrowserPairingRegistry
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_revoke import install_browser_revoke_support
from ai_pm_lab_privacy_gate.infrastructure.local_api.server import create_local_api_server
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore


ORIGIN = "chrome-extension://privacygate-test"


def _request(server, *, token: str | None = None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    headers = {"Origin": ORIGIN}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    connection.request("DELETE", "/v1/browser/pairing", headers=headers)
    response = connection.getresponse()
    raw = response.read().decode("utf-8")
    connection.close()
    return response.status, json.loads(raw) if raw else {}


def _pair(registry: BrowserPairingRegistry, *, now: float, name: str) -> str:
    challenge = registry.create_challenge(now=now)
    return registry.pair(ORIGIN, challenge.code, client_name=name, now=now + 1)


def test_browser_disconnect_revokes_only_calling_credential() -> None:
    registry = BrowserPairingRegistry(MemorySecretStore())
    token_edge = _pair(registry, now=100.0, name="Microsoft Edge")
    token_chrome = _pair(registry, now=200.0, name="Google Chrome")
    server = create_local_api_server(
        PrivacyGateService(),
        port=0,
        auth_token="desktop-main-token-0123456789012345",
        browser_pairing=registry,
    )
    assert install_browser_revoke_support(server) is True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        status, payload = _request(server, token=token_edge)
        assert status == 200
        assert payload == {"revoked": True}
        assert registry.validate(ORIGIN, token_edge) is False
        assert registry.validate(ORIGIN, token_chrome) is True
        assert registry.status().paired_count == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_browser_disconnect_requires_scoped_pairing_token() -> None:
    registry = BrowserPairingRegistry(MemorySecretStore())
    server = create_local_api_server(
        PrivacyGateService(),
        port=0,
        auth_token="desktop-main-token-0123456789012345",
        browser_pairing=registry,
    )
    assert install_browser_revoke_support(server) is True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        status, payload = _request(server)
        assert status == 401
        assert payload["error"] == "browser_pairing_required"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
