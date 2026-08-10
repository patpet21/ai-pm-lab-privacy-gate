from pathlib import Path

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding
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


def test_second_scan_detects_unprotected_residual_pii():
    service = PrivacyGateService(pii_engine=FakeResidualEngine())
    document = service.document_from_text("Contact jane@example.com")
    unprotected = service.protect(document, ())
    protected = service.protect(document, service.analyze(document, get_profile("property_management")))

    assert len(service.verify_protected(unprotected, get_profile("property_management"))) == 1
    assert service.verify_protected(protected, get_profile("property_management")) == ()
