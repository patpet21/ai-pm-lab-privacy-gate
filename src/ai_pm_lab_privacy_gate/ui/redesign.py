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
        lambda index: clone.setCurrentIndex(index) if clone.currentIndex() != index else None
    )
    return clone


def _make_help_card() -> QFrame:
    card = QFrame()
    card.setObjectName("RestoreHelpCard")
    card.setFixedWidth(250)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)

    title = QLabel("How restore works")
    title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0a2940;")
    layout.addWidget(title)

    steps = (
        ("1", "Protect with reversible placeholders", "Sensitive values become local reversible tokens."),
        ("2", "Use the protected version with AI", "Only the protected copy leaves Privacy Gate."),
        ("3", "Paste the AI response in Restore", "Open Restore and paste the AI output."),
        ("4", "Restore original values locally", "The original values are restored on this device."),
    )
    for number, heading, body in steps:
        row = QHBoxLayout()
        badge = QLabel(number)
        badge.setFixedSize(24, 24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            "background:#0a9b98;color:white;border-radius:12px;font-weight:700;"
        )
        text = QLabel(f"<b>{heading}</b><br><span style='color:#66788a'>{body}</span>")
        text.setWordWrap(True)
        row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        row.addWidget(text, 1)
        layout.addLayout(row)

    note = QLabel("Everything stays on your device.\nOriginal values never need to be sent to AI.")
    note.setWordWrap(True)
    note.setStyleSheet(
        "background:#eefaf8;border:1px solid #d5eeea;border-radius:8px;"
        "padding:10px;color:#28645f;"
    )
    layout.addWidget(note)
    layout.addStretch(1)
    return card


