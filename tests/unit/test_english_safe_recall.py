from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.safe_recall import (
    CONTEXT_RULES,
    PATTERN_RECOGNIZERS,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.real_estate import (
    ContextValueRecognizer,
)


def _values(entity_type: str, text: str) -> set[str]:
    values: set[str] = set()
    for rule in CONTEXT_RULES:
        if rule.entity_type != entity_type:
            continue
        recognizer = ContextValueRecognizer(rule)
        for result in recognizer.analyze(text, entities=[entity_type]):
            values.add(text[result.start : result.end])
    return values


def _pattern_values(entity_type: str, text: str) -> set[str]:
    values: set[str] = set()
    for recognizer in PATTERN_RECOGNIZERS:
        if entity_type not in recognizer.supported_entities:
            continue
        for result in recognizer.analyze(text, entities=[entity_type]):
            values.add(text[result.start : result.end])
    return values


def test_government_and_financial_label_variants() -> None:
    assert _values("US_EIN", "Employer Identification Number = 98-7654321") == {"98-7654321"}
    assert _values("US_EIN", "Company EIN — 27-1357924.") == {"27-1357924"}
    assert _values("US_SSN", "Social Security Number = 123-45-6789") == {"123-45-6789"}
    assert _values("US_ROUTING_NUMBER", "ABA routing = 011000015") == {"011000015"}
    assert _values("SWIFT_BIC", "BIC = CHASUS33") == {"CHASUS33"}
    assert _values("SWIFT_BIC", "SWIFT code CITIUS33") == {"CITIUS33"}


def test_card_last_four_variants() -> None:
    assert _values("CARD_LAST_FOUR", "Visa ending 8820") == {"8820"}
    assert _values("CARD_LAST_FOUR", "Last four: 7712") == {"7712"}
    assert _values("CARD_LAST_FOUR", "CARD LAST 4 = 1934") == {"1934"}


def test_business_identifier_separator_and_abbreviation_variants() -> None:
    assert _values("BUSINESS_REGISTRATION_NUMBER", "Business ID = NY-8842017") == {"NY-8842017"}
    assert _values("INVOICE_NUMBER", "INV NO. = INV-NY-8821") == {"INV-NY-8821"}
    assert _values("PURCHASE_ORDER_ID", "P.O. # 889104") == {"889104"}
    assert _values("PURCHASE_ORDER_ID", "PO ID = NY-PO-2026-77") == {"NY-PO-2026-77"}
    assert _values("CONTRACT_ID", "Contract # AG-2026-118") == {"AG-2026-118"}
    assert _values("CONTRACT_ID", "Agreement contract ID = C-88420") == {"C-88420"}
    assert _values("CONTRACT_ID", "CONTRACT NO.\nNYC-4417-A") == {"NYC-4417-A"}
    assert _values("EMPLOYEE_ID", "Employee no. = 771204") == {"771204"}
    assert _values("CASE_REFERENCE", "Case No.: LT-302184-26") == {"LT-302184-26"}
    assert _values("HOUSING_LEGAL_CASE_ID", "Legal matter ID = MAT-99172") == {"MAT-99172"}


def test_real_estate_explicit_label_variants() -> None:
    assert _values("TENANT_ID", "Resident account = RES-44018") == {"RES-44018"}
    assert _values("LEASE_ID", "Lease no.\nL-2026-8841") == {"L-2026-8841"}
    assert _values("NYC_BBL", "BBL = 1011650042") == {"1011650042"}
    assert _values("PROPERTY_IDENTIFIER", "Tax lot = 42") == {"42"}
    assert _values("SECURITY_CODE", "Alarm code = 1984") == {"1984"}
    assert _values("SAFE_COMBINATION", "Safe combination = 33-18-72") == {"33-18-72"}
    assert _values("RENT_AMOUNT", "Legal rent = 4850") == {"4850"}
    assert _values("SECURITY_DEPOSIT_AMOUNT", "Security deposit held = $3,275.00") == {"$3,275.00"}
    assert _values("OPERATING_BALANCE", "Operating balance = $86,204.14") == {"$86,204.14"}
    assert _values("PURCHASE_PRICE", "Purchase price = $1,385,000") == {"$1,385,000"}
    assert _values("BROKER_COMMISSION", "Broker commission = 5%") == {"5%"}
    assert _values("ESCROW_AMOUNT", "Escrow holdback = $35,000") == {"$35,000"}
    assert _values("CONTRACTOR_LICENSE", "Contractor license = NYC-HIC-2091842") == {"NYC-HIC-2091842"}
    assert _values("LIEN_WAIVER_ID", "Lien waiver ID = LW-2026-1184") == {"LW-2026-1184"}
    assert _values("WIFI_CREDENTIAL", "Building Wi-Fi password = N0rthPier!8842") == {"N0rthPier!8842"}


def test_date_of_birth_and_full_url_variants() -> None:
    assert _values("DATE_OF_BIRTH", "Born on March 14, 1981.") == {"March 14, 1981"}
    assert _pattern_values(
        "URL",
        "Portal URL: https://portal.northharbor.example/login",
    ) == {"https://portal.northharbor.example/login"}
    assert _pattern_values(
        "URL",
        "Website = https://www.cedarstone.example/projects/42",
    ) == {"https://www.cedarstone.example/projects/42"}


def test_safe_recall_does_not_promote_plain_business_language() -> None:
    text = """The contract is under review.
The broker commission policy was updated.
Wi-Fi password policy is documented.
The invoice process is handled by accounting.
The tenant account team meets monthly.
"""
    for entity_type in {
        "CONTRACT_ID",
        "BROKER_COMMISSION",
        "WIFI_CREDENTIAL",
        "INVOICE_NUMBER",
        "TENANT_ID",
    }:
        assert _values(entity_type, text) == set()
