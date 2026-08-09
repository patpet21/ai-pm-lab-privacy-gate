from __future__ import annotations

import os
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, PageContent


class PdfDocumentService:
    def extract(self, path: str | Path) -> AnalysisDocument:
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(source)
        reader = PdfReader(str(source))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise ValueError("Password-protected PDFs are not supported in this build.") from exc
        pages = tuple(
            PageContent(page_number=index, text=page.extract_text() or "")
            for index, page in enumerate(reader.pages, start=1)
        )
        return AnalysisDocument(source_kind="pdf", source_path=source, pages=pages)

    def write_protected(self, pages: tuple[PageContent, ...], path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        font_name = self._register_windows_font()
        styles = getSampleStyleSheet()
        body = ParagraphStyle(
            "PrivacyGateBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9.5,
            leading=13,
            alignment=TA_LEFT,
            spaceAfter=6,
        )
        heading = ParagraphStyle(
            "PrivacyGateHeading",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=12,
            leading=15,
            textColor="#16324F",
            spaceAfter=10,
        )
        doc = SimpleDocTemplate(
            str(destination),
            pagesize=letter,
            rightMargin=0.65 * inch,
            leftMargin=0.65 * inch,
            topMargin=0.7 * inch,
            bottomMargin=0.65 * inch,
            title="Protected copy - AI PM LAB Privacy Gate",
            author="AI PM LAB Privacy Gate",
        )
        story = []
        for page_index, page in enumerate(pages):
            story.append(Paragraph(f"Protected copy - source page {page.page_number}", heading))
            chunks = page.text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            for chunk in chunks:
                cleaned = chunk.strip()
                if cleaned:
                    story.append(Paragraph(escape(cleaned), body))
                else:
                    story.append(Spacer(1, 5))
            if page_index < len(pages) - 1:
                story.append(PageBreak())
        doc.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
        return destination

    @staticmethod
    def _register_windows_font() -> str:
        font_path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf"
        if font_path.exists():
            try:
                if "PrivacyGateArial" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("PrivacyGateArial", str(font_path)))
                return "PrivacyGateArial"
            except Exception:
                pass
        return "Helvetica"

    @staticmethod
    def _footer(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColorRGB(0.35, 0.39, 0.43)
        canvas.drawString(0.65 * inch, 0.35 * inch, "Generated locally by AI PM LAB Privacy Gate")
        canvas.drawRightString(7.85 * inch, 0.35 * inch, f"Page {document.page}")
        canvas.restoreState()

