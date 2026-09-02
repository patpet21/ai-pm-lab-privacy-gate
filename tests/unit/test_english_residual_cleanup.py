from __future__ import annotations

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.residual_cleanup import (
    CONTEXT_RULES,
    PATTERN_RECOGNIZERS,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.real_estate import (
    ContextValueRecognizer,
)


def _context_values(entity_type: str, text: str) -> set[str]:
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


def test_residual_government_identity_variants() -> None:
    assert _context_values("US_DRIVER_LICENSE", "DL No. A-482-991-73") == {"A-482-991-73"}
    assert _context_values("US_DRIVER_LICENSE", "License no.\nS123-4567-8901") == {
        "S123-4567-8901"
    }
    assert _context_values("US_PASSPORT", "Passport (US): X1234567") == {"X1234567"}
    assert _context_values("DATE_OF_BIRTH", "Borrower (DOB 4-18-87)") == {"4-18-87"}
    assert _context_values("DATE_OF_BIRTH", "Birth date: April 18, 1987") == {
        "April 18, 1987"
    }


def test_residual_financial_and_phone_variants() -> None:
    assert _context_values("MERCHANT", "Merchant: Green House Farmers Market") == {
        "Green House Farmers Market"
    }
    assert _pattern_values("PHONE_NUMBER", "Call 212-555-0199 ext. 42") == {
        "212-555-0199 ext. 42"
    }


def test_residual_cleanup_requires_strong_structure() -> None:
    text = """The driver license policy was revised.
Passport renewal policy is documented.
The DOB field is required on this form.
Merchant services training starts Monday.
Call 212-555-0199 tomorrow.
"""
    assert _context_values("US_DRIVER_LICENSE", text) == set()
    assert _context_values("US_PASSPORT", text) == set()
    assert _context_values("DATE_OF_BIRTH", text) == set()
    assert _context_values("MERCHANT", text) == set()
    assert _pattern_values("PHONE_NUMBER", text) == set()


def test_residual_cleanup_wins_exact_spans_in_central_engine() -> None:
    text = """DL No. A-482-991-73
License no.
S123-4567-8901
Passport (US): X1234567
Borrower (DOB 4-18-87)
Merchant: Green House Farmers Market
Call 212-555-0199 ext. 42
"""
    base = get_profile("general_business")
    profile = type(base)(
        key=base.key,
        name=base.name,
        description=base.description,
        entities=entities_for_scope(base, "maximum"),
        threshold=base.threshold,
    )
    service = PrivacyGateService()
    findings = service.analyze(service.document_from_text(text), profile)
    found = {(item.entity_type, item.text) for item in findings}

    assert {
        ("US_DRIVER_LICENSE", "A-482-991-73"),
        ("US_DRIVER_LICENSE", "S123-4567-8901"),
        ("US_PASSPORT", "X1234567"),
        ("DATE_OF_BIRTH", "4-18-87"),
        ("MERCHANT", "Green House Farmers Market"),
        ("PHONE_NUMBER", "212-555-0199 ext. 42"),
    } <= found
