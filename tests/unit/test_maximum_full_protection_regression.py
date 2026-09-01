from __future__ import annotations

from dataclasses import dataclass

from ai_pm_lab_privacy_gate.domain.profiles import (
    DEFAULT_PROFILE_KEY,
    DEFAULT_SCOPE_KEY,
    entities_for_scope,
    get_profile,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine


@dataclass
class _Result:
    entity_type: str
    start: int
    end: int
    score: float = 0.97


def _result(text: str, value: str, entity_type: str) -> _Result:
    start = text.index(value)
    return _Result(entity_type=entity_type, start=start, end=start + len(value))


def test_default_maximum_scans_core_and_installed_vertical_categories() -> None:
    general = get_profile(DEFAULT_PROFILE_KEY)
    maximum = entities_for_scope(general, DEFAULT_SCOPE_KEY)

    assert set(general.entities).issubset(maximum)
    assert "NYC_BBL" in maximum
    assert "UNIT_NUMBER" in maximum
    assert "RENT_AMOUNT" in maximum
    assert "VEHICLE_LICENSE_PLATE" in maximum
    assert len(maximum) == len(set(maximum))

    # Custom remains the selected profile's explicit entity set.
    assert entities_for_scope(general, "custom") == general.entities


def test_vertical_context_filter_drops_unit_grammar_but_keeps_real_unit() -> None:
    false_text = "The leased unit is located at 245 West 74th Street."
    false_result = _result(false_text, "is", "UNIT_NUMBER")
    assert PresidioPrivacyEngine._filter_context_value_false_positives(
        false_text,
        [false_result],
    ) == []

    real_text = "Apartment 8B is ready for inspection."
    real_result = _result(real_text, "8B", "UNIT_NUMBER")
    assert PresidioPrivacyEngine._filter_context_value_false_positives(
        real_text,
        [real_result],
    ) == [real_result]


def test_vertical_context_filter_rejects_street_number_as_signed_rent() -> None:
    false_text = "Payment memo: Rent - 245 West 74th Street Apt 8B - New York."
    false_result = _result(false_text, "- 245", "RENT_AMOUNT")
    assert PresidioPrivacyEngine._filter_context_value_false_positives(
        false_text,
        [false_result],
    ) == []

    real_text = "Monthly rent amount: 4850 per month."
    real_result = _result(real_text, "4850", "RENT_AMOUNT")
    assert PresidioPrivacyEngine._filter_context_value_false_positives(
        real_text,
        [real_result],
    ) == [real_result]
