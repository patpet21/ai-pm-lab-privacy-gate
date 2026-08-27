from __future__ import annotations

from types import MethodType

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


NAVY = "#062B4F"
TEAL = "#0B7180"
MUTED = "#61798A"
BORDER = "#D7E2EA"


def _summary_available(page, original_should_show) -> bool:
    try:
        return bool(original_should_show())
    except Exception:
        return False


def _reset_stale_source_state(page) -> None:
    """Invalidate the previous source without clearing the newly selected input."""
    page.current_document = None
    page.current_findings = ()
    page.current_result = None
    page._last_residual = ()

    table = getattr(page, "findings_table", None)
    if table is not None:
        table.blockSignals(True)
        try:
            table.setRowCount(0)
        finally:
            table.blockSignals(False)

    categories = getattr(page, "category_list", None)
    if categories is not None:
        categories.clear()

    preview = getattr(page, "preview", None)
    if preview is not None:
        preview.clear()

    for document_name in ("original_pdf_document", "protected_pdf_document"):
        document = getattr(page, document_name, None)
        if document is not None:
            try:
                document.close()
            except Exception:
                pass

    for view_name in ("original_office_view", "protected_office_view"):
        view = getattr(page, view_name, None)
        if view is not None:
            try:
                view.clear()
            except Exception:
                pass

    if hasattr(page, "_redesign_protected_metric"):
        page._redesign_protected_metric.setText("0 protected")
    if hasattr(page, "_redesign_review_metric"):
        page._redesign_review_metric.setText("Ready to scan")
    if hasattr(page, "_redesign_protect_button"):
        page._redesign_protect_button.setEnabled(False)
        page._redesign_protect_button.setText("Protect document")
    if hasattr(page, "_redesign_final_actions"):
        page._redesign_final_actions.hide()
    if hasattr(page, "_redesign_set_final_actions"):
        page._redesign_set_final_actions(False)

    quick_actions = getattr(page, "_protect_quick_actions", None)
    if quick_actions is not None:
        quick_actions.hide()


def _install_source_isolation(page) -> None:
    """Make document and pasted/email sources mutually exclusive."""
    if bool(getattr(page, "_privacygate_source_isolation_installed", False)):
        return
    page._privacygate_source_isolation_installed = True
    page._privacygate_source_reset_guard = False

    def clear_provenance() -> None:
        page._external_source_name = ""
        page._external_source_metadata = {}

    def text_changed() -> None:
        if bool(getattr(page, "_privacygate_source_reset_guard", False)):
            return
        if not page.text_input.toPlainText().strip():
            return
        page._privacygate_source_reset_guard = True
        try:
            if page.pdf_path.text().strip():
                page.pdf_path.clear()
            clear_provenance()
            _reset_stale_source_state(page)
        finally:
            page._privacygate_source_reset_guard = False

    def file_changed(path: str) -> None:
        if bool(getattr(page, "_privacygate_source_reset_guard", False)):
            return
        if not str(path or "").strip():
            return
        page._privacygate_source_reset_guard = True
        try:
            if page.text_input.toPlainText():
                page.text_input.clear()
            clear_provenance()
            _reset_stale_source_state(page)
        finally:
            page._privacygate_source_reset_guard = False

    page.text_input.textChanged.connect(text_changed)
    page.pdf_path.textChanged.connect(file_changed)


def _keep_protect_actions_visible(page) -> None:
    """Keep Scan/Protect controls above the long document preview."""
    preview_card = getattr(page, "preview_card", None)
    preview_layout = preview_card.layout() if preview_card is not None else None
    action_bar = getattr(page, "_polish_protect_bottom_bar", None)
    mode_bar = getattr(page, "_polish_protect_mode_bar", None)
    if not isinstance(preview_layout, QVBoxLayout) or action_bar is None:
        return

    preview_layout.removeWidget(action_bar)
    insert_at = 0
    if mode_bar is not None:
        mode_index = preview_layout.indexOf(mode_bar)
        if mode_index >= 0:
            insert_at = mode_index + 1
    preview_layout.insertWidget(insert_at, action_bar)
    action_bar.setMaximumHeight(16777215)
    action_bar.show()

    protect_button = getattr(page, "_redesign_protect_button", None)
    if protect_button is not None:
        protect_button.show()


