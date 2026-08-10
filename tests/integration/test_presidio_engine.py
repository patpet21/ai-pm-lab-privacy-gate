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


def test_strict_context_recognizers_cover_government_financial_and_property_ids():
    values = {
        "US_SSN": "123-45-6789",
        "US_DRIVER_LICENSE": "123 456 789",
        "US_PASSPORT": "123456789",
        "US_BANK_NUMBER": "9876543210",
        "US_ROUTING_NUMBER": "021000021",
        "TENANT_ID": "TEN-982174",
        "LEASE_ID": "LEASE-NY-260809-04",
        "NYC_BBL": "1-00758-0042",
        "NYC_BIN": "1015862",
        "VENDOR_ACCOUNT_ID": "VND-204851",
        "WORK_ORDER_ID": "WO-260809-42",
        "PROPOSAL_ID": "PROP-MBS-260809-17",
        "INSURANCE_POLICY_ID": "CGL-NY-1234567",
        "PREAPPROVAL_ID": "PA-NY-260809-18",
        "MORTGAGE_REFERENCE": "MTG-260809-735",
    }
    text = "\n".join(
        (
            "Synthetic SSN: 123-45-6789",
            "NY driver's license: 123 456 789",
            "Passport no.: 123456789",
            "Bank account: 9876543210",
            "ABA routing number: 021000021",
            "Tenant ID: TEN-982174",
            "Lease ID: LEASE-NY-260809-04",
            "NYC BBL: 1-00758-0042",
            "NYC BIN: 1015862",
            "Vendor account ID: VND-204851",
            "Work order: WO-260809-42",
            "Proposal: PROP-MBS-260809-17",
            "Insurance policy: CGL-NY-1234567",
            "Preapproval reference: PA-NY-260809-18",
            "Mortgage reference: MTG-260809-735",
        )
    )
    page = PageContent(page_number=1, text=text)
    engine = PresidioPrivacyEngine()
    findings = engine.analyze_page(page, get_profile("property_management"))
    by_type = {finding.entity_type: finding.text for finding in findings}

    for entity_type, value in values.items():
        assert by_type.get(entity_type) == value

    protected = engine.protect_text(text, findings)
    for value in values.values():
        assert value not in protected


def test_phone_split_by_pdf_line_wrap_is_detected():
    text = "Call the tenant at (917)\n555-0126 today."
    page = PageContent(page_number=1, text=text)
    findings = PresidioPrivacyEngine().analyze_page(page, get_profile("property_management"))
    assert any(
        finding.entity_type == "PHONE_NUMBER" and finding.text == "(917)\n555-0126"
        for finding in findings
    )


def test_structured_sector_ids_are_detected_when_repeated_without_labels():
    text = "Invoices reference VND-204851, PROP-MBS-260809-17 and BBL 1-00758-0042."
    page = PageContent(page_number=1, text=text)
    findings = PresidioPrivacyEngine().analyze_page(page, get_profile("projects_renovations"))
    detected = {(finding.entity_type, finding.text) for finding in findings}
    assert ("VENDOR_ACCOUNT_ID", "VND-204851") in detected
    assert ("PROPOSAL_ID", "PROP-MBS-260809-17") in detected
    assert ("NYC_BBL", "1-00758-0042") in detected
