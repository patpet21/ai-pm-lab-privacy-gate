from __future__ import annotations

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.semantic_context import (
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


def test_semantic_person_labels_keep_unicode_hyphens_suffixes_and_clean_boundary() -> None:
    assert _context_values("PERSON", "Prepared by: Ana María Torres") == {"Ana María Torres"}
    assert _context_values("PERSON", "Site contact — Jean-Luc Bernard") == {"Jean-Luc Bernard"}
    assert _context_values("PERSON", "Please copy Darnell Washington, Jr. on the closing note.") == {
        "Darnell Washington, Jr."
    }
    assert _context_values("PERSON", "Contact person: Amina El-Sayed.") == {"Amina El-Sayed"}


def test_semantic_organization_context_and_legal_suffix_forms() -> None:
    assert _pattern_values(
        "ORGANIZATION",
        "North Harbor Facilities LLC will handle the work order.",
    ) == {"North Harbor Facilities LLC"}
    assert _pattern_values(
        "ORGANIZATION",
        "Invoice issued by Cedar & Stone Design, Inc.",
    ) == {"Cedar & Stone Design, Inc"}
    assert _context_values(
        "ORGANIZATION",
        "Employer\nBrightline Analytics Group",
    ) == {"Brightline Analytics Group"}
    assert _context_values(
        "ORGANIZATION",
        "Service provider — East River Mechanical Corp.",
    ) == {"East River Mechanical Corp"}


def test_semantic_location_context_recovers_named_places() -> None:
    assert _context_values("LOCATION", "Jurisdiction: District of Columbia") == {
        "District of Columbia"
    }
    assert _context_values("LOCATION", "Meeting location = White Plains") == {"White Plains"}
    assert _context_values("LOCATION", "She relocated from Santa Fe last year.") == {"Santa Fe"}


def test_semantic_context_does_not_promote_plain_labels_or_lowercase_concepts() -> None:
    negatives = (
        "Prepared by the project team",
        "Employer requirements were updated.",
        "Meeting location is flexible.",
        "She relocated from storage last year.",
    )
    for text in negatives:
        assert _context_values("PERSON", text) == set()
        assert _context_values("ORGANIZATION", text) == set()
        assert _context_values("LOCATION", text) == set()
    assert _pattern_values("ORGANIZATION", "The term LLC appears in the guide.") == set()


def test_semantic_context_wins_expected_categories_in_central_engine() -> None:
    text = """Prepared by: Ana María Torres
Site contact — Jean-Luc Bernard
Please copy Darnell Washington, Jr. on the closing note.
Contact person: Amina El-Sayed.
North Harbor Facilities LLC will handle the work order.
Invoice issued by Cedar & Stone Design, Inc.
Service provider — East River Mechanical Corp.
Employer
Brightline Analytics Group
She relocated from Santa Fe last year.
Jurisdiction: District of Columbia
Meeting location = White Plains
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
        ("PERSON", "Ana María Torres"),
        ("PERSON", "Jean-Luc Bernard"),
        ("PERSON", "Darnell Washington, Jr."),
        ("PERSON", "Amina El-Sayed"),
        ("ORGANIZATION", "North Harbor Facilities LLC"),
        ("ORGANIZATION", "Cedar & Stone Design, Inc"),
        ("ORGANIZATION", "East River Mechanical Corp"),
        ("ORGANIZATION", "Brightline Analytics Group"),
        ("LOCATION", "Santa Fe"),
        ("LOCATION", "District of Columbia"),
        ("LOCATION", "White Plains"),
    } <= found
