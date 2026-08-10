from dataclasses import replace

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile


def _financial_profile():
    profile = get_profile("property_management")
    return replace(profile, entities=entities_for_scope(profile, "financial"))


def test_financial_context_corrects_generic_numeric_guesses():
    text = """Account number
8310722758
Routing number
026073150
Swift/BIC
CMFGUS33
registered number 0713629988
Card transaction of 8.67 USD issued by Green House Farmers Mk ASTORIA
31 July 2026 Card ending in 0461 Pietro Forestieri Transaction: CARD-4131737330
-8.67 39.09
Sent money to Pietro Forestieri
31 July 2026 Transaction: TRANSFER-8822946 Reference: Donation for school
Received money from Jane Doe with reference grocery
"""
    service = PrivacyGateService()
    document = service.document_from_text(text)
    findings = service.analyze(document, _financial_profile())
    by_text = {(item.text, item.entity_type) for item in findings}

    assert ("8310722758", "US_BANK_NUMBER") in by_text
    assert ("026073150", "US_ROUTING_NUMBER") in by_text
    assert ("CMFGUS33", "SWIFT_BIC") in by_text
    assert ("0713629988", "BUSINESS_REGISTRATION_NUMBER") in by_text
    assert ("0461", "CARD_LAST_FOUR") in by_text
    assert ("4131737330", "CARD_TRANSACTION_ID") in by_text
    assert ("8822946", "TRANSFER_TRANSACTION_ID") in by_text
    assert ("Green House Farmers Mk ASTORIA", "MERCHANT") in by_text
    assert ("grocery", "TRANSACTION_REFERENCE") in by_text
    assert ("Pietro Forestieri", "PERSON") in by_text or (
        "Pietro Forestieri", "COUNTERPARTY"
    ) in by_text
    assert any(item.entity_type == "MONEY_AMOUNT" and "8.67" in item.text for item in findings)
    assert not any(
        item.entity_type == "PHONE_NUMBER" and item.text in {"4131737330", "8822946"}
        for item in findings
    )
    protected = service.protect(document, findings)
    assert service.verify_protected(protected, _financial_profile()) == ()


def test_multiline_international_address_is_detected_as_one_sensitive_block():
    text = """Tenant address
via Mazzini 14
san sosti
87010
Italy
"""
    service = PrivacyGateService()
    document = service.document_from_text(text)
    findings = service.analyze(document, _financial_profile())

    assert any(
        item.entity_type == "STREET_ADDRESS"
        and "via Mazzini 14" in item.text
        and "87010" in item.text
        for item in findings
    )


def test_business_scope_recognizes_general_operational_identifiers():
    base = get_profile("projects_renovations")
    profile = replace(base, entities=entities_for_scope(base, "business"))
    text = (
        "Invoice number INV-2048\n"
        "Purchase order number PO-7741\n"
        "Contract reference CTR-9912\n"
        "Customer ID CUST-8801\n"
        "Employee ID EMP-3209\n"
        "Case reference CASE-4511"
    )
    service = PrivacyGateService()
    findings = service.analyze(service.document_from_text(text), profile)
    entity_types = {item.entity_type for item in findings}
    assert {
        "INVOICE_NUMBER",
        "PURCHASE_ORDER_ID",
        "CONTRACT_ID",
        "CUSTOMER_ID",
        "EMPLOYEE_ID",
        "CASE_REFERENCE",
    } <= entity_types
