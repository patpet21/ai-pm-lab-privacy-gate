from __future__ import annotations

import base64
import json
import threading
from http.client import HTTPConnection

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_file_v2 import (
    install_browser_file_support_v2,
)
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_pairing import BrowserPairingRegistry
from ai_pm_lab_privacy_gate.infrastructure.local_api.server import create_local_api_server
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore


ORIGIN = "chrome-extension://privacygate-concurrency-test"
AUTH_TOKEN = "test-local-concurrency-auth-token-0123456789"


class ConcurrentFakeExecutor:
    def __init__(self) -> None:
        self.barrier = threading.Barrier(2, timeout=3)

    def warm_async(self) -> None:
        return

    def close(self) -> None:
        return

    def execute(self, request):
        if request.get("operation") != "analyze":
            raise AssertionError("unexpected operation")
        self.barrier.wait()
        return {
            "source_kind": "txt",
            "findings": [],
            "internal_findings": [],
            "worker_pid": 999,
        }


def _request(server, path: str, payload: dict, *, token: str | None = None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    headers = {"Content-Type": "application/json", "Origin": ORIGIN}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    connection.request("POST", path, body=json.dumps(payload), headers=headers)
    response = connection.getresponse()
    raw = response.read().decode("utf-8")
    connection.close()
    return response.status, json.loads(raw) if raw else {}


def _pair(server) -> str:
    challenge = server.browser_pairing.create_challenge()
    status, payload = _request(
        server,
        "/v1/browser/pair",
        {"code": challenge.code, "client_name": "concurrency-test"},
    )
    assert status == 200
    return payload["browser_token"]


def test_two_browser_file_analyses_are_not_globally_locked() -> None:
    pairing = BrowserPairingRegistry(MemorySecretStore())
    server = create_local_api_server(
        PrivacyGateService(),
        port=0,
        auth_token=AUTH_TOKEN,
        browser_pairing=pairing,
    )
    executor = ConcurrentFakeExecutor()
    assert install_browser_file_support_v2(server, executor=executor)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    try:
        token = _pair(server)
        results = []
        errors = []

        def call(name: str) -> None:
            try:
                results.append(
                    _request(
                        server,
                        "/v1/browser/file/analyze",
                        {
                            "filename": name,
                            "file_base64": base64.b64encode(b"hello").decode("ascii"),
                            "profile_key": "general_business",
                            "language": "en",
                        },
                        token=token,
                    )
                )
            except Exception as error:  # pragma: no cover - assertion reports detail
                errors.append(error)

        first = threading.Thread(target=call, args=("first.txt",))
        second = threading.Thread(target=call, args=("second.txt",))
        first.start()
        second.start()
        first.join(timeout=5)
        second.join(timeout=5)

        assert not errors
        assert len(results) == 2
        assert sorted(status for status, _payload in results) == [200, 200]
        assert all(payload.get("isolated_worker") is True for _status, payload in results)
        assert all(payload.get("findings_count") == 0 for _status, payload in results)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
