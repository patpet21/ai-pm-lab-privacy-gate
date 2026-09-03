from __future__ import annotations

from dataclasses import replace

import pytest

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile


def _findings(text: str):
    service = PrivacyGateService()
    base = get_profile("general_business")
    profile = replace(base, entities=entities_for_scope(base, "maximum"))
    return service.analyze(service.document_from_text(text), profile, language="en")


def _pairs(text: str) -> set[tuple[str, str]]:
    return {(item.entity_type, item.text) for item in _findings(text)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Traveler passport\nC01X23456", ("US_PASSPORT", "C01X23456")),
        ("UNIT\n4A", ("UNIT_NUMBER", "4A")),
        ("COI reference\nCOI-NY-88217", ("COI_REFERENCE", "COI-NY-88217")),
    ],
)
def test_explicit_sensitive_label_can_wrap_one_line_to_structured_value(
    text: str,
    expected: tuple[str, str],
) -> None:
    assert expected in _pairs(text)


def test_wrapped_label_does_not_consume_next_field_label() -> None:
    text = (
        "Passport:\n"
        "Tenant ID: TEN-77192\n"
        "UNIT:\n"
        "Lease number: L-2026-8841\n"
        "COI reference:\n"
        "Policy number: POL-991820\n"
    )
    pairs = _pairs(text)
    assert not any(entity == "US_PASSPORT" for entity, _ in pairs)
    assert not any(entity == "UNIT_NUMBER" and value.lower().startswith("lease") for entity, value in pairs)
    assert not any(entity == "COI_REFERENCE" and value.lower().startswith("policy") for entity, value in pairs)


def test_narrative_organization_before_later_contact_colon_is_preserved() -> None:
    text = (
        "Managed by Oakline Property Group LLC at 205 East 63rd Street Suite 12. "
        "Contact: Maya Patel, 917-555-0171."
    )
    pairs = _pairs(text)
    assert ("ORGANIZATION", "Oakline Property Group LLC") in pairs
    assert ("PERSON", "Maya Patel") in pairs


def test_short_field_labels_are_still_filtered_as_ner_noise() -> None:
    text = (
        "Broker email: broker@example.com\n"
        "Receipt email: receipt@example.com\n"
        "Seller net proceeds: $611,772.09\n"
        "Lobby access code: 8204\n"
    )
    pairs = _pairs(text)
    forbidden = {
        ("PERSON", "Broker"),
        ("PERSON", "Receipt"),
        ("PERSON", "Seller"),
        ("PERSON", "Lobby"),
    }
    assert not (pairs & forbidden)
