from __future__ import annotations

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, Finding, PageContent
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.guardrails import (
    adjacent_segment_findings,
    is_italian_ner_false_positive,
    propagate_known_ner_values,
)


def test_italian_ner_guardrails_reject_form_labels_from_real_fixture() -> None:
    for entity_type, value in (
        ("PERSON", "Telefono"),
        ("PERSON", "Codice Fiscale"),
        ("PERSON", "Foglio"),
        ("LOCATION", "Campo"),
        ("LOCATION", "Particella"),
        ("LOCATION", "Mappale"),
        ("LOCATION", "Subalterno"),
        ("LOCATION", "Targa"),
        ("LOCATION", "Italiano"),
        ("LOCATION", "F205"),
    ):
        assert is_italian_ner_false_positive(entity_type, value)

    assert not is_italian_ner_false_positive("PERSON", "Mario Rossi")
    assert not is_italian_ner_false_positive("LOCATION", "Milano")
    assert not is_italian_ner_false_positive(
        "ORGANIZATION", "Aurora Gestioni Immobiliari S.r.l."
    )


def test_adjacent_office_segments_recover_cadastral_cap_and_province_values() -> None:
    labels_and_values = (
        ("Comune catastale", "F205", "IT_CADASTRAL_MUNICIPAL_CODE"),
        ("Sezione catastale", "A", "IT_CADASTRAL_SECTION"),
        ("Foglio", "123", "IT_CADASTRAL_SHEET"),
        ("Particella / Mappale", "456", "IT_CADASTRAL_PARCEL"),
        ("Subalterno", "7", "IT_CADASTRAL_SUBALTERN"),
        ("CAP", "20121", "IT_POSTAL_CODE"),
        ("Provincia", "MI", "IT_PROVINCE"),
    )
    pages = []
    expected = []
    page_number = 1
    for label, value, entity_type in labels_and_values:
        pages.append(PageContent(page_number, label))
        page_number += 1
        pages.append(PageContent(page_number, value))
        expected.append((page_number, value, entity_type))
        page_number += 1

    document = AnalysisDocument(source_kind="docx", pages=tuple(pages))
    findings = adjacent_segment_findings(document)

    assert {(item.page_number, item.text, item.entity_type) for item in findings} == set(expected)


def test_known_italian_location_is_propagated_to_short_causale() -> None:
    document = AnalysisDocument(
        source_kind="docx",
        pages=(
            PageContent(1, "Residente a Milano"),
            PageContent(2, "Causale: canone locazione - Milano"),
        ),
    )
    first_start = document.pages[0].text.index("Milano")
    seed = Finding(
        finding_id="seed-milano",
        entity_type="LOCATION",
        text="Milano",
        start=first_start,
        end=first_start + len("Milano"),
        score=0.85,
        page_number=1,
        context=document.pages[0].text,
    )

    findings = propagate_known_ner_values(document, (seed,))

    assert [(item.page_number, item.text) for item in findings] == [
        (1, "Milano"),
        (2, "Milano"),
    ]