def apply_protect_workflow_visibility_fix(main_window) -> None:
    """Keep Protect usable while exposing managed Preflight as a secondary view."""
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_privacygate_protect_workflow_visibility_fixed", False)):
        return

    summary = getattr(page, "_privacygate_managed_mockup", None)
    original_shell = getattr(page, "_privacygate_original_protect_shell", None)
    if summary is None or original_shell is None:
        return

    page._privacygate_protect_workflow_visibility_fixed = True

    # Keep the existing Scan/Protect dock above long previews so it never appears
    # to disappear after a scan.
    _keep_protect_actions_visible(page)

    # Gmail/pasted text and local/Drive documents are mutually exclusive. Clear
    # the previous renderer state when the source changes so stale PDFs cannot
    # survive into a text/email scan.
    _install_source_isolation(page)

    page._privacygate_force_original_protect = True

    original_should_show = summary.should_show
    original_render = summary.render

    def should_show(self) -> bool:
        return bool(
            _summary_available(page, original_should_show)
            and not bool(getattr(page, "_privacygate_force_original_protect", True))
        )

    summary.should_show = MethodType(should_show, summary)

    banner = QFrame(objectName="ManagedPreflightSummaryBanner")
    banner.setStyleSheet(
        "QFrame#ManagedPreflightSummaryBanner{background:#F2FAFA;border:1px solid #CDE7E9;"
        "border-radius:10px;}"
    )
    banner_row = QHBoxLayout(banner)
    banner_row.setContentsMargins(12, 8, 12, 8)
    banner_row.setSpacing(10)

    copy = QVBoxLayout()
    copy.setContentsMargins(0, 0, 0, 0)
    copy.setSpacing(1)
    heading = QLabel("Managed Privacy Preflight available")
    heading.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:900;")
    detail = QLabel(
        "Keep working with your file here, or open the company-policy summary before AI handoff."
    )
    detail.setWordWrap(True)
    detail.setStyleSheet(f"color:{MUTED};font-size:8px;")
    copy.addWidget(heading)
    copy.addWidget(detail)
    banner_row.addLayout(copy, 1)

    open_summary = QPushButton("View Preflight summary")
    open_summary.setMinimumHeight(34)
    open_summary.setStyleSheet(
        "QPushButton{background:#0B7180;color:#FFFFFF;border:none;border-radius:8px;"
        "padding:7px 12px;font-size:9px;font-weight:900;}"
        "QPushButton:hover{background:#096672;}"
    )
    banner_row.addWidget(open_summary, alignment=Qt.AlignmentFlag.AlignVCenter)

    original_layout = original_shell.layout()
    if isinstance(original_layout, QVBoxLayout):
        original_layout.insertWidget(0, banner)
    else:
        banner.hide()

    back_bar = QFrame(objectName="ManagedPreflightBackBar")
    back_bar.setStyleSheet(
        f"QFrame#ManagedPreflightBackBar{{background:#FFFFFF;border:1px solid {BORDER};border-radius:9px;}}"
    )
    back_row = QHBoxLayout(back_bar)
    back_row.setContentsMargins(10, 7, 10, 7)
    back_row.setSpacing(9)
    back_note = QLabel("Preflight summary · your original Protect controls and current file remain available.")
    back_note.setWordWrap(True)
    back_note.setStyleSheet(f"color:{MUTED};font-size:8px;")
    back_button = QPushButton("← Back to Protect / Files")
    back_button.setMinimumHeight(34)
    back_button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:8px;"
        "padding:7px 12px;font-size:9px;font-weight:850;}"
        "QPushButton:hover{background:#F2FAFA;border-color:#96C9CD;color:#0B7180;}"
    )
    back_row.addWidget(back_button)
    back_row.addWidget(back_note, 1)

    summary_layout = summary.layout()
    if isinstance(summary_layout, QVBoxLayout):
        summary_layout.insertWidget(1, back_bar)
    else:
        back_bar.hide()

    def show_summary() -> None:
        if not _summary_available(page, original_should_show):
            return
        page._privacygate_force_original_protect = False
        summary.render()

    def show_protect() -> None:
        page._privacygate_force_original_protect = True
        summary.render()

    open_summary.clicked.connect(show_summary)
    back_button.clicked.connect(show_protect)

    def render_with_navigation(self) -> None:
        original_render()
        available = _summary_available(page, original_should_show)
        banner.setVisible(available and bool(getattr(page, "_privacygate_force_original_protect", True)))
        back_bar.setVisible(available and not bool(getattr(page, "_privacygate_force_original_protect", True)))

    summary.render = MethodType(render_with_navigation, summary)
    summary.render()