def _apply_redesign(page: ProtectionPage) -> None:
    page.setProperty("privacyGateRedesign", True)

    for label in page.findChildren(QLabel):
        if label.text() == "Protect a document":
            label.setText("Protect your document")
        elif label.text() == "Review every detected item before anything leaves this PC.":
            label.setText("Remove sensitive data locally before using AI.")
        elif label.text() == "Load text, PDF, Word or Excel, choose a profile, then scan.":
            label.hide()

    page.local_badge.setText("100% LOCAL  •  NO CLOUD UPLOAD  •  RESTORE AVAILABLE")
    page.setup_toggle.hide()
    page.setup_card.hide()

    root = page.layout()
    wrapper = QWidget()
    wrapper_layout = QHBoxLayout(wrapper)
    wrapper_layout.setContentsMargins(0, 0, 0, 0)
    wrapper_layout.setSpacing(14)

    start_card = QFrame()
    start_card.setObjectName("SimpleStartCard")
    start_card.setStyleSheet(
        "QFrame#SimpleStartCard{background:white;border:1px solid #d8e2ea;border-radius:12px;}"
        "QFrame#UploadZone{background:#f8fcfc;border:1px dashed #58b9b5;border-radius:10px;}"
        "QFrame#RestoreHelpCard{background:white;border:1px solid #d8e2ea;border-radius:12px;}"
    )
    start_layout = QVBoxLayout(start_card)
    start_layout.setContentsMargins(20, 18, 20, 18)
    start_layout.setSpacing(12)

    protect_restore_tabs = QHBoxLayout()
    protect_tab = QPushButton("Protect")
    protect_tab.setEnabled(False)
    protect_tab.setStyleSheet(
        "QPushButton{background:#e8f7f6;color:#087d7b;border:1px solid #b8e0dd;"
        "border-radius:8px;padding:8px 18px;font-weight:700;}"
    )
    restore_hint = QLabel("Restore is available from the left navigation after you use reversible placeholders.")
    restore_hint.setStyleSheet("color:#6b7d8e;")
    protect_restore_tabs.addWidget(protect_tab)
    protect_restore_tabs.addWidget(restore_hint)
    protect_restore_tabs.addStretch(1)
    start_layout.addLayout(protect_restore_tabs)

    input_row = QHBoxLayout()
    input_row.setSpacing(16)

    paste_col = QVBoxLayout()
    paste_title = QLabel("Paste text")
    paste_title.setStyleSheet("font-size:15px;font-weight:700;color:#0a2940;")
    paste_col.addWidget(paste_title)
    simple_text = QPlainTextEdit()
    simple_text.setPlaceholderText(
        "Paste an email, lease excerpt, offer, contractor proposal or other business text..."
    )
    simple_text.setMinimumHeight(150)
    simple_text.setStyleSheet(
        "QPlainTextEdit{background:white;border:1px solid #cfdbe5;border-radius:9px;"
        "padding:12px;font-size:14px;}"
    )
    paste_col.addWidget(simple_text)
    paste_note = QLabel("Text stays on your device and is never uploaded.")
    paste_note.setStyleSheet("color:#748596;font-size:12px;")
    paste_col.addWidget(paste_note)

    upload_col = QVBoxLayout()
    upload_title = QLabel("Upload document")
    upload_title.setStyleSheet("font-size:15px;font-weight:700;color:#0a2940;")
    upload_col.addWidget(upload_title)

    upload_zone = QFrame()
    upload_zone.setObjectName("UploadZone")
    upload_zone_layout = QVBoxLayout(upload_zone)
    upload_zone_layout.setContentsMargins(18, 20, 18, 20)
    upload_zone_layout.setSpacing(8)
    upload_icon = QLabel("UPLOAD")
    upload_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    upload_icon.setStyleSheet("font-size:16px;color:#078c89;font-weight:800;letter-spacing:1px;")
    upload_button = QPushButton("Upload document")
    upload_button.setObjectName("Primary")
    upload_button.setMinimumHeight(42)
    upload_filename = QLabel("or choose a local file")
    upload_filename.setAlignment(Qt.AlignmentFlag.AlignCenter)
    upload_filename.setWordWrap(True)
    upload_filename.setStyleSheet("color:#67798a;")
    upload_zone_layout.addWidget(upload_icon)
    upload_zone_layout.addWidget(upload_button)
    upload_zone_layout.addWidget(upload_filename)
    upload_col.addWidget(upload_zone)
    format_note = QLabel("PDF, Word, Excel — processed locally")
    format_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
    format_note.setStyleSheet("color:#748596;font-size:12px;")
    upload_col.addWidget(format_note)

    input_row.addLayout(paste_col, 1)
    input_row.addLayout(upload_col, 1)
    start_layout.addLayout(input_row)

    steps = QLabel(
        "1  Upload or paste    •    2  Scan sensitive data    •    "
        "3  Protect selected items    •    4  Use with AI / Restore locally"
    )
    steps.setAlignment(Qt.AlignmentFlag.AlignCenter)
    steps.setStyleSheet("color:#5f7385;font-size:12px;padding:4px;")
    start_layout.addWidget(steps)

    action_row = QHBoxLayout()
    action_row.addStretch(1)
    scan_button = QPushButton("Scan")
    scan_button.setMinimumSize(150, 44)
    scan_button.setEnabled(False)
    scan_button.setStyleSheet(
        "QPushButton{background:#d9e1e8;color:#8a98a5;border:none;border-radius:8px;"
        "font-size:15px;font-weight:700;padding:10px 24px;}"
        "QPushButton:enabled{background:#0b93a0;color:white;}"
        "QPushButton:enabled:hover{background:#087f8b;}"
    )
    protect_button = QPushButton("Protect document")
    protect_button.setMinimumSize(190, 44)
    protect_button.setEnabled(False)
    protect_button.setStyleSheet(
        "QPushButton{background:#d9e1e8;color:#8a98a5;border:none;border-radius:8px;"
        "font-size:15px;font-weight:700;padding:10px 24px;}"
        "QPushButton:enabled{background:#078c89;color:white;}"
        "QPushButton:enabled:hover{background:#057a77;}"
    )
    action_row.addWidget(scan_button)
    action_row.addWidget(protect_button)
    action_row.addStretch(1)
    start_layout.addLayout(action_row)

    advanced_toggle = QToolButton()
    advanced_toggle.setText(">  Advanced protection settings")
    advanced_toggle.setCheckable(True)
    advanced_toggle.setChecked(False)
    advanced_toggle.setStyleSheet(
        "QToolButton{border:none;color:#18384e;font-weight:700;padding:7px;text-align:left;}"
    )
    start_layout.addWidget(advanced_toggle)

    advanced_panel = QFrame()
    advanced_panel.setVisible(False)
    advanced_layout = QHBoxLayout(advanced_panel)
    advanced_layout.setContentsMargins(0, 4, 0, 0)
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
        lambda value: confidence.setValue(value) if confidence.value() != value else None
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
            "v  Advanced protection settings" if checked else ">  Advanced protection settings"
        )
    )

    wrapper_layout.addWidget(start_card, 1)
    help_card = _make_help_card()
    help_card.setStyleSheet(
        "QFrame#RestoreHelpCard{background:white;border:1px solid #d8e2ea;border-radius:12px;}"
    )
    wrapper_layout.addWidget(help_card)
    root.insertWidget(1, wrapper)

    page.types_metric.hide()
    page.pages_metric.hide()
    page.source_metric.hide()
    page.preview_tabs.setTabText(0, "Protected text")
    if page.preview_tabs.count() > 1:
        page.preview_tabs.setTabText(1, "Document preview / Compare")

    for widget in (page.copy_button, page.save_copy_button, page.save_download_button, page.ai_button):
        widget.hide()

    action_card = QFrame()
    action_card.setObjectName("Card")
    bottom = QHBoxLayout(action_card)
    bottom.setContentsMargins(14, 10, 14, 10)
    bottom.setSpacing(10)

    copy_action = QPushButton("Copy protected text")
    download_action = QPushButton("Download protected file")
    ai_action = QPushButton("Use with AI")
    ai_action.setObjectName("Primary")
    save_action = QPushButton("Save to local library")
    for button in (copy_action, download_action, ai_action, save_action):
        button.setMinimumHeight(40)
        button.setEnabled(False)
        bottom.addWidget(button, 1)
    root.addWidget(action_card)

    page._redesign_scan_button = scan_button
    page._redesign_protect_button = protect_button
    page._redesign_simple_text = simple_text
    page._redesign_upload_filename = upload_filename
    page._redesign_action_buttons = (copy_action, download_action, ai_action, save_action)

    def set_actions(enabled: bool) -> None:
        for button in page._redesign_action_buttons:
            button.setEnabled(enabled)

    def invalidate_scan() -> None:
        has_text = bool(simple_text.toPlainText().strip())
        has_file = bool(page.pdf_path.text().strip())
        scan_button.setEnabled(has_text or has_file)
        protect_button.setEnabled(False)
        protect_button.setText("Protect document")
        set_actions(False)
        page.current_result = None

    def sync_text() -> None:
        page.text_input.setPlainText(simple_text.toPlainText())
        if simple_text.toPlainText().strip():
            page.input_tabs.setCurrentIndex(0)
        invalidate_scan()

    def sync_file(path: str) -> None:
        if path:
            page.input_tabs.setCurrentIndex(1)
            upload_filename.setText(path.replace("\\", "/").split("/")[-1])
        else:
            upload_filename.setText("or choose a local file")
        invalidate_scan()

    simple_text.textChanged.connect(sync_text)
    page.pdf_path.textChanged.connect(sync_file)
    upload_button.clicked.connect(page._browse_document)
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
    invalidate_scan()


