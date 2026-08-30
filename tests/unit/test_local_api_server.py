from __future__ import annotations

import json
import re
import threading
from http.client import HTTPConnection

import pytest

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding, PageContent
from ai_pm_lab_privacy_gate.infrastructure.local_api.server import create_local_api_server


TOKEN = "test-local-bridge-token-0123456789"
EMAIL = "jane.smith@example.com"
BROWSER_ORIGIN = "chrome-extension://privacygate-test"


class FakePiiEngine:
    document_language = "en"

    def analyze_page(self, page: PageContent, _profile) -> list[Finding]:
        start = page.text.find(EMAIL)
        if start < 0:
            return []
        end = start + len(EMAIL)
        return [
            Finding(
                finding_id=f"p{page.page_number}-{start}-{end}-0",
                entity_type="EMAIL_ADDRESS",
                text=EMAIL,
                start=start,
                end=end,
                score=0.99,
                page_number=page.page_number,
                context=f"Contact {EMAIL}",
            )
        ]


@pytest.fixture()
def local_api():
    service = PrivacyGateService(pii_engine=FakePiiEngine())
    server = create_local_api_server(
        service,
        port=0,
        auth_token=TOKEN,
        allowed_origins=(BROWSER_ORIGIN,),
    )
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(server, method: str, path: str, payload=None, *, token: str | None = None, origin: str | None = None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    body = None if payload is None else json.dumps(payload)
    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if origin is not None:
        headers["Origin"] = origin
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    raw = response.read().decode("utf-8")
    connection.close()
    return response.status, json.loads(raw) if raw else {}, raw


def test_status_is_local_safe_and_does_not_reveal_token(local_api) -> None:
    status, payload, raw = request(local_api, "GET", "/v1/status")
    assert status == 200
    assert payload["status"] == "ready"
    assert payload["mode"] == "local-only"
    assert payload["returns_restore_mappings"] is False
    assert payload["can_restore_session_text"] is True
    assert TOKEN not in raw


def test_analyze_requires_authentication(local_api) -> None:
    status, payload, _ = request(
        local_api,
        "POST",
        "/v1/analyze",
        {"text": f"Contact {EMAIL}", "profile_key": "property_management", "language": "en"},
    )
    assert status == 401
    assert payload["error"] == "authentication_required"


def test_analyze_returns_coordinates_but_not_original_values(local_api) -> None:
    status, payload, raw = request(
        local_api,
        "POST",
        "/v1/analyze",
        {"text": f"Contact {EMAIL}", "profile_key": "property_management", "language": "en"},
        token=TOKEN,
    )
    assert status == 200
    assert payload["findings_count"] == 1
    finding = payload["findings"][0]
    assert finding["entity_type"] == "EMAIL_ADDRESS"
    assert set(finding) == {"finding_id", "entity_type", "start", "end", "score", "page_number"}
    assert EMAIL not in raw


def test_protect_creates_namespaced_ram_session_and_never_returns_mapping(local_api) -> None:
    status, payload, raw = request(
        local_api,
        "POST",
        "/v1/protect",
        {"text": f"Contact {EMAIL}", "profile_key": "property_management", "language": "en"},
        token=TOKEN,
    )
    assert status == 200
    assert re.fullmatch(r"[a-f0-9]{32}", payload["session_id"])
    assert re.fullmatch(r"Contact \[\[PG_B[A-F0-9]{8}_T0001_EMAIL_ADDRESS_001\]\]", payload["protected_text"])
    assert payload["applied_findings_count"] == 1
    assert payload["entity_types"] == ["EMAIL_ADDRESS"]
    assert "mapping" not in raw.lower()
    assert EMAIL not in raw


def test_restore_returns_original_text_without_exposing_raw_mapping(local_api) -> None:
    _, protected, _ = request(
        local_api,
        "POST",
        "/v1/protect",
        {"text": f"Contact {EMAIL}", "profile_key": "property_management"},
        token=TOKEN,
    )
    status, restored, raw = request(
        local_api,
        "POST",
        "/v1/restore",
        {"session_id": protected["session_id"], "text": f"AI reply: {protected['protected_text']}"},
        token=TOKEN,
    )
    assert status == 200
    assert restored["restored_text"] == f"AI reply: Contact {EMAIL}"
    assert set(restored) == {"restored_text", "session_id"}
    assert "original_text" not in raw
    assert "mappings" not in raw


def test_browser_round_trip_uses_allowlisted_extension_origin_without_bearer(local_api) -> None:
    status, analyzed, raw = request(
        local_api,
        "POST",
        "/v1/browser/analyze",
        {"text": f"Contact {EMAIL}", "profile_key": "property_management", "language": "en"},
        origin=BROWSER_ORIGIN,
    )
    assert status == 200
    assert analyzed["findings_count"] == 1
    assert EMAIL not in raw

    finding_id = analyzed["findings"][0]["finding_id"]
    status, protected, raw = request(
        local_api,
        "POST",
        "/v1/browser/protect",
        {
            "text": f"Contact {EMAIL}",
            "profile_key": "property_management",
            "language": "en",
            "finding_ids": [finding_id],
            "replacement_mode": "reversible",
        },
        origin=BROWSER_ORIGIN,
    )
    assert status == 200
    assert EMAIL not in raw
    assert protected["session_id"]

    status, restored, _ = request(
        local_api,
        "POST",
        "/v1/browser/restore",
        {
            "session_id": protected["session_id"],
            "text": f"AI reply: {protected['protected_text']}",
        },
        origin=BROWSER_ORIGIN,
    )
    assert status == 200
    assert restored["restored_text"] == f"AI reply: Contact {EMAIL}"


def test_browser_restore_requires_allowlisted_extension_origin(local_api) -> None:
    _, protected, _ = request(
        local_api,
        "POST",
        "/v1/protect",
        {"text": f"Contact {EMAIL}", "profile_key": "property_management"},
        token=TOKEN,
    )

    status, payload, _ = request(
        local_api,
        "POST",
        "/v1/browser/restore",
        {"session_id": protected["session_id"], "text": protected["protected_text"]},
    )
    assert status == 403
    assert payload["error"] == "browser_origin_not_allowed"


def test_reusing_session_generates_unique_tokens_per_turn(local_api) -> None:
    _, first, _ = request(
        local_api,
        "POST",
        "/v1/protect",
        {"text": f"First {EMAIL}", "profile_key": "property_management"},
        token=TOKEN,
    )
    _, second, _ = request(
        local_api,
        "POST",
        "/v1/protect",
        {
            "text": f"Second {EMAIL}",
            "profile_key": "property_management",
            "session_id": first["session_id"],
        },
        token=TOKEN,
    )
    assert second["session_id"] == first["session_id"]
    assert "_T0001_" in first["protected_text"]
    assert "_T0002_" in second["protected_text"]
    assert first["protected_text"] != second["protected_text"]


def test_deleted_session_can_no_longer_restore(local_api) -> None:
    _, protected, _ = request(
        local_api,
        "POST",
        "/v1/protect",
        {"text": f"Contact {EMAIL}", "profile_key": "property_management"},
        token=TOKEN,
    )
    session_id = protected["session_id"]
    status, payload, _ = request(
        local_api,
        "DELETE",
        f"/v1/sessions/{session_id}",
        token=TOKEN,
    )
    assert status == 200
    assert payload["status"] == "deleted"
    status, payload, _ = request(
        local_api,
        "POST",
        "/v1/restore",
        {"session_id": session_id, "text": protected["protected_text"]},
        token=TOKEN,
    )
    assert status == 404
    assert payload["error"] == "session_not_found"


def test_browser_origin_is_denied_unless_explicitly_allowed(local_api) -> None:
    status, payload, _ = request(
        local_api,
        "POST",
        "/v1/analyze",
        {"text": f"Contact {EMAIL}", "profile_key": "property_management"},
        token=TOKEN,
        origin="https://evil.example",
    )
    assert status == 403
    assert payload["error"] == "origin_not_allowed"


def test_server_cannot_bind_to_network_interface() -> None:
    with pytest.raises(ValueError, match="bind only"):
        create_local_api_server(host="0.0.0.0", port=0, auth_token=TOKEN)
