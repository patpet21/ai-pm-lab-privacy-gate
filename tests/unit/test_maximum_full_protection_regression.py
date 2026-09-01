from __future__ import annotations

from dataclasses import dataclass

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, Finding, PageContent
from ai_pm_lab_privacy_gate.domain.profiles import (
    DEFAULT_PROFILE_KEY,
    DEFAULT_SCOPE_KEY,
    entities_for_scope,
    get_profile,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.universal_sensitive import (
    adjacent_segment_findings,
)


@dataclass
class _Result:
    entity_type: str
    start: int
    end: int
    score: float = 0.97


def _result(text: str, value: str, entity_type: str) -> _Result:
    start = text.index(value)
    return _Result(entity_type=entity_type, start=start, end=start + len(value))


def _finding(page_number: int, text: str, value: str, entity_type: str) -> Finding:
    start = text.index(value)
    end = start + len(value)
    return Finding(
        finding_id=f"test-{page_number}-{start}-{end}-{entity_type}",
        entity_type=entity_type,
        text=text[start:end],
        start=start,
        end=end,
        score=0.97,
        page_number=page_number,
        context=text,
    )


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


def test_schema_and_procedure_phrases_are_not_organizations() -> None:
    schema_text = "NYC property IDs: borough / block / lot / BBL / unit"
    schema_result = _result(schema_text, "NYC", "ORGANIZATION")
    assert PresidioPrivacyEngine._filter_context_value_false_positives(
        schema_text,
        [schema_result],
    ) == []

    procedure_text = "Scan & Protect."
    procedure_result = _result(procedure_text, "Scan & Protect", "ORGANIZATION")
    assert PresidioPrivacyEngine._filter_context_value_false_positives(
        procedure_text,
        [procedure_result],
    ) == []


def test_office_adjacent_segments_recover_property_table_values() -> None:
    document = AnalysisDocument(
        source_kind="docx",
        pages=(
            PageContent(1, "Block"),
            PageContent(2, "1165"),
            PageContent(3, "Lot"),
            PageContent(4, "42"),
            PageContent(5, "BBL"),
            PageContent(6, "1011650042"),
            PageContent(7, "Unit"),
            PageContent(8, "8B"),
        ),
    )
    general = get_profile(DEFAULT_PROFILE_KEY)
    enabled = entities_for_scope(general, DEFAULT_SCOPE_KEY)

    findings = adjacent_segment_findings(document, enabled)
    assert {(item.page_number, item.entity_type, item.text) for item in findings} == {
        (2, "PROPERTY_IDENTIFIER", "1165"),
        (4, "PROPERTY_IDENTIFIER", "42"),
        (6, "NYC_BBL", "1011650042"),
        (8, "UNIT_NUMBER", "8B"),
    }


def test_adjacent_segment_recovery_does_not_cross_pdf_pages() -> None:
    document = AnalysisDocument(
        source_kind="pdf",
        pages=(PageContent(1, "BBL"), PageContent(2, "1011650042")),
    )
    general = get_profile(DEFAULT_PROFILE_KEY)
    enabled = entities_for_scope(general, DEFAULT_SCOPE_KEY)

    assert adjacent_segment_findings(document, enabled) == ()


def test_final_en_cleanup_blocks_propagated_schema_noise_and_preserves_punctuation() -> None:
    schema = "NYC property IDs: borough / block / lot / BBL / unit"
    procedure = "Run Scan & Protect."
    synthetic = "Synthetic test data only - PrivacyGate English / NYC real estate detector validation"
    access = "Building access credential: NYC-8B-4821. Authorized vehicle plate: KNY-4821."
    document = AnalysisDocument(
        source_kind="docx",
        pages=(
            PageContent(1, schema),
            PageContent(2, procedure),
            PageContent(3, synthetic),
            PageContent(4, access),
        ),
    )
    findings = (
        _finding(1, schema, "NYC", "LOCATION"),
        _finding(2, procedure, "Run Scan & Protect", "ORGANIZATION"),
        _finding(3, synthetic, "NYC", "LOCATION"),
        _finding(4, access, "NYC-8B-4821.", "PROPERTY_ACCESS_CODE"),
    )

    cleaned = PrivacyGateService._filter_english_document_findings(document, findings)

    assert len(cleaned) == 1
    access_finding = cleaned[0]
    assert access_finding.entity_type == "PROPERTY_ACCESS_CODE"
    assert access_finding.text == "NYC-8B-4821"
    assert access[access_finding.end] == "."
