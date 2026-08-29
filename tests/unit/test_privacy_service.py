from pathlib import Path

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, Finding, PageContent
from ai_pm_lab_privacy_gate.domain.profiles import get_profile


class FakePiiEngine:
    def analyze_page(self, page, profile):
        start = page.text.index("Jane Smith")
        return [
            Finding(
                finding_id="p1-person",
                entity_type="PERSON",
                text="Jane Smith",
                start=start,
                end=start + len("Jane Smith"),
                score=0.99,
                page_number=page.page_number,
                context=page.text,
            )
        ]

    def protect_text(self, text, findings):
        for finding in sorted(findings, key=lambda item: item.start, reverse=True):
            text = text[: finding.start] + f"<{finding.entity_type}>" + text[finding.end :]
        return text


class FakeResidualEngine:
    def analyze_page(self, page, profile):
        marker = "jane@example.com"
        if marker not in page.text:
            return []
        start = page.text.index(marker)
        return [
            Finding(
                finding_id=f"email-{start}",
                entity_type="EMAIL_ADDRESS",
                text=marker,
                start=start,
                end=start + len(marker),
                score=1.0,
                page_number=page.page_number,
                context=page.text,
            )
        ]


def test_text_analysis_and_selective_protection(tmp_path: Path):
    service = PrivacyGateService(pii_engine=FakePiiEngine())
    document = service.document_from_text("Tenant Jane Smith called today.")
    findings = service.analyze(document, get_profile("property_management"))
    result = service.protect(document, findings)
    assert len(findings) == 1
    assert result.combined_text == "Tenant [[PG_PERSON_001]] called today."

    output = service.save_protected_text(result, tmp_path / "protected.txt")
    assert output.read_text(encoding="utf-8") == result.combined_text


def test_language_switch_uses_lazy_cached_engine(monkeypatch):
    import ai_pm_lab_privacy_gate.application.privacy_service as privacy_module

    created: list[str] = []

    class LanguageEngine:
        def __init__(self, language: str = "en") -> None:
            self.document_language = language
            created.append(language)

        def analyze_page(self, page, profile):
            marker = "Mario Rossi"
            start = page.text.index(marker)
            return [
                Finding(
                    finding_id=f"{self.document_language}-{start}",
                    entity_type="PERSON",
                    text=marker,
                    start=start,
                    end=start + len(marker),
                    score=0.99,
                    page_number=page.page_number,
                    context=page.text,
                )
            ]

    monkeypatch.setattr(privacy_module, "PresidioPrivacyEngine", LanguageEngine)
    service = privacy_module.PrivacyGateService()
    document = service.document_from_text("Cliente Mario Rossi")
    profile = get_profile("general_business")

    assert service.document_language == "en"
    assert created == ["en"]

    service.set_document_language("Italiano")
    assert service.document_language == "it"
    assert created == ["en"]  # selecting a language does not eagerly load its model

    italian = service.analyze(document, profile)
    assert italian[0].finding_id.startswith("it-")
    assert created == ["en", "it"]

    service.set_document_language("English")
    english = service.analyze(document, profile)
    assert english[0].finding_id.startswith("en-")
    assert created == ["en", "it"]  # existing engine is reused


def test_mask_mode_keeps_only_last_four_alphanumeric_characters():
    service = PrivacyGateService()
    text = "SSN 123-45-6789"
    finding = Finding(
        finding_id="ssn-1",
        entity_type="US_SSN",
        text="123-45-6789",
        start=4,
        end=len(text),
        score=1.0,
        page_number=1,
        context=text,
    )
    result = service.protect(service.document_from_text(text), (finding,), replacement_mode="mask")
    assert result.combined_text == "SSN ***-**-6789"
    assert result.mappings == ()
    assert len(result.combined_spans) == 1
    span = result.combined_spans[0]
    assert result.combined_text[span.start : span.end] == "***-**-6789"
    assert span.entity_type == "US_SSN"


def test_color_spans_survive_every_protection_mode_and_multiple_pages():
    service = PrivacyGateService()
    document = AnalysisDocument(
        source_kind="pdf",
        pages=(PageContent(1, "Tenant Jane Smith"), PageContent(2, "Owner Jane Smith")),
    )
    findings = tuple(
        Finding(
            finding_id=f"person-{page.page_number}",
            entity_type="PERSON",
            text="Jane Smith",
            start=page.text.index("Jane Smith"),
            end=page.text.index("Jane Smith") + len("Jane Smith"),
            score=1.0,
            page_number=page.page_number,
            context=page.text,
        )
        for page in document.pages
    )

    for mode in ("reversible", "generic", "mask", "redact"):
        result = service.protect(document, findings, replacement_mode=mode)
        assert len(result.combined_spans) == 2
        assert all(span.entity_type == "PERSON" for span in result.combined_spans)
        assert all(
            result.combined_text[span.start : span.end]
            for span in result.combined_spans
        )


def test_second_scan_detects_unprotected_residual_pii():
    service = PrivacyGateService(pii_engine=FakeResidualEngine())
    document = service.document_from_text("Contact jane@example.com")
    unprotected = service.protect(document, ())
    protected = service.protect(document, service.analyze(document, get_profile("property_management")))

    assert len(service.verify_protected(unprotected, get_profile("property_management"))) == 1
    assert service.verify_protected(protected, get_profile("property_management")) == ()