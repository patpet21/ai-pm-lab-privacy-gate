from __future__ import annotations

from dataclasses import dataclass

from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine


@dataclass
class _Result:
    entity_type: str
    start: int
    end: int
    score: float = 0.85


def _result(text: str, value: str, entity_type: str, *, score: float = 0.85, occurrence: int = 1) -> _Result:
    cursor = 0
    start = -1
    for _ in range(occurrence):
        start = text.index(value, cursor)
        cursor = start + len(value)
    return _Result(entity_type=entity_type, start=start, end=start + len(value), score=score)


def test_english_precision_filter_removes_field_and_schedule_noise() -> None:
    text = """DOB: 04/18/1987
Microsoft Presidio was evaluated for prototyping.
Project Budget
Seller Credit
Suite testing passed in development.
CAPEX planning meeting is Monday.
The reserve study will be reviewed next week.
Version 20260901 identifies the build.
Date: March 14, 1981
Hudson Bridge Property Management LLC
"""
    results = [
        _result(text, "DOB", "ORGANIZATION"),
        _result(text, "Microsoft Presidio", "ORGANIZATION"),
        _result(text, "Project Budget", "ORGANIZATION"),
        _result(text, "Seller Credit", "PERSON"),
        _result(text, "Suite", "PERSON"),
        _result(text, "Monday", "DATE_TIME"),
        _result(text, "next week", "DATE_TIME"),
        _result(text, "20260901", "DATE_TIME"),
        _result(text, "March 14, 1981", "DATE_TIME"),
        _result(text, "Hudson Bridge Property Management LLC", "ORGANIZATION"),
    ]

    filtered = PresidioPrivacyEngine._filter_context_value_false_positives(text, results)
    kept = {(item.entity_type, text[item.start:item.end]) for item in filtered}

    assert kept == {
        ("DATE_TIME", "March 14, 1981"),
        ("ORGANIZATION", "Hudson Bridge Property Management LLC"),
    }


def test_english_precision_filter_blocks_postal_fragments_inside_identifiers() -> None:
    text = """Agreement contract ID = C-88420
Client identifier = CL-20991
Resident account = RES-44018
ZIP: 10001
"""
    results = [
        _result(text, "88420", "POSTAL_CODE"),
        _result(text, "20991", "POSTAL_CODE"),
        _result(text, "44018", "POSTAL_CODE"),
        _result(text, "10001", "POSTAL_CODE"),
    ]

    filtered = PresidioPrivacyEngine._filter_context_value_false_positives(text, results)
    assert [(item.entity_type, text[item.start:item.end]) for item in filtered] == [
        ("POSTAL_CODE", "10001")
    ]


def test_english_precision_filter_blocks_context_recognizer_grammar_values() -> None:
    text = """The organization will review the policy next week.
Commission policy follows the brokerage agreement.
Invoice processing is handled by accounting.
Case management procedures were updated.
The tenant ledger template is ready for review.
"""
    results = [
        _result(text, "next", "INSURANCE_POLICY_ID"),
        _result(text, "follows", "INSURANCE_POLICY_ID"),
        _result(text, "processing", "INVOICE_NUMBER"),
        _result(text, "management", "MAINTENANCE_TICKET_ID"),
        _result(text, "is ready for", "VEHICLE_LICENSE_PLATE"),
    ]

    assert PresidioPrivacyEngine._filter_context_value_false_positives(text, results) == []


def test_english_precision_filter_blocks_generic_driver_license_fragment() -> None:
    text = "Employer Identification Number = 98-7654321\nContractor license = NYC-HIC-2091842"
    results = [
        _result(text, "7654321", "US_DRIVER_LICENSE"),
        _result(text, "2091842", "US_DRIVER_LICENSE"),
    ]

    assert PresidioPrivacyEngine._filter_context_value_false_positives(text, results) == []


def test_specific_english_categories_win_over_compatible_generic_overlaps() -> None:
    text = """Date of birth = 1987-04-18
Company EIN = 27-1357924
Agreement contract ID = C-88420
Bank routing no. 071000013
Security deposit held = $3,275.00
"""
    results = [
        _result(text, "1987-04-18", "DATE_TIME", score=0.99),
        _result(text, "1987-04-18", "DATE_OF_BIRTH", score=0.80),
        _result(text, "27-1357924", "DATE_TIME", score=0.95),
        _result(text, "27-1357924", "US_EIN", score=0.78),
        _result(text, "88420", "POSTAL_CODE", score=0.86),
        _result(text, "C-88420", "CONTRACT_ID", score=0.76),
        _result(text, "071000013", "US_BANK_NUMBER", score=0.90),
        _result(text, "071000013", "US_ROUTING_NUMBER", score=0.77),
        _result(text, "$3,275.00", "MONEY_AMOUNT", score=0.90),
        _result(text, "$3,275.00", "SECURITY_DEPOSIT_AMOUNT", score=0.79),
    ]

    preferred = PresidioPrivacyEngine._prefer_specific_english_results(results)
    resolved = PresidioPrivacyEngine._without_overlaps(preferred)
    kept = {(item.entity_type, text[item.start:item.end]) for item in resolved}

    assert kept == {
        ("DATE_OF_BIRTH", "1987-04-18"),
        ("US_EIN", "27-1357924"),
        ("CONTRACT_ID", "C-88420"),
        ("US_ROUTING_NUMBER", "071000013"),
        ("SECURITY_DEPOSIT_AMOUNT", "$3,275.00"),
    }
