from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
from ai_pm_lab_privacy_gate.ui.restore_page_v2 import RestorePage


_INSTALLED = False


def _style_action_button(button: QPushButton, role: str) -> None:
    button.setMinimumHeight(40)
    button.setMaximumHeight(42)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if role == "primary":
        button.setStyleSheet(
            "QPushButton{background:#078c89;color:white;border:1px solid #078c89;"
            "border-radius:8px;padding:8px 16px;font-weight:800;}"
            "QPushButton:hover{background:#057a77;border-color:#057a77;}"
            "QPushButton:disabled{background:#d7e0e7;color:#8796a4;border-color:#d7e0e7;}"
        )
    elif role == "gold":
        button.setStyleSheet(
            "QPushButton{background:#c9942d;color:white;border:1px solid #c9942d;"
            "border-radius:8px;padding:8px 16px;font-weight:800;}"
            "QPushButton:hover{background:#b18125;border-color:#b18125;}"
            "QPushButton:disabled{background:#e2e6e9;color:#9aa7b2;border-color:#e2e6e9;}"
        )
    else:
        button.setStyleSheet(
            "QPushButton{background:white;color:#17384e;border:1px solid #b9cad7;"
            "border-radius:8px;padding:8px 15px;font-weight:750;}"
            "QPushButton:hover{background:#f4f9fb;border-color:#8fb0c2;}"
            "QPushButton:disabled{background:#f2f5f7;color:#9aa7b2;border-color:#d8e0e6;}"
        )


def _style_mode_button(button: QPushButton) -> None:
    button.setCheckable(True)
    button.setMinimumHeight(34)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:#f3f7f9;color:#415d70;border:1px solid #d6e1e8;"
        "border-radius:7px;padding:6px 13px;font-weight:700;}"
        "QPushButton:hover{background:#edf6f6;border-color:#9bcfcb;}"
        "QPushButton:checked{background:#078c89;color:white;border-color:#078c89;}"
    )


def _compact_bar(name: str) -> tuple[QFrame, QHBoxLayout]:
    bar = QFrame(objectName=name)
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(8)
    bar.setStyleSheet(
        f"QFrame#{name}{{background:#f8fbfc;border:1px solid #d8e3ea;"
        "border-radius:10px;}"
    )
    return bar, layout


