import os

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


def test_colored_reflow_pdf_builds(tmp_path):
    from pypdf import PdfReader

    from ai_pm_lab_privacy_gate.infrastructure.documents.colored_reflow_pdf import (
        write_colored_reflow_pdf,
    )
    from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService

    output = write_colored_reflow_pdf(
        PdfDocumentService(),
        _sample_result(),
        tmp_path / "protected.pdf",
    )

    assert output.exists()
    assert output.stat().st_size > 0
    extracted = "\n".join((page.extract_text() or "") for page in PdfReader(str(output)).pages)
    assert "PG_PERSON_001" in extracted
    assert "PG_EMAIL_ADDRESS_001" in extracted


def test_protected_text_token_colors_use_existing_palette():
    from types import SimpleNamespace

    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QApplication, QPlainTextEdit

    from ai_pm_lab_privacy_gate.ui.protect_micro_ux import _apply_result_token_colors

    app = QApplication.instance() or QApplication([])
    result = _sample_result()
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

    person_position = result.combined_text.index("[[PG_PERSON_001]]") + 2
    email_position = result.combined_text.index("[[PG_EMAIL_ADDRESS_001]]") + 2

    person_cursor = QTextCursor(editor.document())
    person_cursor.setPosition(person_position)
    email_cursor = QTextCursor(editor.document())
    email_cursor.setPosition(email_position)

    assert person_cursor.charFormat().background().color().name().upper() == "#DDE7FF"
    assert email_cursor.charFormat().background().color().name().upper() == "#D9F3EE"

    editor.close()
