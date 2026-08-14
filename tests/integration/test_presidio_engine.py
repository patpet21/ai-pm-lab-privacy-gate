from ai_pm_lab_privacy_gate.domain.models import PageContent
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile
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
        "US_EIN": "12-3456789",
        "PROPERTY_IDENTIFIER": "APN-44-01928",
        "UNIT_NUMBER": "4B",
        "PROPERTY_ACCESS_CODE": "7284",
        "LOCKBOX_CODE": "9912",
        "CONTRACTOR_LICENSE": "NYC-HIC-2091842",
        "INSURANCE_CLAIM_ID": "CLM-NY-77421",
        "UTILITY_ACCOUNT_ID": "UTIL-CONED-90177",
        "LOAN_NUMBER": "LOAN-8821904",
        "TRANSACTION_ID": "TXN-NY-55109",
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
            "Employer identification number: 12-3456789",
            "Property ID: APN-44-01928",
            "Unit: 4B",
            "Building access code: 7284",
            "Lockbox code: 9912",
            "Contractor license: NYC-HIC-2091842",
            "Insurance claim: CLM-NY-77421",
            "Electric account: UTIL-CONED-90177",
            "Loan number: LOAN-8821904",
            "Transaction ID: TXN-NY-55109",
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


def test_property_financial_and_operational_pack_is_always_detected():
    text = "\n".join(
        (
            "Alarm code: 1984",
            "Water Meter ID: WM-80271",
            "Section 8 Voucher ID: VCH-901184",
            "Lease expires: 11/30/2026",
            "Monthly Rent: $3,275.00",
            "Resident Balance: $4,860.25",
            "Security Deposit: $3,275.00",
            "Owner Distribution: $18,450.00",
            "Operating Balance: $86,204.14",
            "Replacement Reserve: $42,500",
            "Projected NOI: $325,000",
            "CAPEX Budget: $425,000",
            "Remaining capital budget: 84,500",
            "Construction contingency: $125,000",
            "Contractor Bid: USD 242,100",
            "Invoice Total: $24,880.40",
            "PO Value: $58,200",
            "Offer Price: $1,425,000",
            "Contract Price: $1,385,000",
            "Earnest Money: $69,250",
            "Broker Commission: 5%",
            "Seller Credit: $18,000",
            "Escrow Holdback: $35,000",
            "Management Fee: 4.0%",
            "Service Request: SR-2026-1182",
            "Project Code: REN-QNS-2607",
            "Deal ID: D-2026-10882",
            "Housing Court Index: LT-302184-26/NY",
            "DOB Job # 321884902",
            "HPD Complaint # 15482901",
            "Approval Code: AP-7719",
        )
    )
    profile = get_profile("property_management")
    findings = PresidioPrivacyEngine().analyze_page(PageContent(1, text), profile)
    detected = {finding.entity_type for finding in findings}
    expected = {
        "SECURITY_CODE", "UTILITY_METER_ID", "HOUSING_ASSISTANCE_ID",
        "LEASE_OCCUPANCY_DATE", "RENT_AMOUNT", "TENANT_BALANCE",
        "SECURITY_DEPOSIT_AMOUNT", "OWNER_DISTRIBUTION", "OPERATING_BALANCE",
        "RESERVE_BALANCE", "NOI_AMOUNT", "CAPEX_BUDGET_AMOUNT",
        "REMAINING_CAPITAL_BUDGET", "CONTINGENCY_AMOUNT", "CONTRACTOR_BID_AMOUNT",
        "INVOICE_AMOUNT", "PURCHASE_ORDER_VALUE", "OFFER_PRICE", "PURCHASE_PRICE",
        "EARNEST_MONEY_AMOUNT", "BROKER_COMMISSION", "CLOSING_CREDIT",
        "ESCROW_AMOUNT", "MANAGEMENT_FEE", "MAINTENANCE_TICKET_ID",
        "PROJECT_JOB_CODE", "HOUSING_LEGAL_CASE_ID",
        "NYC_DOB_JOB_ID", "NYC_HPD_RECORD_ID", "APPROVAL_AUTH_CODE",
    }
    assert expected <= detected
    assert expected <= set(entities_for_scope(profile, "essential"))


def test_real_estate_pack_ignores_context_words_without_values():
    text = (
        "CAPEX planning meeting is Monday. Commission policy follows the agreement. "
        "The building contains 12 units. Inspections occur annually. "
        "Reserve the loading area for deliveries."
    )
    findings = PresidioPrivacyEngine().analyze_page(
        PageContent(1, text), get_profile("property_management")
    )
    pack_entities = {
        "CAPEX_BUDGET_AMOUNT", "BROKER_COMMISSION", "UNIT_NUMBER",
        "INSPECTION_ACCESS_WINDOW", "RESERVE_BALANCE",
    }
    assert not pack_entities.intersection(finding.entity_type for finding in findings)
