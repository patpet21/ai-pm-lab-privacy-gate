from pathlib import Path

import pytest

from ai_pm_lab_privacy_gate.application.google_drive_protect_sources import (
    build_google_drive_protect_package,
    should_use_google_drive_adapter,
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
            (PageContent(1, "Alice in Drive document"),),
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


def _metadata() -> dict[str, object]:
    return {
        "provider": "google_drive",
        "provider_label": "Google Drive",
        "account_id": "account-1",
        "account_label": "user@example.com",
        "item_id": "drive-item-123",
        "item_title": "Client Budget.xlsx",
        "item_kind": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "folder_path": "My Drive/Clients/Acme",
    }


def test_drive_adapter_claims_only_google_drive_provenance():
    assert should_use_google_drive_adapter(_metadata())
    assert not should_use_google_drive_adapter({})
    assert not should_use_google_drive_adapter({"provider": "gmail"})
    assert not should_use_google_drive_adapter({"provider": "local"})


def test_drive_package_preserves_remote_identity_on_document_source(tmp_path):
    metadata = _metadata()
    original = dict(metadata)
    path = tmp_path / "working-copy.xlsx"

    package = build_google_drive_protect_package(
        document_path=str(path),
        source_metadata=metadata,
        source_name="Google Drive • user@example.com • Clients • Acme • Client Budget.xlsx",
    )

    assert package is not None
    assert package.origin == "google_drive"
    assert package.source_count == 1
    assert package.metadata == {"adapter": "google_drive_v1"}

    source = package.sources[0]
    assert source.key == "document"
    assert source.label == "Client Budget.xlsx"
    assert source.path == str(path)
    assert source.metadata["provider"] == "google_drive"
    assert source.metadata["item_id"] == "drive-item-123"
    assert source.metadata["folder_path"] == "My Drive/Clients/Acme"
    assert source.metadata["origin"] == "google_drive"
    assert source.metadata["source_kind"] == "file"
    assert "Clients • Acme" in str(source.metadata["source_name"])
    assert metadata == original


def test_drive_document_and_paste_share_one_generic_session_without_collisions(tmp_path):
    package = build_google_drive_protect_package(
        document_path=str(tmp_path / "drive-file.pdf"),
        pasted_text="Alice in pasted text",
        source_metadata=_metadata(),
    )
    assert package is not None
    assert package.origin == "google_drive_mixed"
    assert [source.key for source in package.sources] == ["document", "text"]
    assert package.sources[1].metadata["origin"] == "paste"

    service = ProtectSessionService(_FakePrivacyService())
    analysis = service.analyze(package, object())
    assert {item.finding_id for item in analysis.findings} == {
        "document::person-1",
        "text::person-1",
    }

    result = service.protect(
        analysis,
        (finding.finding_id for finding in analysis.findings),
    )
    document_result = result.source("document")
    text_result = result.source("text")
    assert document_result is not None
    assert text_result is not None
    assert "[[PG_S1_DOCUMENT_PERSON_001]]" in document_result.result.combined_text
    assert "[[PG_S2_TEXT_PERSON_001]]" in text_result.result.combined_text
    assert service.verify(result, object()) == {"document": (), "text": ()}


def test_drive_package_requires_materialized_file_and_drive_provider(tmp_path):
    assert (
        build_google_drive_protect_package(
            document_path="",
            source_metadata=_metadata(),
        )
        is None
    )

    with pytest.raises(ValueError, match="google_drive provenance"):
        build_google_drive_protect_package(
            document_path=str(tmp_path / "file.pdf"),
            source_metadata={"provider": "gmail"},
        )
