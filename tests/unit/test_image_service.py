from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PIL import Image

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.infrastructure.documents.document_pipeline import DocumentPipelineService
from ai_pm_lab_privacy_gate.infrastructure.documents.image_service import ImageDocumentService
from ai_pm_lab_privacy_gate.infrastructure.ocr.base import OcrLineObservation, OcrWordObservation


def _box(left: int, top: int, right: int, bottom: int):
    return ((left, top), (right, top), (right, bottom), (left, bottom))


class FakeOcrEngine:
    def read(self, _image: Image.Image):
        return (
            OcrLineObservation(
                text="Tenant Jane Smith email jane@example.com",
                confidence=0.99,
                polygon=_box(20, 30, 480, 65),
                words=(
                    OcrWordObservation("Tenant", 0.99, _box(20, 30, 85, 65)),
                    OcrWordObservation("Jane", 0.99, _box(100, 30, 150, 65)),
                    OcrWordObservation("Smith", 0.99, _box(158, 30, 220, 65)),
                    OcrWordObservation("email", 0.99, _box(235, 30, 285, 65)),
                    OcrWordObservation("jane@example.com", 0.99, _box(295, 30, 480, 65)),
                ),
            ),
        )


class EmptyOcrEngine:
    def read(self, _image: Image.Image):
        return ()


def _finding(document, value: str, entity_type: str) -> Finding:
    page = document.pages[0]
    start = page.text.index(value)
    return Finding(
        finding_id=f"image-{start}-{entity_type}",
        entity_type=entity_type,
        text=value,
        start=start,
        end=start + len(value),
        score=1.0,
        page_number=1,
        context=page.text,
    )


def test_image_ocr_layout_maps_text_offsets_to_word_pixels(tmp_path: Path) -> None:
    source = tmp_path / "screenshot.png"
    Image.new("RGB", (520, 100), "white").save(source)
    image_service = ImageDocumentService(ocr_engine=FakeOcrEngine())

    document = image_service.extract(source)

    assert document.source_kind == "image"
    assert document.pages[0].text == "Tenant Jane Smith email jane@example.com"
    start = document.pages[0].text.index("Jane Smith")
    regions = document.ocr_pages[0].regions_for_range(start, start + len("Jane Smith"))
    assert [region.text for region in regions] == ["Jane", "Smith"]


def test_image_protection_overwrites_pixels_and_exports_txt_companion(tmp_path: Path) -> None:
    source = tmp_path / "screenshot.png"
    Image.new("RGB", (520, 100), "white").save(source)
    pipeline = DocumentPipelineService(
        image_service=ImageDocumentService(ocr_engine=FakeOcrEngine())
    )
    service = PrivacyGateService(document_pipeline=pipeline)
    document = service.document_from_file(source)
    findings = (
        _finding(document, "Jane Smith", "PERSON"),
        _finding(document, "jane@example.com", "EMAIL_ADDRESS"),
    )
    result = service.protect(document, findings)

    protected, companion = service.save_protected_bundle(
        result, tmp_path / "screenshot_protected.png", document
    )

    assert protected.suffix == ".png"
    assert companion == tmp_path / "screenshot_protected.txt"
    protected_text = companion.read_text(encoding="utf-8")
    assert "Jane Smith" not in protected_text
    assert "jane@example.com" not in protected_text
    with Image.open(protected) as image:
        assert image.getpixel((110, 40)) != (255, 255, 255)
        assert image.getpixel((310, 40)) != (255, 255, 255)


def test_image_redaction_fails_closed_when_selected_value_has_no_geometry(tmp_path: Path) -> None:
    source = tmp_path / "screenshot.jpg"
    Image.new("RGB", (520, 100), "white").save(source)
    service = PrivacyGateService(
        document_pipeline=DocumentPipelineService(
            image_service=ImageDocumentService(ocr_engine=FakeOcrEngine())
        )
    )
    document = service.document_from_file(source)
    finding = _finding(document, "Jane", "PERSON")
    unsafe_document = replace(document, ocr_pages=())
    result = service.protect(document, (finding,))
    try:
        service.save_protected_document(result, tmp_path / "unsafe.jpg", unsafe_document)
    except ValueError as exc:
        assert "OCR layout" in str(exc)
    else:
        raise AssertionError("Image export must fail closed without OCR geometry")


def test_image_ocr_reports_clear_message_when_no_printed_text_is_found(tmp_path: Path) -> None:
    source = tmp_path / "blank.png"
    Image.new("RGB", (320, 180), "white").save(source)
    image_service = ImageDocumentService(ocr_engine=EmptyOcrEngine())

    try:
        image_service.extract(source)
    except ValueError as exc:
        message = str(exc)
        assert "No readable printed text" in message
        assert "Handwriting is not supported" in message
    else:
        raise AssertionError("Blank images must not enter the PII detector as empty documents")
