from __future__ import annotations

import base64
import http.client
import json
import threading
from pathlib import Path

from ai_pm_lab_privacy_gate.domain.models import (
    AnalysisDocument,
    Finding,
    PageContent,
    ProtectionResult,
    ReplacementMapping,
)
from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_ai_persistence import (
    install_browser_ai_persistence,
)
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_pairing import BrowserPairingRegistry
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_pdf import install_browser_pdf_support
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_pdf_integrity import (
    _count_occurrences,
    install_browser_pdf_integrity,
)
from ai_pm_lab_privacy_gate.infrastructure.local_api.server import create_local_api_server
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore
from ai_pm_lab_privacy_gate.infrastructure.storage.ai_library_repository import AiLibraryRepository


class _Service:
    def __init__(self, *, leak_output: bool = False) -> None:
        self.pdf = PdfDocumentService()
        self.leak_output = leak_output

    def document_from_pdf(self, path: str | Path) -> AnalysisDocument:
        return self.pdf.extract(path)

    def analyze(self, document, _profile, *, language="en"):  # noqa: ARG002
        text = document.pages[0].text
        start = text.index("Alice")
        # Deliberately select only the first Alice. The second identical value is
        # unselected and must be allowed to remain in the generated PDF.
        return (
            Finding(
                finding_id="PERSON_001",
                entity_type="PERSON",
                text="Alice",
                start=start,
                end=start + 5,
                score=0.99,
                page_number=1,
                context=text,
            ),
        )

    def protect(self, document, selected, *, replacement_mode="reversible"):
        selected = tuple(selected)
        page = document.pages[0]
        finding = selected[0]
        token = "[[PG_PERSON_001]]"
        protected = page.text[: finding.start] + token + page.text[finding.end :]
        return ProtectionResult(
            protected_pages=(PageContent(1, protected),),
            applied_findings=selected,
            mappings=(ReplacementMapping(token, "PERSON", "Alice"),),
            replacement_mode=replacement_mode,
        )

    def save_protected_pdf(self, result, path, source_document=None):  # noqa: ARG002
        text = result.protected_pages[0].text
        if self.leak_output:
            # Simulate a real post-protection leak after the result has already
            # been namespaced. Replacing a hard-coded pre-namespace token would
            # not create a leak and would make this regression test meaningless.
            text = "Tenant Alice. Public alias Alice remains visible."
        return self.pdf.write_protected((PageContent(1, text),), path)

    @staticmethod
    def restore_text(text: str, mappings) -> str:
        restored = text
        for mapping in mappings:
            restored = restored.replace(mapping.token, mapping.original_text)
        return restored


def _paired_registry():
    origin = "chrome-extension://privacygate-integrity-test"
    registry = BrowserPairingRegistry(MemorySecretStore())
    challenge = registry.create_challenge()
    token = registry.pair(origin, challenge.code, client_name="Integrity test")
    return registry, origin, token


def _post(server, origin: str, token: str, path: str, payload: dict[str, object]):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
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
        return response.status, json.loads(response.read().decode("utf-8"))
    finally:
        connection.close()


def _exercise(tmp_path: Path, *, leak_output: bool):
    source = tmp_path / ("leak.pdf" if leak_output else "safe.pdf")
    PdfDocumentService().write_protected(
        (PageContent(1, "Tenant Alice. Public alias Alice remains visible."),),
        source,
    )
    registry, origin, token = _paired_registry()
    repository = AiLibraryRepository(tmp_path / ("library-leak" if leak_output else "library-safe"))
    server = create_local_api_server(
        service=_Service(leak_output=leak_output),
        port=0,
        auth_token="i" * 32,
        browser_pairing=registry,
    )
    assert install_browser_ai_persistence(server, repository) is True
    assert install_browser_pdf_support(server) is True
    assert install_browser_pdf_integrity(server) is True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        status, analyzed = _post(
            server,
            origin,
            token,
            "/v1/browser/pdf/analyze",
            {
                "filename": source.name,
                "file_base64": base64.b64encode(source.read_bytes()).decode("ascii"),
                "profile_key": "property_management",
                "language": "en",
            },
        )
        assert status == 200
        return _post(
            server,
            origin,
            token,
            "/v1/browser/pdf/protect",
            {
                "analysis_id": analyzed["analysis_id"],
                "finding_ids": [analyzed["findings"][0]["finding_id"]],
                "session_id": None,
            },
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_integrity_occurrence_match_does_not_use_raw_substrings() -> None:
    assert _count_occurrences("PrivacyGate protects AI locally", "AI") == 1
    assert _count_occurrences("PrivacyGate", "AI") == 0
    assert _count_occurrences("Alice and Alice", "Alice") == 2


def test_integrity_gate_allows_identical_unselected_occurrence(tmp_path: Path) -> None:
    status, protected = _exercise(tmp_path, leak_output=False)
    assert status == 200
    assert protected["integrity_verified"] is True
    assert protected["integrity_checked_findings"] == 1


def test_integrity_gate_blocks_selected_occurrence_that_survives(tmp_path: Path) -> None:
    status, blocked = _exercise(tmp_path, leak_output=True)
    assert status == 422
    assert blocked["error"] == "pdf_integrity_failed"
    assert "integrity check failed" in blocked["message"].lower()
