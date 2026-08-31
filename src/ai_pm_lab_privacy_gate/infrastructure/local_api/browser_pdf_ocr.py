from __future__ import annotations

from pathlib import Path

import pdfplumber

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, PageContent
from ai_pm_lab_privacy_gate.infrastructure.documents.image_service import ImageDocumentService
from ai_pm_lab_privacy_gate.infrastructure.ocr.base import OcrEngine
from ai_pm_lab_privacy_gate.infrastructure.ocr.rapidocr_engine import RapidOcrEngine


class BrowserPdfOcrTextExtractor:
    """Local OCR fallback for PDF pages that have no selectable text.

    The browser handoff never needs to preserve the original scanned page objects:
    PrivacyGate sends ChatGPT a newly generated protected PDF.  For that reason the
    OCR adapter only has to recover trustworthy local text for analysis/protection.
    The original PDF bytes remain in the short-lived browser request/temporary file
    and are never forwarded to the AI provider.
    """

    def __init__(
        self,
        ocr_engine: OcrEngine | None = None,
        *,
        resolution: int = 180,
    ) -> None:
        self.ocr = ocr_engine or RapidOcrEngine()
        self.resolution = max(120, min(240, int(resolution)))

    def fill_missing_pages(
        self,
        path: str | Path,
        document: AnalysisDocument,
    ) -> tuple[AnalysisDocument, tuple[int, ...]]:
        """OCR only pages whose PDF text layer is empty.

        A mixed PDF can contain normal text pages and scanned image pages.  Empty
        pages are therefore handled individually rather than treating OCR as an
        all-or-nothing document mode.  If an empty-text page cannot be read by OCR,
        the browser upload is stopped fail-closed instead of silently sending an
        uninspected page to ChatGPT.
        """
        missing = tuple(
            page.page_number for page in document.pages if not page.text.strip()
        )
        if not missing:
            return document, ()

        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)

        missing_set = set(missing)
        updated_pages: list[PageContent] = []
        ocr_pages: list[int] = []

        with pdfplumber.open(source) as pdf:
            if len(pdf.pages) != len(document.pages):
                raise ValueError(
                    "PDF page count changed during local OCR; protection was stopped for safety."
                )

            for index, page_content in enumerate(document.pages, start=1):
                if page_content.page_number not in missing_set:
                    updated_pages.append(page_content)
                    continue

                rendered = pdf.pages[index - 1].to_image(
                    resolution=self.resolution,
                    antialias=True,
                ).original.convert("RGB")
                lines = self.ocr.read(rendered)
                text, _regions = ImageDocumentService._layout_text(lines)
                if not text.strip():
                    raise ValueError(
                        f"Local OCR could not safely read PDF page {page_content.page_number}. "
                        "Nothing was attached to the AI."
                    )

                updated_pages.append(
                    PageContent(
                        page_number=page_content.page_number,
                        text=text,
                        location="pdf-ocr",
                    )
                )
                ocr_pages.append(page_content.page_number)

        return (
            AnalysisDocument(
                source_kind=document.source_kind,
                source_path=document.source_path,
                pages=tuple(updated_pages),
                ocr_pages=document.ocr_pages,
            ),
            tuple(ocr_pages),
        )
