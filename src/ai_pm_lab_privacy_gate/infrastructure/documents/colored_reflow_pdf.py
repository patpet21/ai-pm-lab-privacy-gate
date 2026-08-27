from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from ai_pm_lab_privacy_gate.domain.models import ProtectedSpan, ProtectionResult


def _replacement_entities(spans: tuple[ProtectedSpan, ...]) -> dict[str, str]:
    """Map exact replacement tokens to their real category, ignoring namespaces."""

    categories: dict[str, set[str]] = {}
    for span in spans:
        token = str(span.replacement_text or "")
        if not token:
            continue
        categories.setdefault(token, set()).add(span.entity_type)
    return {
        token: next(iter(values)) if len(values) == 1 else "REDACTED"
        for token, values in categories.items()
    }


def _styled_line_markup(
    text: str,
    line_start: int,
    line_end: int,
    spans: tuple[ProtectedSpan, ...],
    entity_colors: Mapping[str, str],
) -> str:
    """Return category-colored markup using exact replacement tokens.

    Multi-source sessions deliberately add namespaces to reversible placeholders
    (for example ``PG_GMAIL1_PERSON``). Exact token matching keeps the visual
    category tied to ``PERSON`` even if legacy span offsets predate that namespace.
    """

    line = text[line_start:line_end]
    token_entities = _replacement_entities(spans)
    if not token_entities:
        return escape(line)
    tokens = sorted(token_entities, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(token) for token in tokens))
    cursor = 0
    chunks: list[str] = []
    for match in pattern.finditer(line):
        if match.start() > cursor:
            chunks.append(escape(line[cursor : match.start()]))
        token = match.group(0)
        entity = token_entities[token]
        color = entity_colors.get(entity, "#E7E9ED")
        chunks.append(
            f'<font backColor="{color}" color="#102A43"><b>{escape(token)}</b></font>'
        )
        cursor = match.end()
    if cursor < len(line):
        chunks.append(escape(line[cursor:]))
    return "".join(chunks)


def write_colored_reflow_pdf(
    pdf_service,
    result: ProtectionResult,
    path: str | Path,
) -> Path:
    """Write the safe-reflow fallback while preserving category color semantics.

    The layout-preserving PDF path already paints replacements with entity colors.
    This renderer gives the fallback/reflow path the same visual language without
    changing placeholder text, mappings, namespaces, or restore behavior.
    """

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    font_name = pdf_service._register_windows_font()
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "PrivacyGateColoredReflowBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9.5,
        leading=13,
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    heading = ParagraphStyle(
        "PrivacyGateColoredReflowHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=12,
        leading=15,
        textColor="#16324F",
        spaceAfter=10,
    )
    document = SimpleDocTemplate(
        str(destination),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.65 * inch,
        title="Protected copy - AI PM LAB Privacy Gate",
        author="AI PM LAB Privacy Gate",
    )

    spans_by_page: dict[int, tuple[ProtectedSpan, ...]] = {}
    for page in result.protected_pages:
        spans_by_page[page.page_number] = tuple(
            span for span in result.protected_spans if span.page_number == page.page_number
        )

    story = []
    for page_index, page in enumerate(result.protected_pages):
        story.append(
            Paragraph(f"Protected copy - source page {page.page_number}", heading)
        )
        offset = 0
        raw_lines = page.text.splitlines(keepends=True)
        if not raw_lines and page.text:
            raw_lines = [page.text]
        for raw_line in raw_lines:
            line = raw_line.rstrip("\r\n")
            line_end = offset + len(line)
            if line.strip():
                markup = _styled_line_markup(
                    page.text,
                    offset,
                    line_end,
                    spans_by_page.get(page.page_number, ()),
                    pdf_service.ENTITY_COLORS,
                )
                story.append(Paragraph(markup, body))
            else:
                story.append(Spacer(1, 5))
            offset += len(raw_line)
        if page_index < len(result.protected_pages) - 1:
            story.append(PageBreak())

    document.build(
        story,
        onFirstPage=pdf_service._footer,
        onLaterPages=pdf_service._footer,
    )
    return destination
