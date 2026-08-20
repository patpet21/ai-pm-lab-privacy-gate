from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage

_INSTALLED = False


def _clone_combo(source: QComboBox) -> QComboBox:
    clone = QComboBox()
    for index in range(source.count()):
        clone.addItem(source.itemText(index), source.itemData(index))
    clone.setCurrentIndex(source.currentIndex())
    clone.currentIndexChanged.connect(source.setCurrentIndex)
    source.currentIndexChanged.connect(
        lambda index: clone.setCurrentIndex(index)
        if clone.currentIndex() != index
        else None
    )
    return clone


def _make_help_card() -> QFrame:
    card = QFrame(objectName="RestoreHelpCard")
    card.setMinimumWidth(275)
    card.setMaximumWidth(305)
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    card.setStyleSheet(
        "QFrame#RestoreHelpCard{background:white;border:1px solid #d8e2ea;"
        "border-radius:12px;}"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(10)

    title = QLabel("How restore works")
    title.setStyleSheet("font-size:16px;font-weight:700;color:#0a2940;")
    layout.addWidget(title)

    subtitle = QLabel("Your originals stay local from protection to restore.")
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet("color:#687b8d;font-size:12px;")
    layout.addWidget(subtitle)

    steps = (
        ("1", "Protect with reversible placeholders"),
        ("2", "Use the protected version with AI"),
        ("3", "Paste the AI response in Restore"),
        ("4", "Restore original values locally"),
    )
    for number, heading in steps:
        row = QHBoxLayout()
        row.setSpacing(10)
        badge = QLabel(number)
        badge.setFixedSize(24, 24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            "background:#0a9b98;color:white;border-radius:12px;font-weight:700;"
        )
        text = QLabel(heading)
        text.setWordWrap(True)
        text.setStyleSheet("color:#12334a;font-weight:700;font-size:12px;")
        row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        row.addWidget(text, 1)
        layout.addLayout(row)

    layout.addStretch(1)
    note = QLabel("100% local restore\nOriginal values never need to be sent to AI.")
    note.setWordWrap(True)
    note.setStyleSheet(
        "background:#eefaf8;border:1px solid #d5eeea;border-radius:8px;"
        "padding:10px;color:#28645f;font-size:11px;"
    )
    layout.addWidget(note)
    return card


def _apply_redesign(page: ProtectionPage) -> None:
    root = page.layout()
    root.setSpacing(10)

    for label in page.findChildren(QLabel):
        if label.text() == "Protect a document":
            label.setText("Protect your document")
        elif label.text() == "Review every detected item before anything leaves this PC.":
            label.setText("Remove sensitive data locally before using AI.")
        elif label.text() == "Load text, PDF, Word or Excel, choose a profile, then scan.":
            label.hide()

    page.local_badge.setText("100% LOCAL   |   NO CLOUD UPLOAD   |   RESTORE AVAILABLE")
    page.setup_toggle.hide()
    page.setup_card.hide()

    original_action_bar = page.findChild(QFrame, "ActionBar")
    if original_action_bar is not None:
        original_action_bar.hide()

    # Keep the review surface simple until a scan exists.
    page.types_metric.hide()
    page.pages_metric.hide()
    page.source_metric.hide()
    page.findings_metric.hide()
    page.verification_metric.hide()
    page.workspace.hide()
    page.findings_table.setColumnHidden(4, True)

    page.preview_tabs.setTabText(0, "Protected text")
    if page.preview_tabs.count() > 1:
        page.preview_tabs.setTabText(1, "Document preview / Compare")

    # ---------- Simple start card ----------
    wrapper = QWidget()
    wrapper_layout = QHBoxLayout(wrapper)
    wrapper_layout.setContentsMargins(0, 0, 0, 0)
    wrapper_layout.setSpacing(14)

    start_card = QFrame(objectName="SimpleStartCard")
    start_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    start_card.setStyleSheet(
        "QFrame#SimpleStartCard{background:white;border:1px solid #d8e2ea;"
        "border-radius:12px;}"
        "QFrame#UploadZone{background:#f8fcfc;border:1px dashed #58b9b5;"
        "border-radius:10px;}"
    )
    start_layout = QVBoxLayout(start_card)
    start_layout.setContentsMargins(20, 18, 20, 18)
    start_layout.setSpacing(10)

    intro_row = QHBoxLayout()
    protect_chip = QLabel("PROTECT")
    protect_chip.setStyleSheet(
        "background:#e8f7f6;color:#087d7b;border:1px solid #b8e0dd;"
        "border-radius:8px;padding:7px 16px;font-weight:700;"
    )
    restore_hint = QLabel(
        "Protect locally now. Restore later from the Restore page when using reversible placeholders."
    )
    restore_hint.setWordWrap(True)
    restore_hint.setStyleSheet("color:#6b7d8e;font-size:12px;")
    intro_row.addWidget(protect_chip)
    intro_row.addWidget(restore_hint, 1)
    start_layout.addLayout(intro_row)

    input_panel = QWidget()
    input_panel.setMinimumHeight(230)
    input_row = QHBoxLayout(input_panel)
    input_row.setContentsMargins(0, 0, 0, 0)
    input_row.setSpacing(18)

    paste_col = QVBoxLayout()
    paste_col.setSpacing(7)
    paste_title = QLabel("Paste text")
    paste_title.setStyleSheet("font-size:15px;font-weight:700;color:#0a2940;")
    paste_col.addWidget(paste_title)
    simple_text = QPlainTextEdit()
    simple_text.setPlaceholderText(
        "Paste an email, lease excerpt, offer, contractor proposal or other business text..."
    )
    simple_text.setMinimumHeight(170)
    simple_text.setStyleSheet(
        "QPlainTextEdit{background:white;border:1px solid #cfdbe5;"
        "border-radius:9px;padding:12px;font-size:14px;}"
    )
    paste_col.addWidget(simple_text, 1)
    paste_note = QLabel("Text stays on this device and is never uploaded.")
    paste_note.setStyleSheet("color:#748596;font-size:11px;")
    paste_col.addWidget(paste_note)

    upload_col = QVBoxLayout()
    upload_col.setSpacing(7)
    upload_title = QLabel("Upload document")
    upload_title.setStyleSheet("font-size:15px;font-weight:700;color:#0a2940;")
    upload_col.addWidget(upload_title)

    upload_zone = QFrame(objectName="UploadZone")
    upload_zone.setMinimumHeight(170)
    upload_zone_layout = QVBoxLayout(upload_zone)
    upload_zone_layout.setContentsMargins(22, 18, 22, 18)
    upload_zone_layout.setSpacing(9)
    upload_zone_layout.addStretch(1)

    upload_symbol = QLabel("↑")
    upload_symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
    upload_symbol.setStyleSheet("font-size:30px;color:#078c89;font-weight:700;")
    upload_zone_layout.addWidget(upload_symbol)

    upload_button = QPushButton("Upload document", objectName="Primary")
    upload_button.setMinimumHeight(44)
    upload_button.setMinimumWidth(220)
    upload_zone_layout.addWidget(upload_button, alignment=Qt.AlignmentFlag.AlignCenter)

    upload_filename = QLabel("or choose a local file")
    upload_filename.setAlignment(Qt.AlignmentFlag.AlignCenter)
    upload_filename.setWordWrap(True)
    upload_filename.setStyleSheet("color:#67798a;font-size:11px;")
    upload_zone_layout.addWidget(upload_filename)
    upload_zone_layout.addStretch(1)
    upload_col.addWidget(upload_zone, 1)

    format_note = QLabel("PDF, Word, Excel — processed locally")
    format_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
    format_note.setStyleSheet("color:#748596;font-size:11px;")
    upload_col.addWidget(format_note)

    input_row.addLayout(paste_col, 1)
    input_row.addLayout(upload_col, 1)
    start_layout.addWidget(input_panel)

    steps = QLabel(
        "1  Upload or paste     •     2  Scan sensitive data     •     "
        "3  Review & protect     •     4  Use with AI / restore locally"
    )
    steps.setAlignment(Qt.AlignmentFlag.AlignCenter)
    steps.setStyleSheet("color:#5f7385;font-size:11px;padding:4px;")
    start_layout.addWidget(steps)

    action_row = QHBoxLayout()
    action_row.setSpacing(10)
    action_row.addStretch(1)

    clear_button = QPushButton("Clear", objectName="Secondary")
    clear_button.setMinimumSize(90, 44)

    scan_button = QPushButton("Scan")
    scan_button.setMinimumSize(150, 44)
    scan_button.setEnabled(False)
    scan_button.setStyleSheet(
        "QPushButton{background:#d9e1e8;color:#8a98a5;border:none;"
        "border-radius:8px;font-size:14px;font-weight:700;padding:10px 24px;}"
        "QPushButton:enabled{background:#0b93a0;color:white;}"
        "QPushButton:enabled:hover{background:#087f8b;}"
    )

    protect_button = QPushButton("Protect document")
    protect_button.setMinimumSize(190, 44)
    protect_button.setEnabled(False)
    protect_button.setStyleSheet(
        "QPushButton{background:#d9e1e8;color:#8a98a5;border:none;"
        "border-radius:8px;font-size:14px;font-weight:700;padding:10px 24px;}"
        "QPushButton:enabled{background:#078c89;color:white;}"
        "QPushButton:enabled:hover{background:#057a77;}"
    )

    action_row.addWidget(clear_button)
    action_row.addWidget(scan_button)
    action_row.addWidget(protect_button)
    action_row.addStretch(1)
    start_layout.addLayout(action_row)

    advanced_toggle = QToolButton()
    advanced_toggle.setText("›  Advanced protection settings")
    advanced_toggle.setCheckable(True)
    advanced_toggle.setChecked(False)
    advanced_toggle.setStyleSheet(
        "QToolButton{border:none;color:#18384e;font-weight:700;"
        "padding:7px;text-align:left;}"
    )
    start_layout.addWidget(advanced_toggle, alignment=Qt.AlignmentFlag.AlignLeft)

    advanced_panel = QFrame()
    advanced_panel.setVisible(False)
    advanced_layout = QHBoxLayout(advanced_panel)
    advanced_layout.setContentsMargins(0, 2, 0, 0)
    advanced_layout.setSpacing(10)

    profile = _clone_combo(page.profile_combo)
    scope = _clone_combo(page.scope_combo)
    mode = _clone_combo(page.mode_combo)
    confidence = QDoubleSpinBox()
    confidence.setRange(page.threshold_input.minimum(), page.threshold_input.maximum())
    confidence.setSingleStep(page.threshold_input.singleStep())
    confidence.setDecimals(page.threshold_input.decimals())
    confidence.setValue(page.threshold_input.value())
    confidence.valueChanged.connect(page.threshold_input.setValue)
    page.threshold_input.valueChanged.connect(
        lambda value: confidence.setValue(value)
        if confidence.value() != value
        else None
    )

    for text, widget in (
        ("Industry profile", profile),
        ("Protection scope", scope),
        ("Protection mode", mode),
        ("Confidence", confidence),
    ):
        group = QVBoxLayout()
        field = QLabel(text)
        field.setStyleSheet("font-size:11px;color:#6c7f90;font-weight:600;")
        group.addWidget(field)
        group.addWidget(widget)
        advanced_layout.addLayout(group, 1)

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
    wrapper_layout.addWidget(start_card, 1)
    wrapper_layout.addWidget(help_card)
    root.insertWidget(1, wrapper)

    # ---------- Simplified result actions ----------
    for widget in (
        page.copy_button,
        page.save_copy_button,
        page.save_download_button,
        page.ai_button,
    ):
        widget.hide()

    action_card = QFrame(objectName="Card")
    action_card.hide()
    bottom = QHBoxLayout(action_card)
    bottom.setContentsMargins(12, 9, 12, 9)
    bottom.setSpacing(10)

    copy_action = QPushButton("Copy protected text")
    download_action = QPushButton("Download protected file")
    ai_action = QPushButton("Use with AI", objectName="Primary")
    save_action = QPushButton("Save to local library")
    for button in (copy_action, download_action, ai_action, save_action):
        button.setMinimumHeight(40)
        button.setEnabled(False)
        bottom.addWidget(button, 1)
    root.addWidget(action_card)

    page._redesign_scan_button = scan_button
    page._redesign_protect_button = protect_button
    page._redesign_simple_text = simple_text
    page._redesign_upload_button = upload_button
    page._redesign_upload_filename = upload_filename
    page._redesign_help_card = help_card
    page._redesign_input_panel = input_panel
    page._redesign_action_card = action_card
    page._redesign_action_buttons = (
        copy_action,
        download_action,
        ai_action,
        save_action,
    )

    def set_actions(enabled: bool) -> None:
        for button in page._redesign_action_buttons:
            button.setEnabled(enabled)

    def set_review_visible(visible: bool) -> None:
        page.workspace.setVisible(visible)
        page.findings_metric.setVisible(visible)
        page.verification_metric.setVisible(visible)
        action_card.setVisible(visible)
        help_card.setVisible(not visible)
        if visible:
            input_panel.setMinimumHeight(140)
            input_panel.setMaximumHeight(165)
            simple_text.setMinimumHeight(90)
            simple_text.setMaximumHeight(110)
            upload_zone.setMinimumHeight(90)
            upload_zone.setMaximumHeight(110)
        else:
            input_panel.setMaximumHeight(16777215)
            input_panel.setMinimumHeight(230)
            simple_text.setMaximumHeight(16777215)
            simple_text.setMinimumHeight(170)
            upload_zone.setMaximumHeight(16777215)
            upload_zone.setMinimumHeight(170)

    page._redesign_set_review_visible = set_review_visible

    def update_scan_state() -> None:
        has_text = bool(simple_text.toPlainText().strip())
        has_file = bool(page.pdf_path.text().strip())
        scan_button.setEnabled(has_text or has_file)

    page._redesign_update_scan_state = update_scan_state

    def invalidate_result() -> None:
        update_scan_state()
        protect_button.setEnabled(False)
        protect_button.setText("Protect document")
        set_actions(False)
        page.current_result = None
        set_review_visible(False)

    def sync_text() -> None:
        page.text_input.setPlainText(simple_text.toPlainText())
        if simple_text.toPlainText().strip():
            page.input_tabs.setCurrentIndex(0)
        invalidate_result()

    def sync_file(path: str) -> None:
        if path:
            page.input_tabs.setCurrentIndex(1)
            upload_filename.setText(path.replace("\\", "/").split("/")[-1])
        else:
            upload_filename.setText("or choose a local file")
        invalidate_result()

    simple_text.textChanged.connect(sync_text)
    page.pdf_path.textChanged.connect(sync_file)
    upload_button.clicked.connect(page._browse_document)
    clear_button.clicked.connect(page.clear)
    scan_button.clicked.connect(page._start_analysis)

    def protect_now() -> None:
        if page.current_document is None or not page.current_findings:
            return
        page._refresh_preview()
        page.preview_tabs.setCurrentIndex(0)
        protect_button.setText("Protected")
        set_actions(True)

    protect_button.clicked.connect(protect_now)
    copy_action.clicked.connect(page._copy_result)
    download_action.clicked.connect(page._save_and_download)
    ai_action.clicked.connect(page._copy_and_open_chatgpt)

    def save_only() -> None:
        if page.current_result is None:
            return
        if not page._confirm_residual_risk("saving"):
            return
        saved = page._save_to_library()
        if saved:
            QMessageBox.information(
                page,
                "Saved locally",
                "The protected document and its reversible mapping were saved to your local library.",
            )

    save_action.clicked.connect(save_only)
    set_review_visible(False)
    update_scan_state()


def install_redesign() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_init = ProtectionPage.__init__
    original_clear = ProtectionPage.clear
    original_set_busy = ProtectionPage._set_busy

    def redesigned_init(self: ProtectionPage, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        _apply_redesign(self)

    def redesigned_analysis_ready(self: ProtectionPage, payload: object) -> None:
        self.current_document, self.current_findings = payload
        self.current_result = None
        self._populate_findings()
        self.setup_toggle.setChecked(False)
        self.findings_metric.setText(f"{len(self.current_findings)} detected")
        self._last_residual = ()
        self.verification_metric.setText("Ready to review and protect")
        self._set_result_actions(False)
        self._redesign_protect_button.setEnabled(bool(self.current_findings))
        self._redesign_protect_button.setText("Protect document")
        for button in self._redesign_action_buttons:
            button.setEnabled(False)
        self.preview_tabs.setCurrentIndex(0)
        self._redesign_set_review_visible(True)

    def redesigned_set_busy(self: ProtectionPage, busy: bool) -> None:
        original_set_busy(self, busy)
        if not hasattr(self, "_redesign_scan_button"):
            return
        self._redesign_simple_text.setEnabled(not busy)
        self._redesign_upload_button.setEnabled(not busy)
        if busy:
            self._redesign_scan_button.setEnabled(False)
            self._redesign_scan_button.setText("Scanning...")
        else:
            self._redesign_scan_button.setText("Scan")
            self._redesign_update_scan_state()

    def redesigned_clear(self: ProtectionPage) -> None:
        original_clear(self)
        if not hasattr(self, "_redesign_simple_text"):
            return
        self._redesign_simple_text.blockSignals(True)
        self._redesign_simple_text.clear()
        self._redesign_simple_text.blockSignals(False)
        self._redesign_upload_filename.setText("or choose a local file")
        self._redesign_scan_button.setText("Scan")
        self._redesign_scan_button.setEnabled(False)
        self._redesign_protect_button.setEnabled(False)
        self._redesign_protect_button.setText("Protect document")
        for button in self._redesign_action_buttons:
            button.setEnabled(False)
        self._redesign_set_review_visible(False)

    ProtectionPage.__init__ = redesigned_init
    ProtectionPage._analysis_ready = redesigned_analysis_ready
    ProtectionPage._set_busy = redesigned_set_busy
    ProtectionPage.clear = redesigned_clear
