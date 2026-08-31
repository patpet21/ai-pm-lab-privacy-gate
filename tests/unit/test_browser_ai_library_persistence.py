from __future__ import annotations

import http.client
import json
import threading

from ai_pm_lab_privacy_gate.domain.models import (
    AnalysisDocument,
    Finding,
    PageContent,
    ProtectionResult,
    ReplacementMapping,
)
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_ai_persistence import (
    install_browser_ai_persistence,
)
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_pairing import BrowserPairingRegistry
from ai_pm_lab_privacy_gate.infrastructure.local_api.server import create_local_api_server
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore
from ai_pm_lab_privacy_gate.infrastructure.storage.ai_library_repository import AiLibraryRepository
from ai_pm_lab_privacy_gate.infrastructure.storage.protected_library import ProtectedLibraryRepository


class _FakePrivacyService:
    def document_from_text(self, text: str) -> AnalysisDocument:
        return AnalysisDocument(
            source_kind="text",
            pages=(PageContent(page_number=1, text=text),),
        )

    def analyze(self, document, _profile, *, language="en"):
        text = document.pages[0].text
        start = text.index("Alice")
        return (
            Finding(
                finding_id="PERSON_001",
                entity_type="PERSON",
                text="Alice",
                start=start,
                end=start + len("Alice"),
                score=0.99,
                page_number=1,
                context="",
            ),
        )

    def protect(self, document, selected, *, replacement_mode="reversible"):
        selected = tuple(selected)
        original = document.pages[0].text
        token = "[[PG_PERSON_001]]"
        protected = original.replace("Alice", token)
        return ProtectionResult(
            protected_pages=(PageContent(page_number=1, text=protected),),
            applied_findings=selected,
            mappings=(
                ReplacementMapping(
                    token=token,
                    entity_type="PERSON",
                    original_text="Alice",
                ),
            ),
            replacement_mode=replacement_mode,
        )

    def restore_text(self, text: str, mappings) -> str:
        restored = text
        for mapping in mappings:
            restored = restored.replace(mapping.token, mapping.original_text)
        return restored


def _paired_registry():
    origin = "chrome-extension://privacygate-test"
    registry = BrowserPairingRegistry(MemorySecretStore())
    challenge = registry.create_challenge()
    token = registry.pair(origin, challenge.code, client_name="test browser")
    return registry, origin, token


def _post(server, origin: str, token: str, path: str, payload: dict[str, object]):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        body = json.dumps(payload)
        connection.request(
            "POST",
            path,
            body=body,
            headers={
                "Origin": origin,
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Content-Length": str(len(body.encode("utf-8"))),
            },
        )
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        return response.status, data
    finally:
        connection.close()


def _serve(server):
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    return thread


def _stop(server, thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_browser_mapping_survives_bridge_restart(tmp_path) -> None:
    repository = AiLibraryRepository(tmp_path)
    registry, origin, token = _paired_registry()

    first = create_local_api_server(
        service=_FakePrivacyService(),
        port=0,
        auth_token="a" * 32,
        browser_pairing=registry,
    )
    assert install_browser_ai_persistence(first, repository) is True
    first_thread = _serve(first)

    status, protected = _post(
        first,
        origin,
        token,
        "/v1/browser/protect",
        {
            "text": "Contact Alice today.",
            "profile_key": "property_management",
            "language": "en",
            "replacement_mode": "reversible",
        },
    )
    assert status == 200
    session_id = protected["session_id"]
    protected_text = protected["protected_text"]
    assert session_id
    assert "Alice" not in protected_text
    assert "[[PG_B" in protected_text

    stored = repository.load_session(session_id)
    assert stored is not None
    assert stored.turn == 1
    assert tuple(mapping.original_text for mapping in stored.mappings) == ("Alice",)
    assert repository.list_conversations(provider="chatgpt")[0].message_count == 1

    # Browser AI history is intentionally absent from the physically separate
    # MCP-readable Protected Library.
    protected_library = ProtectedLibraryRepository(tmp_path / "Protected")
    assert protected_library.list_mcp_documents() == ()

    # Closing the server explicitly destroys the in-memory working set.
    _stop(first, first_thread)

    second = create_local_api_server(
        service=_FakePrivacyService(),
        port=0,
        auth_token="b" * 32,
        browser_pairing=registry,
    )
    assert install_browser_ai_persistence(second, repository) is True
    second_thread = _serve(second)
    try:
        assert second.session_store._sessions == {}
        status, restored = _post(
            second,
            origin,
            token,
            "/v1/browser/restore",
            {
                "text": f"Hello, {protected_text}",
                "session_id": session_id,
            },
        )
        assert status == 200
        assert "Alice" in restored["restored_text"]

        # Rehydration restores the namespace counter too, so a later protected
        # turn cannot reuse T0001 tokens from before the desktop restart.
        status, second_protected = _post(
            second,
            origin,
            token,
            "/v1/browser/protect",
            {
                "text": "Alice again.",
                "profile_key": "property_management",
                "language": "en",
                "replacement_mode": "reversible",
                "session_id": session_id,
            },
        )
        assert status == 200
        assert "_T0002_" in second_protected["protected_text"]
        reloaded = repository.load_session(session_id)
        assert reloaded is not None
        assert reloaded.turn == 2
        assert len(reloaded.mappings) == 2
    finally:
        _stop(second, second_thread)
