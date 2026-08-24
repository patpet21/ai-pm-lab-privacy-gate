from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
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
    source_toolbar = page._redesign_document_mode.parentWidget()
    source_stack = page._redesign_source_stack
    document_mode = page._redesign_document_mode
    paste_mode = page._redesign_paste_mode
    protect_button = page._redesign_protect_button

    # The document picker no longer consumes a large block above the previews.
    # Document/Paste remains a small mode selector; paste text expands only when needed.
    source_stack.setMinimumHeight(0)
    source_stack.setMaximumHeight(0)
    source_stack.hide()
    if source_toolbar is not None:
        source_toolbar.setMaximumHeight(88)

    bottom_bar, bottom = _compact_bar("ProtectWorkspaceActions")

    page.browse_button.setParent(bottom_bar)
    page.browse_button.setText("Upload document")
    page.browse_button.setMinimumWidth(145)
    _style_action_button(page.browse_button, "primary")

    page.clear_button.setParent(bottom_bar)
    page.clear_button.setText("Clear")
    page.clear_button.setMinimumWidth(88)
    _style_action_button(page.clear_button, "secondary")

    page.scan_button.setParent(bottom_bar)
    page.scan_button.setText("Scan locally")
    page.scan_button.setMinimumWidth(135)
    _style_action_button(page.scan_button, "secondary")

    protect_button.setParent(bottom_bar)
    protect_button.setText("Protect document")
    protect_button.setMinimumWidth(175)
    _style_action_button(protect_button, "primary")

    bottom.addWidget(page.browse_button)
    bottom.addWidget(page.clear_button)
    bottom.addStretch(1)
    bottom.addWidget(page.scan_button)
    bottom.addWidget(protect_button)

    # Place the actions directly beneath the preview workspace.
    preview_layout.addWidget(bottom_bar)
    page._polish_protect_bottom_bar = bottom_bar

    def sync_source_mode() -> None:
        paste = paste_mode.isChecked()
        source_stack.setVisible(paste)
        source_stack.setMaximumHeight(170 if paste else 0)
        if source_toolbar is not None:
            source_toolbar.setMaximumHeight(250 if paste else 88)

    document_mode.clicked.connect(lambda: QTimer.singleShot(0, sync_source_mode))
    paste_mode.clicked.connect(lambda: QTimer.singleShot(0, sync_source_mode))
    QTimer.singleShot(0, sync_source_mode)

    # Make the result actions read as one professional action dock rather than
    # four unrelated blocks. Their callbacks remain untouched.
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
            _style_action_button(save_only, "secondary")
        if save_copy is not None:
            _style_action_button(save_copy, "primary")
        if save_download is not None:
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

    # Paste text is still the same control/function, but it only consumes space
    # when the user explicitly chooses it.
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

    # Keep the existing copy/download functionality, but reduce visual noise.
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
