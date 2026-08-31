from __future__ import annotations

import base64
import http.client
import json
import threading
from pathlib import Path

from pypdf import PdfReader

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
from ai_pm_lab_privacy_gate.infrastructure.local_api.server import create_local_api_server
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore
from ai_pm_lab_privacy_gate.infrastructure.storage.ai_library_repository import AiLibraryRepository


class _FakePdfPrivacyService:
    def __init__(self) -> None:
        self.pdf = PdfDocumentService()

    def document_from_pdf(self, path: str | Path) -> AnalysisDocument:
        return self.pdf.extract(path)

    def analyze(self, document, _profile, *, language="en"):  # noqa: ARG002
        if not document.has_text:
            raise ValueError(
                "No selectable text was found. Scanned/image-only PDFs are not supported in this build."
            )
        findings: list[Finding] = []
        for page in document.pages:
            cursor = 0
            while True:
                start = page.text.find("Alice", cursor)
                if start < 0:
                    break
                findings.append(
                    Finding(
                        finding_id=f"PERSON_{len(findings) + 1:03d}",
                        entity_type="PERSON",
                        text="Alice",
                        start=start,
                        end=start + len("Alice"),
                        score=0.99,
                        page_number=page.page_number,
                        context="",
                    )
                )
                cursor = start + len("Alice")
        return tuple(findings)

    def protect(self, document, selected, *, replacement_mode="reversible"):
        selected = tuple(selected)
        by_page: dict[int, list[Finding]] = {}
        mappings: list[ReplacementMapping] = []
        for finding in selected:
            by_page.setdefault(finding.page_number, []).append(finding)
            mappings.append(
                ReplacementMapping(
                    token="[[PG_PERSON_001]]",
                    entity_type="PERSON",
                    original_text=finding.text,
                )
            )

        pages: list[PageContent] = []
        for page in document.pages:
            text = page.text
            for finding in sorted(
                by_page.get(page.page_number, ()), key=lambda item: item.start, reverse=True
            ):
                text = text[: finding.start] + "[[PG_PERSON_001]]" + text[finding.end :]
            pages.append(PageContent(page.page_number, text, page.location))

        return ProtectionResult(
            protected_pages=tuple(pages),
            applied_findings=selected,
            mappings=tuple(mappings[:1]),
            replacement_mode=replacement_mode,
        )

    def save_protected_pdf(self, result, path, source_document=None):  # noqa: ARG002
        return self.pdf.write_protected(result.protected_pages, path)

    @staticmethod
    def restore_text(text: str, mappings) -> str:
        restored = text
        for mapping in mappings:
            restored = restored.replace(mapping.token, mapping.original_text)
        return restored


def _paired_registry():
    origin = "chrome-extension://privacygate-pdf-test"
    registry = BrowserPairingRegistry(MemorySecretStore())
    challenge = registry.create_challenge()
    token = registry.pair(origin, challenge.code, client_name="PDF test browser")
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


def test_browser_pdf_is_scanned_protected_and_persisted_locally(tmp_path: Path) -> None:
    pdf = PdfDocumentService()
    source = tmp_path / "tenant.pdf"
    pdf.write_protected(
        (PageContent(1, "Tenant Alice\nCase notes remain local."),),
        source,
    )

    repository = AiLibraryRepository(tmp_path / "library")
    registry, origin, token = _paired_registry()
    server = create_local_api_server(
        service=_FakePdfPrivacyService(),
        port=0,
        auth_token="p" * 32,
        browser_pairing=registry,
    )
    assert install_browser_ai_persistence(server, repository) is True
    assert install_browser_pdf_support(server) is True
    thread = _serve(server)

    try:
        status, analyzed = _post(
            server,
            origin,
            token,
            "/v1/browser/pdf/analyze",
            {
                "filename": "tenant.pdf",
                "file_base64": base64.b64encode(source.read_bytes()).decode("ascii"),
                "profile_key": "property_management",
                "language": "en",
            },
        )
        assert status == 200
        assert analyzed["requires_protection"] is True
        assert analyzed["findings_count"] == 1
        assert analyzed["findings"][0]["entity_type"] == "PERSON"
        assert analyzed["findings"][0]["page_number"] == 1

        status, protected = _post(
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
        assert status == 200
        assert protected["protected_filename"] == "tenant_PrivacyGate.pdf"
        assert protected["applied_findings_count"] == 1
        session_id = protected["session_id"]
        assert isinstance(session_id, str) and len(session_id) == 32

        output = tmp_path / "browser-protected.pdf"
        output.write_bytes(base64.b64decode(protected["protected_file_base64"]))
        output_text = "\n".join(
            page.extract_text() or "" for page in PdfReader(str(output)).pages
        )
        assert "Alice" not in output_text
        assert "[[PG_B" in output_text
        assert "_T0001_PERSON_001]]" in output_text

        snapshot = repository.load_session(session_id)
        assert snapshot is not None
        assert snapshot.turn == 1
        assert tuple(mapping.original_text for mapping in snapshot.mappings) == ("Alice",)

        placeholder = snapshot.mappings[0].token
        status, restored = _post(
            server,
            origin,
            token,
            "/v1/browser/restore",
            {"text": f"The tenant is {placeholder}.", "session_id": session_id},
        )
        assert status == 200
        assert restored["restored_text"] == "The tenant is Alice."
    finally:
        _stop(server, thread)
