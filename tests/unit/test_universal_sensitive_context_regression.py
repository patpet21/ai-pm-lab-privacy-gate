from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.real_estate import (
    ContextValueRecognizer,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.universal_sensitive import (
    CONTEXT_RULES,
    PATTERN_RECOGNIZERS,
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


def test_general_bank_account_labels_cover_descriptive_account_names() -> None:
    assert _values(
        "US_BANK_NUMBER",
        "Dedicated rent account number: 000123456789",
    ) == {"000123456789"}
    assert _values(
        "US_BANK_NUMBER",
        "Business account no. 987654321098",
    ) == {"987654321098"}


def test_general_business_registration_labels_cover_no_colon_and_state_entity_id() -> None:
    assert _values(
        "BUSINESS_REGISTRATION_NUMBER",
        "Registration No.: 004821",
    ) == {"004821"}
    assert _values(
        "BUSINESS_REGISTRATION_NUMBER",
        "NY DOS Entity ID: 7654321",
    ) == {"7654321"}


def test_money_amount_allows_normal_sentence_punctuation() -> None:
    assert _pattern_values(
        "MONEY_AMOUNT",
        "Monthly rent amount: USD 4,850.00.",
    ) == {"USD 4,850.00"}
