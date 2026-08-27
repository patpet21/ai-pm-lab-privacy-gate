from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


NAVY = "#062B4F"
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

    text_compare = getattr(page, "_privacygate_text_compare_protected", None)
    if text_compare is not None:
        text_compare.clear()

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


def _restore_action_dock_under_documents(page) -> None:
    """Keep one Scan/Protect dock directly below the document comparison cards."""
    preview_card = getattr(page, "preview_card", None)
    preview_layout = preview_card.layout() if preview_card is not None else None
    action_bar = getattr(page, "_polish_protect_bottom_bar", None)
    preview_tabs = getattr(page, "preview_tabs", None)
    if not isinstance(preview_layout, QVBoxLayout) or action_bar is None:
        return

    preview_layout.removeWidget(action_bar)
    insert_at = preview_layout.count()
    if preview_tabs is not None:
        tab_index = preview_layout.indexOf(preview_tabs)
        if tab_index >= 0:
            insert_at = tab_index + 1
    preview_layout.insertWidget(insert_at, action_bar)
    action_bar.setMaximumHeight(16777215)
    action_bar.show()

    # The upper quick-source strip is for choosing a source only. Scan and
    # Protect belong below the document cards, so do not duplicate them above.
    for name in ("_protect_source_scan", "_protect_source_protect"):
        duplicate = getattr(page, name, None)
        if duplicate is not None:
            duplicate.hide()

    protect_button = getattr(page, "_redesign_protect_button", None)
    if protect_button is not None:
        protect_button.show()

    # Keep the cards useful but compact enough that their action dock is reachable
    # without traversing an oversized multi-page preview. The PDF/Office viewers
    # remain internally scrollable and Full document view can still expand them.
    if preview_card is not None:
        preview_card.setMinimumHeight(650)
    if preview_tabs is not None:
        preview_tabs.setMinimumHeight(500)
    splitter = getattr(page, "document_preview_splitter", None)
    if splitter is not None:
        splitter.setMinimumHeight(430)


def _install_text_email_compare(page) -> None:
    """Render pasted text and Gmail email in the same Original/Protected compare UI."""
    if bool(getattr(page, "_privacygate_text_compare_installed", False)):
        return

    protected_panel = getattr(page, "protected_document_panel", None)
    protected_stack = getattr(page, "protected_view_stack", None)
    if protected_panel is None or protected_stack is None:
        return
    protected_layout = protected_panel.layout()
    if not isinstance(protected_layout, QVBoxLayout):
        return

    page._privacygate_text_compare_installed = True

    protected_text = QPlainTextEdit(protected_panel)
    protected_text.setReadOnly(True)
    protected_text.setPlaceholderText(
        "Protected text will appear here after you click Protect document."
    )
    protected_text.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    protected_text.setMinimumHeight(360)
    protected_text.setStyleSheet(
        "QPlainTextEdit{background:#FFFFFF;color:#17384E;border:1px solid #CFDBE5;"
        "border-radius:8px;padding:14px;font-size:13px;}"
    )
    protected_layout.addWidget(protected_text, 1)
    protected_text.hide()
    page._privacygate_text_compare_protected = protected_text

    def text_mode() -> bool:
        return bool(
            page.input_tabs.currentIndex() == 0
            and not page.pdf_path.text().strip()
        )

    def refresh_compare() -> None:
        if text_mode():
            protected_stack.hide()
            protected_text.show()
            result = getattr(page, "current_result", None)
            protected_text.setPlainText(result.combined_text if result is not None else "")
            page.preview_tabs.setTabVisible(1, True)
            page.comparison_note.setText(
                "Original text or email on the left. Protected text on the right."
            )
            try:
                page._set_pdf_controls_enabled(False)
            except Exception:
                pass
        else:
            protected_text.hide()
            protected_stack.show()
            document = getattr(page, "current_document", None)
            if document is not None and document.source_kind in {"pdf", "docx", "xlsx"}:
                page.preview_tabs.setTabVisible(1, True)

    # Refresh after the existing scan/protect handlers so this view always follows
    # the same controller state rather than maintaining a second protection flow.
    original_analysis_ready = page._analysis_ready

    def analysis_ready(self, payload: object) -> None:
        original_analysis_ready(payload)
        QTimer.singleShot(0, refresh_compare)

    page._analysis_ready = MethodType(analysis_ready, page)

    original_refresh_preview = page._refresh_preview

    def refresh_preview(self, *args, **kwargs):
        result = original_refresh_preview(*args, **kwargs)
        QTimer.singleShot(0, refresh_compare)
        return result

    page._refresh_preview = MethodType(refresh_preview, page)

    page.text_input.textChanged.connect(lambda: QTimer.singleShot(0, refresh_compare))
    page.pdf_path.textChanged.connect(lambda _value: QTimer.singleShot(0, refresh_compare))

    document_mode = getattr(page, "_redesign_document_mode", None)
    paste_mode = getattr(page, "_redesign_paste_mode", None)
    if document_mode is not None:
        document_mode.clicked.connect(lambda: QTimer.singleShot(0, refresh_compare))
    if paste_mode is not None:
        paste_mode.clicked.connect(lambda: QTimer.singleShot(0, refresh_compare))

    protect_button = getattr(page, "_redesign_protect_button", None)
    if protect_button is not None:
        protect_button.clicked.connect(lambda: QTimer.singleShot(0, refresh_compare))

    QTimer.singleShot(0, refresh_compare)


def apply_protect_workflow_visibility_fix(main_window) -> None:
    """Keep the established file workflow primary and make Compare source-safe."""
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_privacygate_protect_workflow_visibility_fixed", False)):
        return

    summary = getattr(page, "_privacygate_managed_mockup", None)
    original_shell = getattr(page, "_privacygate_original_protect_shell", None)
    if summary is None or original_shell is None:
        return

    page._privacygate_protect_workflow_visibility_fixed = True

    _restore_action_dock_under_documents(page)
    _install_source_isolation(page)
    _install_text_email_compare(page)

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
    back_note = QLabel(
        "Preflight summary · your original Protect controls and current file remain available."
    )
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
        banner.setVisible(
            available and bool(getattr(page, "_privacygate_force_original_protect", True))
        )
        back_bar.setVisible(
            available and not bool(getattr(page, "_privacygate_force_original_protect", True))
        )

    summary.render = MethodType(render_with_navigation, summary)
    summary.render()
