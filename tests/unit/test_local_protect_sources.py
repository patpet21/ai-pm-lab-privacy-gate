from pathlib import Path

from ai_pm_lab_privacy_gate.application.local_protect_sources import (
    build_local_protect_package,
    compatibility_results,
    compatibility_sources,
    should_use_local_adapter,
)
from ai_pm_lab_privacy_gate.application.protect_session_service import ProtectSessionService
from ai_pm_lab_privacy_gate.domain.models import (
    AnalysisDocument,
    Finding,
    PageContent,
    ProtectionResult,
    ReplacementMapping,
)


class _FakePrivacyService:
    def document_from_text(self, text: str) -> AnalysisDocument:
        return AnalysisDocument("text", (PageContent(1, text),))

    def document_from_file(self, path: str) -> AnalysisDocument:
        return AnalysisDocument(
            Path(path).suffix.lstrip(".") or "pdf",
            (PageContent(1, "Alice in uploaded document"),),
            Path(path),
        )

    def analyze(self, document: AnalysisDocument, _profile) -> tuple[Finding, ...]:
        text = document.pages[0].text
        start = text.index("Alice")
        return (
            Finding(
                finding_id="person-1",
                entity_type="PERSON",
                text="Alice",
                start=start,
                end=start + 5,
                score=0.99,
                page_number=1,
                context=text,
            ),
        )

    def protect(self, document, findings, replacement_mode="reversible") -> ProtectionResult:
        findings = tuple(findings)
        original = document.pages[0].text
        if not findings:
            return ProtectionResult(
                protected_pages=(PageContent(1, original),),
                replacement_mode=replacement_mode,
            )
        token = "[[PG_PERSON_001]]"
        return ProtectionResult(
            protected_pages=(PageContent(1, original.replace("Alice", token, 1)),),
            applied_findings=findings,
            mappings=(ReplacementMapping(token, "PERSON", "Alice"),),
            replacement_mode=replacement_mode,
        )

    def verify_protected(self, _result, _profile):
        return ()


def test_local_package_empty_inputs_return_none():
    assert build_local_protect_package() is None


def test_local_upload_builds_one_file_source(tmp_path):
    source = tmp_path / "agreement.pdf"
    package = build_local_protect_package(document_path=str(source))

    assert package is not None
    assert package.origin == "local_upload"
    assert package.source_count == 1
    assert package.sources[0].key == "document"
    assert package.sources[0].label == "agreement.pdf"
    assert package.sources[0].path == str(source)
    assert package.sources[0].metadata["origin"] == "local_upload"


def test_local_paste_builds_one_text_source():
    package = build_local_protect_package(pasted_text="Alice pasted here")

    assert package is not None
    assert package.origin == "paste"
    assert package.source_count == 1
    assert package.sources[0].key == "text"
    assert package.sources[0].label == "Pasted text"
    assert package.sources[0].text == "Alice pasted here"


def test_local_document_and_paste_are_one_ordered_package(tmp_path):
    source = tmp_path / "budget.xlsx"
    package = build_local_protect_package(
        document_path=str(source),
        pasted_text="Alice pasted here",
    )

    assert package is not None
    assert package.origin == "local_mixed"
    assert package.source_count == 2
    assert [item.key for item in package.sources] == ["document", "text"]


def test_local_adapter_does_not_claim_connected_provider_routes():
    assert should_use_local_adapter({})
    assert should_use_local_adapter({"provider": "local"})
    assert not should_use_local_adapter({"provider": "google_drive"})
    assert not should_use_local_adapter({"provider": "gmail"})
    assert not should_use_local_adapter({"provider": "clickup"})


def test_local_package_runs_through_generic_session_service(tmp_path):
    package = build_local_protect_package(
        document_path=str(tmp_path / "agreement.pdf"),
        pasted_text="Alice in pasted text",
    )
    service = ProtectSessionService(_FakePrivacyService())

    analysis = service.analyze(package, object())
    assert {item.finding_id for item in analysis.findings} == {
        "document::person-1",
        "text::person-1",
    }

    compat = compatibility_sources(analysis)
    assert set(compat) == {"document", "text"}
    assert compat["document"]["document"].source_path.name == "agreement.pdf"
    assert compat["text"]["label"] == "Pasted text"

    result = service.protect(
        analysis,
        (finding.finding_id for finding in analysis.findings),
    )
    mirrored = compatibility_results(result)

    assert set(mirrored) == {"document", "text"}
    assert "[[PG_S1_DOCUMENT_PERSON_001]]" in mirrored["document"].combined_text
    assert "[[PG_S2_TEXT_PERSON_001]]" in mirrored["text"].combined_text
    assert service.verify(result, object()) == {"document": (), "text": ()}
