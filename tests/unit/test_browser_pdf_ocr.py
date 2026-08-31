from pathlib import Path

from reportlab.pdfgen import canvas as reportlab_canvas

from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_pdf_ocr import (
    BrowserPdfOcrTextExtractor,
)
from ai_pm_lab_privacy_gate.infrastructure.ocr.base import OcrLineObservation


class _DeterministicOcrEngine:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, image):
        self.calls += 1
        assert image.width > 0
        assert image.height > 0
        return (
            OcrLineObservation(
                text="Scanned tenant Alice",
                confidence=0.99,
                polygon=((10.0, 10.0), (200.0, 10.0), (200.0, 35.0), (10.0, 35.0)),
            ),
        )


def test_browser_pdf_ocr_fills_only_pages_without_text_layer(tmp_path: Path) -> None:
    source = tmp_path / "mixed.pdf"
    pdf = reportlab_canvas.Canvas(str(source))
    pdf.drawString(72, 720, "Selectable first page")
    pdf.showPage()
    pdf.showPage()
    pdf.save()

    document = PdfDocumentService().extract(source)
    assert document.pages[0].text.strip()
    assert not document.pages[1].text.strip()

    ocr = _DeterministicOcrEngine()
    extractor = BrowserPdfOcrTextExtractor(ocr_engine=ocr, resolution=120)
    recovered, ocr_pages = extractor.fill_missing_pages(source, document)

    assert ocr.calls == 1
    assert ocr_pages == (2,)
    assert "Selectable first page" in recovered.pages[0].text
    assert recovered.pages[1].text == "Scanned tenant Alice"
    assert recovered.pages[1].location == "pdf-ocr"
