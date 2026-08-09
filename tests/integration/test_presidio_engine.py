from ai_pm_lab_privacy_gate.domain.models import PageContent
from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine


def test_presidio_detects_common_us_pii_and_protects_it():
    text = "Jane Smith can be reached at jane.smith@example.com or 212-555-5555. SSN: 219-09-9999."
    page = PageContent(page_number=1, text=text)
    engine = PresidioPrivacyEngine()
    findings = engine.analyze_page(page, get_profile("property_management"))
    entity_types = {finding.entity_type for finding in findings}
    assert "EMAIL_ADDRESS" in entity_types
    assert "PHONE_NUMBER" in entity_types
    assert "US_SSN" in entity_types
    protected = engine.protect_text(text, findings)
    assert "jane.smith@example.com" not in protected
    assert "212-555-5555" not in protected
    assert "219-09-9999" not in protected
