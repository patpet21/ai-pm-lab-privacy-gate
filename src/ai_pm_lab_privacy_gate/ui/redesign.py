from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


_INSTALLED = False


class _UploadDropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__(objectName="RedesignUploadZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @staticmethod
    def _supported(path: str) -> bool:
        return Path(path).suffix.lower() in {".pdf", ".docx", ".xlsx"}

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if urls and urls[0].isLocalFile() and self._supported(urls[0].toLocalFile()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if urls and urls[0].isLocalFile():
            path = urls[0].toLocalFile()
            if self._supported(path):
                self.file_dropped.emit(path)
                event.acceptProposedAction()
                return
        event.ignore()


def _pill(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        "QLabel{background:#eefaf8;color:#087d72;border:1px solid #d4ece8;"
        "border-radius:10px;padding:8px 13px;font-weight:700;}"
    )
    return label


def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-size:15px;font-weight:700;color:#0a2940;")
    return label


def _make_help_card() -> QFrame:
    card = QFrame(objectName="RedesignHelpCard")
    card.setMinimumWidth(270)
    card.setMaximumWidth(300)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)

    title = QLabel("How restore works")
    title.setStyleSheet("font-size:16px;font-weight:800;color:#0a2940;")
    layout.addWidget(title)

    intro = QLabel(
        "Protect with reversible placeholders, use the safe copy with AI, "
        "then restore the final answer locally."
    )
    intro.setWordWrap(True)
    intro.setStyleSheet("color:#6b7d8e;font-size:12px;")
    layout.addWidget(intro)

    steps = (
        ("1", "Protect with reversible placeholders",
         "Sensitive values become local reversible tokens."),
        ("2", "Send the protected version to AI",
         "Only protected content needs to leave Privacy Gate."),
        ("3", "Paste the AI response in Restore",
         "Open Restore and paste the AI output."),
        ("4", "Restore original values locally",
         "The original values are restored on this device."),
    )
    for number, heading, body in steps:
        row = QHBoxLayout()
        row.setSpacing(10)
        badge = QLabel(number)
        badge.setFixedSize(24, 24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            "background:#0a9b98;color:white;border-radius:12px;font-weight:800;"
        )
        text = QLabel(
            f"<b>{heading}</b><br>"
            f"<span style='color:#66788a;font-size:11px'>{body}</span>"
        )
        text.setWordWrap(True)
        row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        row.addWidget(text, 1)
        layout.addLayout(row)

    layout.addStretch(1)
    note = QLabel(
        "100% local restore\nOriginal values never need to be sent to AI."
    )
    note.setWordWrap(True)
    note.setStyleSheet(
        "background:#eefaf8;border:1px solid #d5eeea;border-radius:9px;"
        "padding:11px;color:#28645f;font-size:11px;"
    )
    layout.addWidget(note)
    return card


def _hide_old_root(root) -> None:
    """Remove the legacy visual tree from the page without deleting reusable widgets."""
    while root.count():
        item = root.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
        child_layout = item.layout()
        if child_layout is not None:
            for index in range(child_layout.count()):
                child_widget = child_layout.itemAt(index).widget()
                if child_widget is not None:
                    child_widget.hide()


def _reparent(widget: QWidget, parent: QWidget) -> None:
    widget.hide()
    widget.setParent(parent)
    widget.show()


def _open_restore_page(page: ProtectionPage) -> None:
    window = page.window()
    show_page = getattr(window, "_show_page", None)
    if callable(show_page):
        show_page(2)


def _apply_redesign(page: ProtectionPage) -> None:
    # Preserve references to all functional legacy widgets before rebuilding the layout.
    root = page.layout()
    _hide_old_root(root)

    page.setup_toggle.hide()
    page.setup_card.hide()
    page.local_badge.hide()
    page.types_metric.hide()
    page.pages_metric.hide()
    page.source_metric.hide()

    # Reparent the widgets that remain the single source of truth for the existing engine.
    holder = QWidget(page)
    for widget in (
        page.text_input,
        page.profile_combo,
        page.scope_combo,
        page.mode_combo,
        page.threshold_input,
        page.pdf_path,
        page.browse_button,
        page.scan_button,
        page.clear_button,
        page.workspace,
        page.findings_metric,
        page.verification_metric,
    ):
        _reparent(widget, holder)

    page.pdf_path.hide()
    page.workspace.hide()
    page.findings_table.setColumnHidden(4, True)
    page.findings_table.setMinimumHeight(230)
    page.preview_tabs.setTabText(0, "Protected text")
    if page.preview_tabs.count() > 1:
        page.preview_tabs.setTabText(1, "Compare")
    page.focus_preview_button.setText("Full document view")

    page.copy_button.hide()
    page.save_copy_button.hide()
    page.save_download_button.hide()
    page.ai_button.hide()

    # Entire page becomes scrollable so the top input card is never crushed by results.
    scroll = QScrollArea()
    scroll.setObjectName("RedesignScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(24, 20, 24, 22)
    content_layout.setSpacing(14)
    scroll.setWidget(content)
    root.addWidget(scroll)

    # Header
    header = QHBoxLayout()
    headings = QVBoxLayout()
    title = QLabel("Protect your document")
    title.setStyleSheet("font-size:29px;font-weight:800;color:#071f35;")
    subtitle = QLabel("Remove sensitive data locally before using AI.")
    subtitle.setStyleSheet("font-size:12px;color:#6b7d8e;")
    headings.addWidget(title)
    headings.addWidget(subtitle)
    header.addLayout(headings)
    header.addStretch(1)
    for text in ("100% local", "No cloud upload", "Restore available"):
        header.addWidget(_pill(text))
    content_layout.addLayout(header)

    # Top composition: main flow + restore help.
    top_row = QHBoxLayout()
    top_row.setSpacing(14)

    start_card = QFrame(objectName="RedesignStartCard")
    start_card.setMinimumHeight(430)
    start_layout = QVBoxLayout(start_card)
    start_layout.setContentsMargins(18, 0, 18, 16)
    start_layout.setSpacing(10)

    # Protect / Restore tabs
    tab_row = QHBoxLayout()
    protect_tab = QPushButton("Protect")
    restore_tab = QPushButton("Restore")
    protect_tab.setCheckable(True)
    protect_tab.setChecked(True)
    protect_tab.setEnabled(False)
    for button in (protect_tab, restore_tab):
        button.setMinimumHeight(42)
        button.setMinimumWidth(165)
        button.setStyleSheet(
            "QPushButton{background:#ffffff;color:#455b70;border:1px solid #d5e0e8;"
            "border-bottom:none;border-top-left-radius:9px;border-top-right-radius:9px;"
            "padding:9px 18px;font-weight:700;}"
            "QPushButton:checked{background:#f8fffe;color:#078c89;}"
        )
    restore_tab.clicked.connect(lambda: _open_restore_page(page))
    tab_row.addWidget(protect_tab)
    tab_row.addWidget(restore_tab)
    tab_row.addStretch(1)
    start_layout.addLayout(tab_row)

    # Input columns
    input_row = QHBoxLayout()
    input_row.setSpacing(18)

    paste_box = QVBoxLayout()
    paste_box.setSpacing(7)
    paste_box.addWidget(_section_title("Paste text"))
    page.text_input.setMinimumHeight(210)
    page.text_input.setMaximumHeight(310)
    page.text_input.setPlaceholderText(
        "Paste an email, lease excerpt, offer, contractor proposal "
        "or other business text..."
    )
    page.text_input.setStyleSheet(
        "QPlainTextEdit{background:#ffffff;border:1px solid #ccd9e3;"
        "border-radius:9px;padding:12px;font-size:13px;}"
    )
    paste_box.addWidget(page.text_input, 1)
    paste_note = QLabel("Text stays on your device and is never uploaded.")
    paste_note.setStyleSheet("color:#748596;font-size:11px;")
    paste_box.addWidget(paste_note)

    upload_box = QVBoxLayout()
    upload_box.setSpacing(7)
    upload_box.addWidget(_section_title("Upload document"))

    upload_zone = _UploadDropZone()
    upload_zone_layout = QVBoxLayout(upload_zone)
    upload_zone_layout.setContentsMargins(24, 22, 24, 22)
    upload_zone_layout.setSpacing(8)
    upload_zone_layout.addStretch(1)
    upload_icon = QLabel("⇧")
    upload_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    upload_icon.setStyleSheet("font-size:34px;color:#078c89;font-weight:500;")
    upload_zone_layout.addWidget(upload_icon)

    page.browse_button.setText("Upload document")
    page.browse_button.setObjectName("Primary")
    page.browse_button.setMinimumHeight(42)
    page.browse_button.setMaximumWidth(260)
    upload_zone_layout.addWidget(
        page.browse_button, alignment=Qt.AlignmentFlag.AlignHCenter
    )
    upload_filename = QLabel("or drag and drop a local file here")
    upload_filename.setAlignment(Qt.AlignmentFlag.AlignCenter)
    upload_filename.setWordWrap(True)
    upload_filename.setStyleSheet("color:#67798a;font-size:11px;")
    upload_zone_layout.addWidget(upload_filename)
    upload_zone_layout.addStretch(1)
    upload_box.addWidget(upload_zone, 1)

    format_note = QLabel("PDF, Word, Excel — processed locally")
    format_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
    format_note.setStyleSheet("color:#748596;font-size:11px;")
    upload_box.addWidget(format_note)

    input_row.addLayout(paste_box, 1)
    input_row.addLayout(upload_box, 1)
    start_layout.addLayout(input_row, 1)

    # Guidance steps
    steps = QLabel(
        "① Upload or paste     •     ② Scan sensitive data     •     "
        "③ Review & protect     •     ④ Use with AI / Restore locally"
    )
    steps.setAlignment(Qt.AlignmentFlag.AlignCenter)
    steps.setStyleSheet(
        "background:#f6f9fb;color:#5f7385;border-radius:6px;"
        "padding:7px;font-size:11px;"
    )
    start_layout.addWidget(steps)

    # Main actions
    action_row = QHBoxLayout()
    action_row.addStretch(1)
    page.clear_button.setText("Clear")
    page.clear_button.setMinimumSize(95, 44)
    page.scan_button.setText("Scan")
    page.scan_button.setMinimumSize(155, 44)
    page.scan_button.setEnabled(False)
    page.scan_button.setStyleSheet(
        "QPushButton{background:#d7e0e7;color:#8796a4;border:none;border-radius:8px;"
        "font-size:14px;font-weight:800;padding:10px 24px;}"
        "QPushButton:enabled{background:#0b93a0;color:white;}"
        "QPushButton:enabled:hover{background:#087f8b;}"
    )
    protect_button = QPushButton("Protect document")
    protect_button.setMinimumSize(190, 44)
    protect_button.setEnabled(False)
    protect_button.setStyleSheet(
        "QPushButton{background:#d7e0e7;color:#8796a4;border:none;border-radius:8px;"
        "font-size:14px;font-weight:800;padding:10px 24px;}"
        "QPushButton:enabled{background:#078c89;color:white;}"
        "QPushButton:enabled:hover{background:#057a77;}"
    )
    action_row.addWidget(page.clear_button)
    action_row.addWidget(page.scan_button)
    action_row.addWidget(protect_button)
    action_row.addStretch(1)
    start_layout.addLayout(action_row)

    # Operation status / animated waiting indicator.
    busy_panel = QFrame(objectName="RedesignBusyPanel")
    busy_layout = QHBoxLayout(busy_panel)
    busy_layout.setContentsMargins(12, 8, 12, 8)
    busy_layout.setSpacing(10)
    spinner = QLabel("◐")
    spinner.setFixedWidth(22)
    spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
    spinner.setStyleSheet("color:#0a9b98;font-size:18px;font-weight:800;")
    busy_label = QLabel("Working locally…")
    busy_label.setStyleSheet("color:#496173;font-size:11px;font-weight:600;")
    busy_layout.addWidget(spinner)
    busy_layout.addWidget(busy_label)
    busy_layout.addStretch(1)
    busy_panel.hide()
    start_layout.addWidget(busy_panel)

    # Advanced settings: same real widgets, just visually secondary.
    advanced_toggle = QToolButton()
    advanced_toggle.setText("›  Advanced protection settings")
    advanced_toggle.setCheckable(True)
    advanced_toggle.setChecked(False)
    advanced_toggle.setStyleSheet(
        "QToolButton{border:none;color:#17384e;font-weight:700;padding:7px;"
        "text-align:left;}"
    )
    start_layout.addWidget(advanced_toggle)

    advanced_panel = QFrame(objectName="RedesignAdvanced")
    advanced_panel.hide()
    advanced_layout = QHBoxLayout(advanced_panel)
    advanced_layout.setContentsMargins(10, 8, 10, 8)
    advanced_layout.setSpacing(12)
    for label_text, widget in (
        ("Industry profile", page.profile_combo),
        ("Protection scope", page.scope_combo),
        ("Protection mode", page.mode_combo),
        ("Confidence", page.threshold_input),
    ):
        field_layout = QVBoxLayout()
        field = QLabel(label_text)
        field.setStyleSheet("font-size:10px;color:#6c7f90;font-weight:700;")
        field_layout.addWidget(field)
        field_layout.addWidget(widget)
        advanced_layout.addLayout(field_layout, 1)
    start_layout.addWidget(advanced_panel)

    advanced_toggle.toggled.connect(advanced_panel.setVisible)
    advanced_toggle.toggled.connect(
        lambda checked: advanced_toggle.setText(
            "⌄  Advanced protection settings"
            if checked
            else "›  Advanced protection settings"
        )
    )

    help_card = _make_help_card()
    top_row.addWidget(start_card, 1)
    top_row.addWidget(help_card)
    content_layout.addLayout(top_row)

    # Results are hidden until Scan finishes, but keep the target mockup layout.
    results_card = QFrame(objectName="RedesignResults")
    results_layout = QVBoxLayout(results_card)
    results_layout.setContentsMargins(0, 0, 0, 0)
    results_layout.setSpacing(10)

    metrics_row = QHBoxLayout()
    page.findings_metric.setText("0 detected")
    page.findings_metric.setObjectName("Metric")
    protected_metric = QLabel("0 protected", objectName="Metric")
    review_metric = QLabel("Ready to scan", objectName="SafetyMetric")
    metrics_row.addWidget(page.findings_metric)
    metrics_row.addWidget(protected_metric)
    metrics_row.addWidget(review_metric)
    metrics_row.addStretch(1)
    results_layout.addLayout(metrics_row)

    page.workspace.setChildrenCollapsible(False)
    page.workspace.setMinimumHeight(390)
    page.workspace.setSizes([430, 930])
    results_layout.addWidget(page.workspace)

    # Simplified final action bar.
    final_actions = QFrame(objectName="RedesignFinalActions")
    final_layout = QHBoxLayout(final_actions)
    final_layout.setContentsMargins(12, 10, 12, 10)
    final_layout.setSpacing(10)
    copy_action = QPushButton("Copy protected text")
    download_action = QPushButton("Download protected file")
    ai_action = QPushButton("Use with AI")
    ai_action.setObjectName("Primary")
    save_action = QPushButton("Save to local library")
    for button in (copy_action, download_action, ai_action, save_action):
        button.setMinimumHeight(42)
        button.setEnabled(False)
        final_layout.addWidget(button, 1)
    final_actions.hide()
    results_layout.addWidget(final_actions)

    results_card.hide()
    content_layout.addWidget(results_card)
    content_layout.addStretch(1)

    # Polished local-only styling.
    content.setStyleSheet(
        "QFrame#RedesignStartCard,QFrame#RedesignHelpCard,QFrame#RedesignResults,"
        "QFrame#RedesignFinalActions{background:white;border:1px solid #d7e2ea;"
        "border-radius:12px;}"
        "QFrame#RedesignUploadZone{background:#fbfefe;border:1px dashed #55b9b5;"
        "border-radius:10px;}"
        "QFrame#RedesignAdvanced{background:#f8fafc;border:1px solid #e3eaf0;"
        "border-radius:8px;}"
        "QFrame#RedesignBusyPanel{background:#f4fbfa;border:1px solid #d9eeeb;"
        "border-radius:8px;}"
    )

    # Persist redesigned widgets/state.
    page._redesign_scroll = scroll
    page._redesign_start_card = start_card
    page._redesign_help_card = help_card
    page._redesign_upload_zone = upload_zone
    page._redesign_upload_filename = upload_filename
    page._redesign_protect_button = protect_button
    page._redesign_results_card = results_card
    page._redesign_final_actions = final_actions
    page._redesign_protected_metric = protected_metric
    page._redesign_review_metric = review_metric
    page._redesign_busy_panel = busy_panel
    page._redesign_busy_label = busy_label
    page._redesign_spinner = spinner
    page._redesign_spinner_frames = ("◐", "◓", "◑", "◒")
    page._redesign_spinner_index = 0
    page._redesign_spinner_timer = QTimer(page)
    page._redesign_spinner_timer.setInterval(110)
    page._redesign_spinner_timer.timeout.connect(
        lambda: (
            setattr(
                page,
                "_redesign_spinner_index",
                (page._redesign_spinner_index + 1)
                % len(page._redesign_spinner_frames),
            ),
            page._redesign_spinner.setText(
                page._redesign_spinner_frames[page._redesign_spinner_index]
            ),
        )
    )
    page._redesign_active_operations: dict[str, str] = {}
    page._redesign_action_buttons = (
        copy_action,
        download_action,
        ai_action,
        save_action,
    )
    page._redesign_allow_refresh = False
    page._redesign_preview_worker = None
    page._redesign_pdf_generation = 0

    def refresh_busy() -> None:
        operations = page._redesign_active_operations
        if operations:
            busy_label.setText(next(reversed(operations.values())))
            busy_panel.show()
            if not page._redesign_spinner_timer.isActive():
                page._redesign_spinner_timer.start()
        else:
            page._redesign_spinner_timer.stop()
            busy_panel.hide()

    def begin_operation(key: str, message: str) -> None:
        page._redesign_active_operations[key] = message
        refresh_busy()
        QApplication.processEvents()

    def end_operation(key: str) -> None:
        page._redesign_active_operations.pop(key, None)
        refresh_busy()

    page._redesign_begin_operation = begin_operation
    page._redesign_end_operation = end_operation

    def set_final_actions(enabled: bool) -> None:
        for button in page._redesign_action_buttons:
            button.setEnabled(enabled)

    page._redesign_set_final_actions = set_final_actions

    def update_scan_state() -> None:
        has_text = bool(page.text_input.toPlainText().strip())
        has_file = bool(page.pdf_path.text().strip())
        busy = "scan" in page._redesign_active_operations
        page.scan_button.setEnabled((has_text or has_file) and not busy)

    page._redesign_update_scan_state = update_scan_state

    def invalidate_after_input() -> None:
        update_scan_state()
        page.current_result = None
        protect_button.setEnabled(False)
        protect_button.setText("Protect document")
        results_card.hide()
        final_actions.hide()
        set_final_actions(False)
        page._redesign_protected_metric.setText("0 protected")
        page._redesign_review_metric.setText("Ready to scan")

    def text_changed() -> None:
        if page.text_input.toPlainText().strip():
            page.input_tabs.setCurrentIndex(0)
        invalidate_after_input()

    def file_changed(path: str) -> None:
        if path:
            page.input_tabs.setCurrentIndex(1)
            upload_filename.setText(Path(path).name)
        else:
            upload_filename.setText("or drag and drop a local file here")
        invalidate_after_input()

    page.text_input.textChanged.connect(text_changed)
    page.pdf_path.textChanged.connect(file_changed)
    upload_zone.file_dropped.connect(page.pdf_path.setText)

    def selection_changed(*_args) -> None:
        if page.current_document is None:
            return
        selected = len(page._selected_findings())
        page.current_result = None
        protect_button.setEnabled(bool(page.current_findings))
        protect_button.setText(
            "Update protection" if final_actions.isVisible() else "Protect document"
        )
        final_actions.hide()
        set_final_actions(False)
        protected_metric.setText(f"{selected} selected")
        review_metric.setText("Review selection, then protect")

    page.findings_table.itemChanged.connect(selection_changed)

    def protect_now() -> None:
        if page.current_document is None or not page.current_findings:
            return
        begin_operation("protect", "De-identifying selected data locally…")
        page._redesign_allow_refresh = True
        try:
            page._refresh_preview()
        finally:
            page._redesign_allow_refresh = False
            end_operation("protect")
        if page.current_result is None:
            return
        protected_count = len(page.current_result.applied_findings)
        protected_metric.setText(f"{protected_count} protected")
        review_metric.setText("Protected copy ready")
        protect_button.setText("Protected")
        protect_button.setEnabled(False)
        final_actions.show()
        set_final_actions(True)

    protect_button.clicked.connect(protect_now)

    def with_final_check(message: str, callback) -> None:
        if page.current_result is None:
            return
        begin_operation("verify", message)
        try:
            callback()
        finally:
            end_operation("verify")

    copy_action.clicked.connect(
        lambda: with_final_check("Running final privacy check before copy…", page._copy_result)
    )
    download_action.clicked.connect(
        lambda: with_final_check(
            "Running final privacy check before download…", page._save_and_download
        )
    )
    ai_action.clicked.connect(
        lambda: with_final_check(
            "Running final privacy check before opening AI…",
            page._copy_and_open_chatgpt,
        )
    )

    def save_only() -> None:
        if page.current_result is None:
            return
        begin_operation("verify", "Running final privacy check before saving locally…")
        try:
            if not page._confirm_residual_risk("saving"):
                return
            saved = page._save_to_library()
            if saved:
                QMessageBox.information(
                    page,
                    "Saved locally",
                    "The protected document and its reversible mapping were saved "
                    "to your local library.",
                )
        finally:
            end_operation("verify")

    save_action.clicked.connect(save_only)

    # Keep "full document view" functional without ever resurrecting Document setup.
    def focus_changed(focused: bool) -> None:
        page.findings_card.setVisible(not focused)
        page.focus_preview_button.setText(
            "Show review panel" if focused else "Full document view"
        )
        if focused:
            page.workspace.setSizes([0, max(1000, page.width())])
        else:
            page.workspace.setSizes([430, 930])
        page.setup_toggle.hide()
        page.setup_card.hide()

    page._redesign_focus_changed = focus_changed

    update_scan_state()


def install_redesign() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_init = ProtectionPage.__init__
    original_refresh_preview = ProtectionPage._refresh_preview
    original_set_busy = ProtectionPage._set_busy
    original_clear = ProtectionPage.clear

    def redesigned_init(self: ProtectionPage, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        _apply_redesign(self)

    def redesigned_refresh_preview(self: ProtectionPage, *_args) -> None:
        if not hasattr(self, "_redesign_protect_button"):
            original_refresh_preview(self)
            return
        if not self._redesign_allow_refresh:
            if self.current_document is not None:
                selected = len(self._selected_findings())
                self.current_result = None
                self._redesign_protected_metric.setText(f"{selected} selected")
                self._redesign_review_metric.setText(
                    "Review selection, then protect"
                )
                self._redesign_protect_button.setEnabled(bool(self.current_findings))
                self._redesign_protect_button.setText(
                    "Update protection"
                    if self._redesign_final_actions.isVisible()
                    else "Protect document"
                )
                self._redesign_final_actions.hide()
                self._redesign_set_final_actions(False)
            return
        original_refresh_preview(self)

    def redesigned_analysis_ready(
        self: ProtectionPage, payload: object
    ) -> None:
        self.current_document, self.current_findings = payload
        self.current_result = None
        self._populate_findings()
        self._last_residual = ()
        count = len(self.current_findings)
        self.findings_metric.setText(f"{count} detected")
        self._redesign_protected_metric.setText("0 protected")
        self._redesign_review_metric.setText("Ready to review")
        self.verification_metric.setText("Second scan before export")
        self._set_result_actions(False)
        self._redesign_results_card.show()
        self.workspace.show()
        self._redesign_final_actions.hide()
        self._redesign_set_final_actions(False)
        self._redesign_protect_button.setEnabled(bool(self.current_findings))
        self._redesign_protect_button.setText("Protect document")
        self.preview_tabs.setCurrentIndex(0)
        self.preview_tabs.setTabVisible(
            1,
            bool(
                self.current_document
                and self.current_document.source_kind in {"pdf", "docx", "xlsx"}
            ),
        )
        QTimer.singleShot(
            80,
            lambda: self._redesign_scroll.ensureWidgetVisible(
                self._redesign_results_card, 20, 20
            ),
        )

    def redesigned_set_busy(self: ProtectionPage, busy: bool) -> None:
        original_set_busy(self, busy)
        if not hasattr(self, "_redesign_begin_operation"):
            return
        self.text_input.setEnabled(not busy)
        if busy:
            source = (
                "document"
                if self.input_tabs.currentIndex() == 1
                else "text"
            )
            self._redesign_begin_operation(
                "scan", f"Loading and scanning {source} locally…"
            )
            self.scan_button.setText("Scanning…")
            self.scan_button.setEnabled(False)
        else:
            self._redesign_end_operation("scan")
            self.scan_button.setText("Scan")
            self._redesign_update_scan_state()

    def redesigned_focus_preview(self: ProtectionPage, focused: bool) -> None:
        if hasattr(self, "_redesign_focus_changed"):
            self._redesign_focus_changed(focused)
            return

    def redesigned_update_document_comparison(self: ProtectionPage) -> None:
        if (
            not hasattr(self, "_redesign_begin_operation")
            or self.current_document is None
            or self.current_result is None
            or self.current_document.source_path is None
        ):
            return

        # Office rendering keeps the mature legacy path; PDF generation is moved
        # to a worker because rasterization can otherwise freeze the UI.
        if self.current_document.source_kind != "pdf":
            self._redesign_begin_operation(
                "preview", "Generating document preview locally…"
            )
            QApplication.processEvents()
            try:
                _ORIGINAL_UPDATE_DOCUMENT_COMPARISON(self)
            finally:
                self._redesign_end_operation("preview")
            return

        self._redesign_pdf_generation += 1
        generation = self._redesign_pdf_generation
        document = self.current_document
        result = self.current_result
        source_path = document.source_path
        protected_path = self._preview_directory / (
            f"protected-preview-{os.getpid()}-{generation}.pdf"
        )
        self._redesign_begin_operation(
            "preview", "Generating safe PDF preview locally…"
        )

        def task():
            fallback = False
            fallback_reason = ""
            try:
                self.service.save_protected_pdf(
                    result,
                    protected_path,
                    source_document=document,
                )
            except ValueError as exc:
                # Preview must remain available, but never at the price of exposing
                # original text. Reflow the already-protected pages into a safe PDF.
                fallback = True
                fallback_reason = str(exc)
                self.service.save_protected_pdf(
                    result,
                    protected_path,
                    source_document=None,
                )
            return generation, protected_path, fallback, fallback_reason

        worker = FunctionWorker(task)
        self._redesign_preview_worker = worker

        def preview_error(message: str) -> None:
            if generation != self._redesign_pdf_generation:
                return
            self.comparison_note.setText(
                f"Preview unavailable. The protected text remains available. {message}"
            )
            self.preview_tabs.setCurrentIndex(0)
            self._redesign_end_operation("preview")

        def preview_ready(payload: object) -> None:
            ready_generation, path, fallback, fallback_reason = payload
            if ready_generation != self._redesign_pdf_generation:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
                return

            previous = self._preview_path
            self.original_pdf_document.close()
            self.protected_pdf_document.close()
            QApplication.processEvents()

            self.original_view_stack.setCurrentIndex(0)
            self.protected_view_stack.setCurrentIndex(0)
            self.office_preview_options_widget.setVisible(False)
            self._set_pdf_controls_enabled(True)
            self.original_pdf_document.load(str(source_path))
            self.protected_pdf_document.load(str(path))
            self._preview_path = path
            self.preview_tabs.setTabVisible(1, True)
            self.preview_tabs.setCurrentIndex(1)

            if fallback:
                self.comparison_note.setText(
                    "Safe reflow preview: this PDF could not be mapped reliably "
                    "back onto every original text position, so Privacy Gate is "
                    "showing the original beside a fully protected reflow copy."
                )
                self.preview_tabs.setTabToolTip(
                    1,
                    "Safe reflow preview used because exact layout mapping was not reliable.",
                )
                self._redesign_review_metric.setText("Safe reflow preview")
            else:
                self.comparison_note.setText(
                    "Original PDF on the left. Secure layout-preserving protected "
                    "PDF on the right."
                )
                self.preview_tabs.setTabToolTip(
                    1,
                    "Compare the local source with the secure layout-preserving copy.",
                )

            def wait_for_pdf(attempt: int = 0) -> None:
                if ready_generation != self._redesign_pdf_generation:
                    return
                original_status = self.original_pdf_document.status()
                protected_status = self.protected_pdf_document.status()
                if (
                    original_status == QPdfDocument.Status.Ready
                    and protected_status == QPdfDocument.Status.Ready
                ):
                    self._set_pdf_page(0)
                    self._fit_pdf_width()
                    self._redesign_end_operation("preview")
                    if previous is not None and previous != path:
                        try:
                            previous.unlink(missing_ok=True)
                        except OSError:
                            pass
                    return
                if (
                    original_status == QPdfDocument.Status.Error
                    or protected_status == QPdfDocument.Status.Error
                ):
                    self.comparison_note.setText(
                        "The PDF renderer could not display this file. "
                        "Protected text is still available."
                    )
                    self.preview_tabs.setCurrentIndex(0)
                    self._redesign_end_operation("preview")
                    return
                if attempt >= 50:
                    self.comparison_note.setText(
                        "The PDF preview is taking longer than expected. "
                        "You can continue reviewing the protected text."
                    )
                    self._redesign_end_operation("preview")
                    return
                QTimer.singleShot(100, lambda: wait_for_pdf(attempt + 1))

            wait_for_pdf()

        worker.signals.result.connect(preview_ready)
        worker.signals.error.connect(preview_error)
        worker.signals.finished.connect(
            lambda: setattr(self, "_redesign_preview_worker", None)
        )
        self.thread_pool.start(worker)

    def redesigned_clear(self: ProtectionPage) -> None:
        original_clear(self)
        if not hasattr(self, "_redesign_results_card"):
            return
        self.setup_toggle.hide()
        self.setup_card.hide()
        self._redesign_active_operations.clear()
        self._redesign_spinner_timer.stop()
        self._redesign_busy_panel.hide()
        self._redesign_upload_filename.setText(
            "or drag and drop a local file here"
        )
        self.scan_button.setText("Scan")
        self.scan_button.setEnabled(False)
        self._redesign_protect_button.setEnabled(False)
        self._redesign_protect_button.setText("Protect document")
        self._redesign_results_card.hide()
        self._redesign_final_actions.hide()
        self._redesign_protected_metric.setText("0 protected")
        self._redesign_review_metric.setText("Ready to scan")
        self._redesign_set_final_actions(False)
        self._redesign_scroll.verticalScrollBar().setValue(0)

    # Capture this before replacing the class method below.
    global _ORIGINAL_UPDATE_DOCUMENT_COMPARISON
    _ORIGINAL_UPDATE_DOCUMENT_COMPARISON = ProtectionPage._update_document_comparison

    ProtectionPage.__init__ = redesigned_init
    ProtectionPage._refresh_preview = redesigned_refresh_preview
    ProtectionPage._analysis_ready = redesigned_analysis_ready
    ProtectionPage._set_busy = redesigned_set_busy
    ProtectionPage._toggle_preview_focus = redesigned_focus_preview
    ProtectionPage._update_document_comparison = redesigned_update_document_comparison
    ProtectionPage.clear = redesigned_clear