def install_redesign() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_init = ProtectionPage.__init__
    original_clear = ProtectionPage.clear

    def redesigned_init(self: ProtectionPage, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        _apply_redesign(self)

    def redesigned_analysis_ready(self: ProtectionPage, payload: object) -> None:
        self.current_document, self.current_findings = payload
        self.current_result = None
        self._populate_findings()
        self.setup_toggle.setChecked(False)
        self.findings_metric.setText(f"{len(self.current_findings)} detected  |  0 protected")
        self._last_residual = ()
        self.verification_metric.setText("Ready to protect selected items")
        self._set_result_actions(False)
        self._redesign_protect_button.setEnabled(bool(self.current_findings))
        self._redesign_protect_button.setText("Protect document")
        for button in self._redesign_action_buttons:
            button.setEnabled(False)
        self.preview_tabs.setCurrentIndex(0)

    def redesigned_clear(self: ProtectionPage) -> None:
        original_clear(self)
        if hasattr(self, "_redesign_simple_text"):
            self._redesign_simple_text.blockSignals(True)
            self._redesign_simple_text.clear()
            self._redesign_simple_text.blockSignals(False)
            self._redesign_upload_filename.setText("or choose a local file")
            self._redesign_scan_button.setEnabled(False)
            self._redesign_protect_button.setEnabled(False)
            self._redesign_protect_button.setText("Protect document")
            for button in self._redesign_action_buttons:
                button.setEnabled(False)

    ProtectionPage.__init__ = redesigned_init
    ProtectionPage._analysis_ready = redesigned_analysis_ready
    ProtectionPage.clear = redesigned_clear