def _polish_protect(page: ProtectionPage) -> None:
    if not hasattr(page, "_redesign_start_card"):
        return

    preview_layout = page.preview_card.layout()
    old_source_toolbar = page._redesign_document_mode.parentWidget()
    source_stack = page._redesign_source_stack
    document_mode = page._redesign_document_mode
    paste_mode = page._redesign_paste_mode
    protect_button = page._redesign_protect_button

    # Remove the old large source block entirely. Source selection now lives in
    # the compact workspace mode bar alongside the preview-mode controls.
    source_stack.hide()
    source_stack.setMaximumHeight(0)
    if old_source_toolbar is not None:
        old_source_toolbar.hide()
        old_source_toolbar.setMaximumHeight(0)

    # Hide the native preview tab bar. We keep the same QTabWidget and all of
    # its existing pages/functions, but drive it through the cleaner mode bar.
    page.preview_tabs.tabBar().hide()

    mode_bar = QFrame(objectName="ProtectModeBar")
    mode = QHBoxLayout(mode_bar)
    mode.setContentsMargins(9, 7, 9, 7)
    mode.setSpacing(7)

    source_label = QLabel("SOURCE")
    source_label.setStyleSheet(
        "color:#738797;font-size:10px;font-weight:800;letter-spacing:0.5px;padding-right:2px;"
    )
    mode.addWidget(source_label)

    document_mode.setParent(mode_bar)
    paste_mode.setParent(mode_bar)
    document_mode.setText("Document")
    paste_mode.setText("Paste text")
    _style_mode_button(document_mode)
    _style_mode_button(paste_mode)
    document_mode.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
    paste_mode.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
    mode.addWidget(document_mode)
    mode.addWidget(paste_mode)

    divider = QFrame()
    divider.setFrameShape(QFrame.Shape.VLine)
    divider.setStyleSheet("color:#d6e1e8;")
    divider.setFixedHeight(24)
    mode.addWidget(divider)

    view_label = QLabel("VIEW")
    view_label.setStyleSheet(
        "color:#738797;font-size:10px;font-weight:800;letter-spacing:0.5px;padding-right:2px;"
    )
    mode.addWidget(view_label)

    protected_text_mode = QPushButton("Protected text")
    compare_mode = QPushButton("Compare")
    for button in (protected_text_mode, compare_mode):
        _style_mode_button(button)
        mode.addWidget(button)
    protected_text_mode.setChecked(page.preview_tabs.currentIndex() == 0)
    compare_mode.setChecked(page.preview_tabs.currentIndex() == 1)

    mode.addStretch(1)
    mode_bar.setStyleSheet(
        "QFrame#ProtectModeBar{background:#ffffff;border:1px solid #d7e2ea;"
        "border-radius:9px;}"
    )

    preview_index = preview_layout.indexOf(page.preview_tabs)
    preview_layout.insertWidget(max(0, preview_index), mode_bar)

    # Paste text belongs inside the Original document card. The same existing
    # text_input is reused, so scan/protect behavior and signals remain intact.
    original_layout = page.original_document_panel.layout()
    original_view = page.original_view_stack
    page.text_input.setParent(page.original_document_panel)
    page.text_input.setPlaceholderText(
        "Paste the text you want PrivacyGate to scan and protect locally…"
    )
    page.text_input.setMinimumHeight(280)
    page.text_input.setMaximumHeight(16777215)
    page.text_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    page.text_input.setStyleSheet(
        "QPlainTextEdit{background:#ffffff;border:1px solid #cfdbe5;border-radius:8px;"
        "padding:14px;font-size:13px;color:#17384e;}"
        "QPlainTextEdit:focus{border:1px solid #078c89;}"
    )
    original_layout.addWidget(page.text_input, 1)
    page.text_input.hide()

    paste_hint = QLabel("Paste text here, then use Scan locally → Protect document.")
    paste_hint.setWordWrap(True)
    paste_hint.setStyleSheet(
        "background:#f3faf9;border:1px solid #d8eeeb;border-radius:7px;"
        "padding:7px 9px;color:#4b706d;font-size:11px;"
    )
    original_layout.addWidget(paste_hint)
    paste_hint.hide()

    # Professional workspace actions, directly below the two preview cards.
    bottom_bar, bottom = _compact_bar("ProtectWorkspaceActions")

    page.browse_button.setParent(bottom_bar)
    page.browse_button.setText("Upload document")
    page.browse_button.setMinimumWidth(145)
    page.browse_button.setIcon(
        QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
    )
    _style_action_button(page.browse_button, "primary")

    page.clear_button.setParent(bottom_bar)
    page.clear_button.setText("Clear")
    page.clear_button.setMinimumWidth(88)
    page.clear_button.setIcon(
        QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)
    )
    _style_action_button(page.clear_button, "secondary")

    page.scan_button.setParent(bottom_bar)
    page.scan_button.setText("Scan locally")
    page.scan_button.setMinimumWidth(135)
    page.scan_button.setIcon(
        QApplication.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
    )
    _style_action_button(page.scan_button, "secondary")

    protect_button.setParent(bottom_bar)
    protect_button.setText("Protect document")
    protect_button.setMinimumWidth(175)
    protect_button.setIcon(
        QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
    )
    _style_action_button(protect_button, "primary")

    bottom.addWidget(page.browse_button)
    bottom.addWidget(page.clear_button)
    bottom.addStretch(1)
    bottom.addWidget(page.scan_button)
    bottom.addWidget(protect_button)
    preview_layout.addWidget(bottom_bar)

    def set_source_mode(paste: bool) -> None:
        # Existing redesign click handlers still update input_tabs and scan
        # state. This only changes presentation inside the Original card.
        document_mode.setChecked(not paste)
        paste_mode.setChecked(paste)
        page.text_input.setVisible(paste)
        paste_hint.setVisible(paste)
        original_view.setVisible(not paste)
        page.browse_button.setVisible(not paste)
        if paste:
            page.preview_tabs.setCurrentIndex(1)
            compare_mode.setChecked(True)
            protected_text_mode.setChecked(False)
            QTimer.singleShot(0, page.text_input.setFocus)

    def set_preview_mode(index: int) -> None:
        page.preview_tabs.setCurrentIndex(index)
        protected_text_mode.setChecked(index == 0)
        compare_mode.setChecked(index == 1)

    document_mode.clicked.connect(lambda: QTimer.singleShot(0, lambda: set_source_mode(False)))
    paste_mode.clicked.connect(lambda: QTimer.singleShot(0, lambda: set_source_mode(True)))
    protected_text_mode.clicked.connect(lambda: set_preview_mode(0))
    compare_mode.clicked.connect(lambda: set_preview_mode(1))
    page.preview_tabs.currentChanged.connect(
        lambda index: (
            protected_text_mode.setChecked(index == 0),
            compare_mode.setChecked(index == 1),
        )
    )
    QTimer.singleShot(0, lambda: set_source_mode(paste_mode.isChecked()))

    page._polish_protect_mode_bar = mode_bar
    page._polish_protect_bottom_bar = bottom_bar
    page._polish_protect_paste_hint = paste_hint

    # Make the existing result actions read as one professional action dock.
    # Their callbacks/functions are untouched.
    quick = getattr(page, "_protect_quick_actions", None)
    if quick is not None:
        quick.setStyleSheet(
            "QFrame#ProtectQuickActions{background:#ffffff;border:1px solid #d7e2ea;"
            "border-radius:10px;}"
        )
        quick_layout = quick.layout()
        quick_layout.setContentsMargins(12, 8, 12, 9)
        quick_layout.setSpacing(5)
        save_only = getattr(page, "_protect_save_only", None)
        save_copy = getattr(page, "_protect_save_copy", None)
        save_download = getattr(page, "_protect_save_download", None)
        open_ai = getattr(page, "_protect_open_ai", None)
        if save_only is not None:
            save_only.setText("Save to Library")
            save_only.setIcon(
                QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
            )
            _style_action_button(save_only, "secondary")
        if save_copy is not None:
            save_copy.setText("Save + Copy")
            _style_action_button(save_copy, "primary")
        if save_download is not None:
            save_download.setText("Save + Download")
            save_download.setIcon(
                QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
            )
            _style_action_button(save_download, "gold")
        if open_ai is not None:
            open_ai.setText("Copy & Open ChatGPT")
            _style_action_button(open_ai, "secondary")


