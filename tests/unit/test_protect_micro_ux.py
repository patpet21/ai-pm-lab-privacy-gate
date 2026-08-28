import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _sample_result():
    from ai_pm_lab_privacy_gate.domain.models import PageContent, ProtectedSpan, ProtectionResult

    text = "Contact [[PG_PERSON_001]] at [[PG_EMAIL_ADDRESS_001]]"
    person = "[[PG_PERSON_001]]"
    email = "[[PG_EMAIL_ADDRESS_001]]"
    person_start = text.index(person)
    email_start = text.index(email)
    return ProtectionResult(
        protected_pages=(PageContent(page_number=1, text=text),),
        protected_spans=(
            ProtectedSpan(
                page_number=1,
                start=person_start,
                end=person_start + len(person),
                entity_type="PERSON",
                finding_id="person",
                replacement_text=person,
            ),
            ProtectedSpan(
                page_number=1,
                start=email_start,
                end=email_start + len(email),
                entity_type="EMAIL_ADDRESS",
                finding_id="email",
                replacement_text=email,
            ),
        ),
    )


def _namespaced_result():
    result = _sample_result()
    person = "[[PG_GMAIL1_PERSON_001]]"
    email = "[[PG_GMAIL1_EMAIL_ADDRESS_001]]"
    text = result.combined_text.replace("[[PG_PERSON_001]]", person).replace(
        "[[PG_EMAIL_ADDRESS_001]]", email
    )
    # Deliberately retain the pre-namespace numeric offsets. The visual layer
    # must use exact replacement tokens rather than depending on stale offsets.
    spans = (
        replace(result.protected_spans[0], replacement_text=person),
        replace(result.protected_spans[1], replacement_text=email),
    )
    return replace(
        result,
        protected_pages=(replace(result.protected_pages[0], text=text),),
        protected_spans=spans,
    )


def test_colored_reflow_markup_uses_entity_palette():
    from ai_pm_lab_privacy_gate.infrastructure.documents.colored_reflow_pdf import (
        _styled_line_markup,
    )
    from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService

    result = _sample_result()
    text = result.protected_pages[0].text
    markup = _styled_line_markup(
        text,
        0,
        len(text),
        result.protected_spans,
        PdfDocumentService.ENTITY_COLORS,
    )

    assert 'backColor="#DDE7FF"' in markup
    assert 'backColor="#D9F3EE"' in markup
    assert "[[PG_PERSON_001]]" in markup
    assert "[[PG_EMAIL_ADDRESS_001]]" in markup


def test_colored_reflow_markup_keeps_category_after_namespace():
    from ai_pm_lab_privacy_gate.infrastructure.documents.colored_reflow_pdf import (
        _styled_line_markup,
    )
    from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService

    result = _namespaced_result()
    text = result.combined_text
    markup = _styled_line_markup(
        text,
        0,
        len(text),
        result.protected_spans,
        PdfDocumentService.ENTITY_COLORS,
    )

    assert 'backColor="#DDE7FF"' in markup
    assert 'backColor="#D9F3EE"' in markup
    assert "[[PG_GMAIL1_PERSON_001]]" in markup
    assert "[[PG_GMAIL1_EMAIL_ADDRESS_001]]" in markup


def test_colored_reflow_pdf_builds(tmp_path):
    from pypdf import PdfReader

    from ai_pm_lab_privacy_gate.infrastructure.documents.colored_reflow_pdf import (
        write_colored_reflow_pdf,
    )
    from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService

    output = write_colored_reflow_pdf(
        PdfDocumentService(),
        _namespaced_result(),
        tmp_path / "protected.pdf",
    )

    assert output.exists()
    assert output.stat().st_size > 0
    extracted = "\n".join((page.extract_text() or "") for page in PdfReader(str(output)).pages)
    assert "PG_GMAIL1_PERSON_001" in extracted
    assert "PG_GMAIL1_EMAIL_ADDRESS_001" in extracted


def test_protected_text_token_colors_use_existing_palette():
    from types import SimpleNamespace

    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QApplication, QPlainTextEdit

    from ai_pm_lab_privacy_gate.ui.protect_micro_ux import _apply_result_token_colors

    app = QApplication.instance() or QApplication([])
    result = _namespaced_result()
    editor = QPlainTextEdit()
    editor.setPlainText(result.combined_text)
    page = SimpleNamespace(
        preview=editor,
        _entity_color=lambda entity: {
            "PERSON": "#DDE7FF",
            "EMAIL_ADDRESS": "#D9F3EE",
        }[entity],
    )

    _apply_result_token_colors(page, result)
    app.processEvents()

    person_position = result.combined_text.index("[[PG_GMAIL1_PERSON_001]]") + 2
    email_position = result.combined_text.index("[[PG_GMAIL1_EMAIL_ADDRESS_001]]") + 2

    person_cursor = QTextCursor(editor.document())
    person_cursor.setPosition(person_position)
    email_cursor = QTextCursor(editor.document())
    email_cursor.setPosition(email_position)

    assert person_cursor.charFormat().background().color().name().upper() == "#DDE7FF"
    assert email_cursor.charFormat().background().color().name().upper() == "#D9F3EE"

    editor.close()


def test_namespace_aware_office_palette_resolves_real_category():
    from ai_pm_lab_privacy_gate.ui.protect_micro_ux import _NamespaceAwareColors

    palette = _NamespaceAwareColors(
        {
            "PERSON": "#DDE7FF",
            "EMAIL_ADDRESS": "#D9F3EE",
            "PROPERTY_IDENTIFIER": "#D9F0F3",
        }
    )

    assert palette.get("GMAIL1_PERSON") == "#DDE7FF"
    assert palette.get("S2_EMAIL_ADDRESS") == "#D9F3EE"
    assert palette.get("S1_DOCUMENT_PROPERTY_IDENTIFIER") == "#D9F0F3"
