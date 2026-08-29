from __future__ import annotations

from PIL import Image

from ai_pm_lab_privacy_gate.domain.ocr import OcrTextRegion
from ai_pm_lab_privacy_gate.infrastructure.documents.image_service import ImageDocumentService
from ai_pm_lab_privacy_gate.infrastructure.ocr.rapidocr_engine import (
    _canonical_line_text,
    _line_for_word,
    _prepare_for_ocr,
    _word_entries,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.business import (
    build_business_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.guardrails import (
    is_italian_ner_false_positive,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.identity_documents import (
    build_identity_document_recognizers,
)


def _box(left: float, top: float, right: float, bottom: float):
    return ((left, top), (right, top), (right, bottom), (left, bottom))


def test_rapidocr_flat_word_results_are_kept_and_mapped_to_lines() -> None:
    words = _word_entries(
        (
            ("Mario", 0.99, _box(10, 10, 55, 28)),
            ("Rossi", 0.98, _box(60, 10, 105, 28)),
        )
    )
    assert [word.text for word in words] == ["Mario", "Rossi"]
    line_polygons = (_box(5, 6, 120, 32), _box(5, 50, 120, 75))
    assert _line_for_word(words[0], line_polygons) == 0
    assert _line_for_word(words[1], line_polygons) == 0


def test_word_level_text_recovers_values_missing_from_weak_line_text() -> None:
    words = _word_entries(
        (
            ("Carta", 0.98, _box(10, 10, 45, 28)),
            ("d'identità", 0.97, _box(50, 10, 115, 28)),
            ("CA12345AA", 0.99, _box(120, 10, 195, 28)),
            ("Passaporto", 0.98, _box(205, 10, 285, 28)),
            ("YA1234567", 0.99, _box(290, 10, 365, 28)),
        )
    )
    assert _canonical_line_text("Cart . . . colo", words) == (
        "Carta d'identità CA12345AA Passaporto YA1234567"
    )


def test_preprocessing_upscales_small_document_and_coordinates_can_map_back() -> None:
    image = Image.new("RGB", (1000, 500), "white")
    prepared, scale = _prepare_for_ocr(image)
    assert scale == 2.0
    assert prepared.size == (2000, 1000)

    words = _word_entries(
        (("CA12345AA", 0.99, _box(200, 100, 400, 140)),),
        coordinate_scale=1.0 / scale,
    )
    assert words[0].polygon == _box(100, 50, 200, 70)


def test_image_boxes_remain_separate_across_ocr_lines() -> None:
    regions = (
        OcrTextRegion("Mario", 0, 5, 0.99, _box(10, 10, 55, 28), "word", 0),
        OcrTextRegion("Rossi", 6, 11, 0.99, _box(60, 10, 105, 28), "word", 0),
        OcrTextRegion("Milano", 12, 18, 0.99, _box(10, 50, 70, 70), "word", 1),
    )
    boxes = ImageDocumentService._boxes_by_line(regions, (300, 200))
    assert len(boxes) == 2
    assert boxes[0][3] < boxes[1][1]


def test_italian_schema_labels_are_not_generic_locations_or_people() -> None:
    for value in (
        "IT_FISCAL_CODE",
        "IT_VAT_NUMBER",
        "STREET_ADDRESS",
        "POSTAL_CODE",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
    ):
        assert is_italian_ner_false_positive("LOCATION", value)
        assert is_italian_ner_false_positive("PERSON", value)


def test_wide_italian_checklist_spans_are_not_private_ner_values() -> None:
    for entity_type, value in (
        ("ORGANIZATION", "REA/Registro Imprese"),
        ("LOCATION", "provincia. Dati"),
        ("LOCATION", "STREET_ADDRESS, POSTAL_CODE/CAP, provincia"),
        ("PERSON", "Documenti di identità: carta identità/passaporto/patente"),
    ):
        assert is_italian_ner_false_positive(entity_type, value)


def test_identity_labels_do_not_consume_following_prose() -> None:
    text = "Documenti di identità: carta identità/passaporto/patente Targa veicolo"
    findings = []
    for recognizer in build_identity_document_recognizers():
        findings.extend(recognizer.analyze(text, recognizer.supported_entities))
    assert findings == []

    valid = "Carta d'identità n.: CA12345AA. Passaporto: YA1234567. Patente: U1A234567."
    values = []
    for recognizer in build_identity_document_recognizers():
        for finding in recognizer.analyze(valid, recognizer.supported_entities):
            values.append(valid[finding.start : finding.end])
    assert set(values) == {"CA12345AA", "YA1234567", "U1A234567"}


def test_business_register_label_does_not_consume_instruction_text() -> None:
    text = "REA/Registro Imprese consigliata di test"
    results = []
    for recognizer in build_business_recognizers():
        results.extend(recognizer.analyze(text, recognizer.supported_entities))
    assert not any(result.entity_type == "IT_BUSINESS_REGISTER_NUMBER" for result in results)
