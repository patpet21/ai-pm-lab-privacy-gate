from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

import pdfplumber
from PIL import ImageDraw, ImageFont
from pypdf import PdfReader
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, PageContent, ProtectionResult


class PdfDocumentService:
    ENTITY_COLORS = {
        "PERSON": "#DDE7FF",
        "EMAIL_ADDRESS": "#D9F3EE",
        "PHONE_NUMBER": "#FFE8CC",
        "US_SSN": "#FFDDE2",
        "US_ZIP_CODE": "#E8DFFF",
        "IP_ADDRESS": "#D8EEFF",
        "LOCATION": "#FFF1BD",
        "DATE_TIME": "#E3F2D7",
        "CREDIT_CARD": "#F8DDF1",
        "US_BANK_NUMBER": "#F5E0D3",
        "US_ROUTING_NUMBER": "#E5EED2",
        "SWIFT_BIC": "#DDEBD7",
        "CARD_LAST_FOUR": "#F8DDF1",
        "CARD_TRANSACTION_ID": "#F3E3D5",
        "TRANSFER_TRANSACTION_ID": "#E2E6F5",
        "STATEMENT_REFERENCE": "#DEE7EE",
        "POSTAL_CODE": "#E8DFFF",
        "STREET_ADDRESS": "#FFF1BD",
        "MONEY_AMOUNT": "#DDEFD9",
        "MERCHANT": "#E5E0F5",
        "COUNTERPARTY": "#DCE8F8",
        "TRANSACTION_REFERENCE": "#F4E7D5",
        "BUSINESS_REGISTRATION_NUMBER": "#DEE7EE",
        "INVOICE_NUMBER": "#E2E6F5",
        "PURCHASE_ORDER_ID": "#E5E0F5",
        "CONTRACT_ID": "#D9F0F3",
        "CUSTOMER_ID": "#DCE8F8",
        "EMPLOYEE_ID": "#DDE7FF",
        "CASE_REFERENCE": "#F4E7D5",
        "PROPERTY_IDENTIFIER": "#D9F0F3",
        "CUSTOM": "#E7E9ED",
    }

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

    def write_layout_preserving(
        self,
        source_path: str | Path,
        result: ProtectionResult,
        path: str | Path,
    ) -> Path:
        """Create a safe image-based copy retaining the source page layout.

        Pages are rasterized locally before colored replacements are painted. This
        deliberately removes the original selectable text from the output instead
        of placing an insecure visual rectangle over recoverable PDF text.
        """
        source = Path(source_path)
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        spans_by_finding = {span.finding_id: span for span in result.protected_spans}
        findings_by_page: dict[int, list] = defaultdict(list)
        for finding in result.applied_findings:
            findings_by_page[finding.page_number].append(finding)
        analysis_text_by_page = {
            page_number: (page.extract_text() or "")
            for page_number, page in enumerate(PdfReader(str(source)).pages, start=1)
        }

        unresolved: list[str] = []
        locations_by_page: dict[int, list[tuple[object, object, list[dict]]]] = defaultdict(list)
        temporary = destination.with_name(f".{destination.stem}.building-{os.getpid()}.pdf")
        temporary.unlink(missing_ok=True)

        with pdfplumber.open(source) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                occurrence_by_value: dict[str, int] = defaultdict(int)
                for finding in sorted(
                    findings_by_page.get(page_number, ()), key=lambda item: item.start
                ):
                    span = spans_by_finding.get(finding.finding_id)
                    if span is None:
                        unresolved.append(f"page {page_number}: {finding.text}")
                        continue
                    analysis_text = analysis_text_by_page.get(page_number, "")
                    exact_occurrence = analysis_text[: finding.start].casefold().count(
                        finding.text.casefold()
                    )
                    matches = self._locate_finding(
                        page,
                        finding.text,
                        occurrence_by_value,
                        exact_occurrence=exact_occurrence,
                    )
                    if not matches:
                        unresolved.append(f"page {page_number}: {finding.text}")
                        continue
                    locations_by_page[page_number].append((finding, span, matches))

            if unresolved:
                raise ValueError(
                    "Unable to safely locate every selected value in the original PDF: "
                    + "; ".join(unresolved[:8])
                )

            output = canvas.Canvas(str(temporary))
            try:
                for page_number, page in enumerate(pdf.pages, start=1):
                    rendered = page.to_image(resolution=144, antialias=True).original.convert("RGB")
                    draw = ImageDraw.Draw(rendered)
                    scale_x = rendered.width / float(page.width)
                    scale_y = rendered.height / float(page.height)

                    for finding, span, matches in locations_by_page.get(page_number, ()):
                        label = self._compact_replacement(span.replacement_text, finding.entity_type)
                        if finding.entity_type == "STREET_ADDRESS" and len(matches) > 1:
                            matches = [
                                {
                                    "x0": min(item["x0"] for item in matches),
                                    "top": min(item["top"] for item in matches),
                                    "x1": max(item["x1"] for item in matches),
                                    "bottom": max(item["bottom"] for item in matches),
                                }
                            ]
                        for match in matches:
                            box = (
                                max(0, int(match["x0"] * scale_x) - 2),
                                max(0, int(match["top"] * scale_y) - 2),
                                min(rendered.width, int(match["x1"] * scale_x) + 2),
                                min(rendered.height, int(match["bottom"] * scale_y) + 2),
                            )
                            color = self.ENTITY_COLORS.get(finding.entity_type, "#E7E9ED")
                            draw.rectangle(box, fill=color, outline="#66788A", width=1)
                            self._draw_fitted_text(draw, box, label)
                    output.setPageSize((float(page.width), float(page.height)))
                    output.drawImage(
                        ImageReader(rendered),
                        0,
                        0,
                        width=float(page.width),
                        height=float(page.height),
                    )
                    output.showPage()
                output.save()
            except Exception:
                output._doc = None
                raise
        os.replace(temporary, destination)
        return destination

    @staticmethod
    def _locate_finding(
        page,
        value: str,
        occurrence_by_value: dict[str, int],
        exact_occurrence: int | None = None,
    ) -> list[dict]:
        """Map an analyzed value to one or more visual boxes on a PDF page."""
        search_value = value.strip()
        key = search_value.casefold()
        exact_matches = page.search(re.escape(search_value), regex=True, case=False)
        occurrence = (
            exact_occurrence if exact_occurrence is not None else occurrence_by_value[key]
        )
        if exact_occurrence is None:
            occurrence_by_value[key] += 1
        if occurrence < len(exact_matches):
            return [exact_matches[occurrence]]
        if exact_matches:
            # Text extraction may contain duplicated logical rows which do not
            # exist as separate visual occurrences. Cover every visible match
            # rather than rejecting an otherwise safe image-based export.
            return exact_matches

        # Some PDF extractors join adjacent columns with a newline. Locate and
        # protect every meaningful fragment rather than silently leaving one visible.
        fragments = [part.strip() for part in search_value.splitlines() if part.strip()]
        if len(fragments) <= 1:
            # Table extraction commonly joins adjacent PDF cells as
            # "Tenant name / Unit" even though they are visually separate.
            fragments = [
                part.strip()
                for part in re.split(r"\s+/\s+", search_value)
                if part.strip()
            ]
        if len(fragments) <= 1:
            return []
        located: list[dict] = []
        for fragment in fragments:
            fragment_key = fragment.casefold()
            fragment_matches = page.search(re.escape(fragment), regex=True, case=False)
            fragment_occurrence = occurrence_by_value.get(fragment_key, 0)
            occurrence_by_value[fragment_key] = fragment_occurrence + 1
            if fragment_occurrence >= len(fragment_matches):
                return []
            located.append(fragment_matches[fragment_occurrence])
        return located

    @staticmethod
    def _compact_replacement(replacement: str, entity_type: str) -> str:
        if replacement.startswith("[[PG_") and replacement.endswith("]]" ):
            suffix = replacement[5:-2]
            aliases = {
                "US_ROUTING_NUMBER": "ROUTING",
                "US_BANK_NUMBER": "ACCOUNT",
                "EMAIL_ADDRESS": "EMAIL",
                "PHONE_NUMBER": "PHONE",
                "CREDIT_CARD": "CARD",
                "PROPERTY_IDENTIFIER": "PROPERTY",
                "MONEY_AMOUNT": "AMOUNT",
                "CARD_LAST_FOUR": "CARD_LAST4",
                "CARD_TRANSACTION_ID": "CARD_TX",
                "TRANSFER_TRANSACTION_ID": "TRANSFER_TX",
                "TRANSACTION_REFERENCE": "REFERENCE",
                "STATEMENT_REFERENCE": "STATEMENT_REF",
                "STREET_ADDRESS": "ADDRESS",
                "BUSINESS_REGISTRATION_NUMBER": "REG_NO",
                "SWIFT_BIC": "SWIFT",
            }
            for original, short in aliases.items():
                if suffix.startswith(original + "_"):
                    suffix = short + suffix[len(original) :]
                    break
            return suffix
        if replacement.startswith("[[") and replacement.endswith("]]" ):
            return replacement[2:-2].replace("US_", "")
        if replacement == "[REDACTED]":
            return "REDACTED"
        return replacement

    @staticmethod
    def _draw_fitted_text(
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        text: str,
        *,
        align: str = "center",
    ) -> None:
        left, top, right, bottom = box
        available_width = max(5, right - left - 4)
        available_height = max(5, bottom - top - 2)
        windows_font = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arialbd.ttf"
        font_size = max(6, min(22, int(available_height * 0.82)))
        font = None
        while font_size >= 5:
            try:
                font = ImageFont.truetype(str(windows_font), font_size)
            except OSError:
                font = ImageFont.load_default()
                break
            bounds = draw.textbbox((0, 0), text, font=font)
            if bounds[2] - bounds[0] <= available_width and bounds[3] - bounds[1] <= available_height:
                break
            font_size -= 1
        bounds = draw.textbbox((0, 0), text, font=font)
        text_width = bounds[2] - bounds[0]
        text_height = bounds[3] - bounds[1]
        x = left + 2 if align == "left" else left + max(2, (right - left - text_width) / 2)
        draw.text(
            (x, top + max(0, (bottom - top - text_height) / 2 - bounds[1])),
            text,
            fill="#102A43",
            font=font,
        )

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