def _polish_restore(page: RestorePage) -> None:
    if page.preview_tabs.count() < 2:
        return

    document_tab = page.preview_tabs.widget(1)
    document_layout = document_tab.layout()
    source_toolbar = document_tab.findChild(QFrame, "EmbeddedSourceToolbar")
    if source_toolbar is not None:
        source_toolbar.hide()
        source_toolbar.setMaximumHeight(0)

    bottom_bar, bottom = _compact_bar("RestoreWorkspaceActions")

    upload = QPushButton("Upload file")
    upload.clicked.connect(page._browse_result)
    upload.setMinimumWidth(120)
    _style_action_button(upload, "primary")

    page.paste_toggle.setParent(bottom_bar)
    page.paste_toggle.setText("Paste text")
    page.paste_toggle.setMinimumWidth(105)
    _style_action_button(page.paste_toggle, "secondary")

    page.clear_button.setParent(bottom_bar)
    page.clear_button.setMinimumWidth(80)
    _style_action_button(page.clear_button, "secondary")

    original_label = QLabel("Original")
    original_label.setStyleSheet(
        "color:#516a7b;font-size:11px;font-weight:700;padding-left:8px;"
    )

    page.document_combo.setParent(bottom_bar)
    page.document_combo.setMinimumWidth(260)
    page.document_combo.setMaximumWidth(430)
    page.document_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    page.document_combo.setMinimumHeight(40)

    page.restore_button.setParent(bottom_bar)
    page.restore_button.setText("Restore locally")
    page.restore_button.setMinimumWidth(145)
    page.restore_button.setMaximumWidth(170)
    _style_action_button(page.restore_button, "primary")

    bottom.addWidget(upload)
    bottom.addWidget(page.paste_toggle)
    bottom.addWidget(page.clear_button)
    bottom.addSpacing(8)
    bottom.addWidget(original_label)
    bottom.addWidget(page.document_combo, 1)
    bottom.addWidget(page.restore_button)

    document_layout.addWidget(bottom_bar)
    page._polish_restore_bottom_bar = bottom_bar
    page._polish_restore_upload_button = upload

    page.input_text.setParent(document_tab)
    page.input_text.setMinimumHeight(92)
    page.input_text.setMaximumHeight(120)
    page.input_text.hide()
    document_layout.insertWidget(max(0, document_layout.count() - 2), page.input_text)

    def sync_paste() -> None:
        visible = page.paste_toggle.isChecked()
        page.input_text.setVisible(visible)
        page.paste_toggle.setText("Use uploaded file" if visible else "Paste text")

    page.paste_toggle.toggled.connect(lambda _checked: QTimer.singleShot(0, sync_paste))
    QTimer.singleShot(0, sync_paste)

    for button in (page.copy_button, page.download_text_button):
        _style_action_button(button, "secondary")
    _style_action_button(page.download_button, "gold")


def install_layout_polish() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_protect_init = ProtectionPage.__init__

    def protect_init(self: ProtectionPage, *args, **kwargs) -> None:
        original_protect_init(self, *args, **kwargs)
        _polish_protect(self)

    ProtectionPage.__init__ = protect_init

    original_restore_init = RestorePage.__init__

    def restore_init(self: RestorePage, *args, **kwargs) -> None:
        original_restore_init(self, *args, **kwargs)
        _polish_restore(self)

    RestorePage.__init__ = restore_init
