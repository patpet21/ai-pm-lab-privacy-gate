from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "PRIVACY_GATE_DATA_DIR",
    str((Path(tempfile.gettempdir()) / "privacy-gate-ui-smoke" / uuid.uuid4().hex).resolve()),
)

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import PageContent
from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService
from ai_pm_lab_privacy_gate.ui.main_window import MainWindow
from ai_pm_lab_privacy_gate.ui.fonts import install_app_font
from ai_pm_lab_privacy_gate.ui.styles import APP_STYLE


def main() -> int:
    output_dir = Path(tempfile.gettempdir()) / "privacy-gate-ui-smoke-output"
    output = output_dir / "privacy_gate_main.png"
    collapsed_output = output_dir / "privacy_gate_collapsed.png"
    library_output = output_dir / "privacy_gate_library.png"
    mask_output = output_dir / "privacy_gate_mask_colors.png"
    pdf_output = output_dir / "privacy_gate_pdf_comparison.png"
    focus_output = output_dir / "privacy_gate_focus_preview.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    install_app_font(app)
    app.setStyleSheet(APP_STYLE)
    service = PrivacyGateService()
    document = service.document_from_text(
        "Tenant Jane Smith can be reached at jane.smith@example.com or 212-555-5555. "
        "Social Security Number: 219-09-9999."
    )
    window = MainWindow(service=service)
    page = window.protection_page
    findings = service.analyze(document, page._current_profile())
    page.text_input.setPlainText(document.pages[0].text)
    page._analysis_ready((document, findings))
    window.show()
    app.processEvents()
    if not window.grab().save(str(output)):
        raise RuntimeError("Unable to save UI screenshot")
    page.mode_combo.setCurrentIndex(page.mode_combo.findData("mask"))
    app.processEvents()
    if not page.current_result or len(page.current_result.combined_spans) != len(findings):
        raise RuntimeError("Mask-mode color metadata is incomplete")
    if not window.grab().save(str(mask_output)):
        raise RuntimeError("Unable to save mask color screenshot")

    source_pdf = output_dir / "privacy_gate_source.pdf"
    PdfDocumentService().write_protected(
        (
            PageContent(1, "Tenant Jane Smith\nEmail jane.smith@example.com\nPhone 212-555-5555"),
            PageContent(2, "Social Security Number 219-09-9999"),
        ),
        source_pdf,
    )
    pdf_document = service.document_from_pdf(source_pdf)
    pdf_findings = service.analyze(pdf_document, page._current_profile())
    page.pdf_path.setText(str(source_pdf.resolve()))
    page.input_tabs.setCurrentIndex(1)
    page._analysis_ready((pdf_document, pdf_findings))
    page.preview_tabs.setCurrentIndex(1)
    QTest.qWait(900)
    app.processEvents()
    if page.original_pdf_document.pageCount() != 2 or page.protected_pdf_document.pageCount() != 2:
        raise RuntimeError("PDF comparison did not load both two-page documents")
    if not window.grab().save(str(pdf_output)):
        raise RuntimeError("Unable to save PDF comparison screenshot")
    page.focus_preview_button.setChecked(True)
    app.processEvents()
    if page.findings_card.isVisible() or page.setup_card.isVisible():
        raise RuntimeError("Focus preview did not hide the review panels")
    if not window.grab().save(str(focus_output)):
        raise RuntimeError("Unable to save focused preview screenshot")
    page.focus_preview_button.setChecked(False)

    window._toggle_sidebar()
    app.processEvents()
    if window.sidebar.width() != 76:
        raise RuntimeError("Sidebar did not collapse to the expected width")
    if any(button.text() or button.icon().isNull() for button in window.nav_buttons):
        raise RuntimeError("Collapsed navigation must use recognizable icons without initials")
    if not window.grab().save(str(collapsed_output)):
        raise RuntimeError("Unable to save collapsed UI screenshot")
    result = service.protect(document, findings)
    saved = window.library.save(
        title="Lease 014 - Jane Smith",
        source_kind="text",
        source_name="Pasted text",
        profile_key="property_management",
        result=result,
        labels=("Lease", "Property 014"),
    )
    window.library.set_favorite(saved.document_id, True)
    window._toggle_sidebar()
    window._show_page(1)
    app.processEvents()
    if not window.library_page.backup_button.isEnabled():
        raise RuntimeError("Library backup action is unavailable")
    if not window.grab().save(str(library_output)):
        raise RuntimeError("Unable to save library UI screenshot")
    print(
        f"UI_OK {output.resolve()} {mask_output.resolve()} {pdf_output.resolve()} "
        f"{focus_output.resolve()} {collapsed_output.resolve()} {library_output.resolve()} "
        f"{len(findings)} findings sidebar={window.sidebar.width()}"
    )
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
