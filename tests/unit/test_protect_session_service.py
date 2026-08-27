from pathlib import Path

from ai_pm_lab_privacy_gate.application.protect_session_service import ProtectSessionService
from ai_pm_lab_privacy_gate.domain.models import (
    AnalysisDocument,
    Finding,
    PageContent,
    ProtectedSpan,
    ProtectionResult,
    ReplacementMapping,
)
from ai_pm_lab_privacy_gate.domain.protect_package import ProtectPackage, ProtectSource


class _FakePrivacyService:
    def document_from_text(self, text: str) -> AnalysisDocument:
        return AnalysisDocument("text", (PageContent(1, text),))

    def document_from_file(self, path: str) -> AnalysisDocument:
        return AnalysisDocument(
            "pdf",
            (PageContent(1, "Alice appears in the attachment"),),
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
                end=start + len("Alice"),
                score=0.99,
                page_number=1,
                context=text,
            ),
        )

    def protect(
        self,
        document: AnalysisDocument,
        findings,
        replacement_mode: str = "reversible",
    ) -> ProtectionResult:
        applied = tuple(findings)
        original = document.pages[0].text
        if not applied:
            return ProtectionResult(
                protected_pages=(PageContent(1, original),),
                replacement_mode=replacement_mode,
            )
        token = "[[PG_PERSON_001]]"
        start = original.index("Alice")
        protected = original.replace("Alice", token, 1)
        return ProtectionResult(
            protected_pages=(PageContent(1, protected),),
            applied_findings=applied,
            mappings=(ReplacementMapping(token, "PERSON", "Alice"),),
            protected_spans=(
                ProtectedSpan(
                    page_number=1,
                    start=start,
                    end=start + len(token),
                    entity_type="PERSON",
                    finding_id=applied[0].finding_id,
                    replacement_text=token,
                ),
            ),
            replacement_mode=replacement_mode,
        )

    def verify_protected(self, _result, _profile) -> tuple[Finding, ...]:
        return ()


def test_generic_session_keeps_n_sources_independent():
    package = ProtectPackage(
        origin="gmail",
        label="Message package",
        sources=(
            ProtectSource.text_source(
                key="gmail_body",
                label="Email body",
                text="Alice appears in the body",
            ),
            ProtectSource.file_source(
                key="gmail_attachment_1",
                label="agreement.pdf",
                path="agreement.pdf",
            ),
        ),
    )
    service = ProtectSessionService(_FakePrivacyService())

    analysis = service.analyze(package, object())

    assert len(analysis.sources) == 2
    assert {item.finding_id for item in analysis.findings} == {
        "gmail_body::person-1",
        "gmail_attachment_1::person-1",
    }

    result = service.protect(
        analysis,
        (finding.finding_id for finding in analysis.findings),
    )

    assert result.source_count == 2
    assert result.applied_findings_count == 2
    body = result.source("gmail_body")
    attachment = result.source("gmail_attachment_1")
    assert body is not None and attachment is not None
    assert "[[PG_S1_GMAIL_BODY_PERSON_001]]" in body.result.combined_text
    assert "[[PG_S2_GMAIL_ATTACHMENT_1_PERSON_001]]" in attachment.result.combined_text
    assert "=== Email body ===" in result.combined_text
    assert "=== agreement.pdf ===" in result.combined_text
    assert service.verify(result, object()) == {
        "gmail_body": (),
        "gmail_attachment_1": (),
    }


def test_session_can_protect_only_selected_source_findings():
    package = ProtectPackage(
        origin="mixed",
        label="Two sources",
        sources=(
            ProtectSource.text_source(key="one", label="One", text="Alice one"),
            ProtectSource.text_source(key="two", label="Two", text="Alice two"),
        ),
    )
    service = ProtectSessionService(_FakePrivacyService())
    analysis = service.analyze(package, object())

    result = service.protect(analysis, ("two::person-1",))

    assert result.source("one").result.applied_findings == ()
    assert len(result.source("two").result.applied_findings) == 1
