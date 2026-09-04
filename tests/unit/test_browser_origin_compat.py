from __future__ import annotations

import json
import threading
from http.client import HTTPConnection

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_origin_compat import (
    install_browser_origin_compat,
)
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_pairing import BrowserPairingRegistry
from ai_pm_lab_privacy_gate.infrastructure.local_api.server import create_local_api_server
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore


TOKEN = "test-local-bridge-token-0123456789"
ORIGIN = "chrome-extension://privacygate-origin-compat"


def _request(server, method: str, path: str, payload=None, *, token=None, origin=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    body = None if payload is None else json.dumps(payload)
    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if origin:
        headers["Origin"] = origin
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    raw = response.read().decode("utf-8")
    connection.close()
    return response.status, json.loads(raw) if raw else {}


def test_paired_browser_token_recovers_origin_when_chromium_omits_origin() -> None:
    pairing = BrowserPairingRegistry(MemorySecretStore())
    server = create_local_api_server(
        PrivacyGateService(),
        port=0,
        auth_token=TOKEN,
        browser_pairing=pairing,
    )
    install_browser_origin_compat(server)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        challenge = pairing.create_challenge()
        status, payload = _request(
            server,
            "POST",
            "/v1/browser/pair",
            {"code": challenge.code, "client_name": "compat-test"},
            origin=ORIGIN,
        )
        assert status == 200
        browser_token = payload["browser_token"]

        # Chromium service-worker fetches may omit Origin after pairing. The valid
        # scoped token is enough to recover only its already-paired extension origin.
        status, payload = _request(
            server,
            "GET",
            "/v1/browser/status",
            token=browser_token,
        )
        assert status == 200
        assert payload["paired"] is True

        # An explicit web Origin must never be replaced by the token-derived origin.
        status, payload = _request(
            server,
            "GET",
            "/v1/browser/status",
            token=browser_token,
            origin="https://evil.example",
        )
        assert status == 403
        assert payload["error"] == "origin_not_allowed"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
