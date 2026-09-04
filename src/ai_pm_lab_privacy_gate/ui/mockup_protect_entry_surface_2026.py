from __future__ import annotations

"""Final source-entry polish for Protect.

Presentation only. Existing Upload/Paste/Connected Source callbacks remain
canonical. This layer owns only the visual state of the large Original and
Protected document surfaces.
"""

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon


BLUE = "#2563EB"
BLUE_DARK = "#1D4ED8"
BLUE_SOFT = "#EFF6FF"
TEAL = "#0B858A"
TEAL_DARK = "#096E75"
TEAL_SOFT = "#F0FAFA"
GREEN = "#16794D"
NAVY = "#17384E"
MUTED = "#667085"
SUPPORTED_DROP_SUFFIXES = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".txt",
}


class _ProtectSourceDropZone(QFrame):
    """Visual drop target delegating a local path to the existing source state."""

    def __init__(self, on_drop: Callable[[str], None]) -> None:
        super().__init__()
        self._on_drop = on_drop
        self.setObjectName("ProtectSourceEmptyState")
        self.setAcceptDrops(True)
        self.setProperty("dragActive", False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(360)
        self.setStyleSheet(
            "QFrame#ProtectSourceEmptyState{background:#FCFEFF;border:1px solid #D8E7EE;"
            "border-radius:14px;}"
            "QFrame#ProtectSourceEmptyState[dragActive='true']{background:#F0F7FF;"
            "border:2px dashed #2563EB;}"
        )

    def _set_drag_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    @staticmethod
    def _supported_local_path(event) -> str:  # noqa: ANN001
        mime = event.mimeData()
        if mime is None or not mime.hasUrls():
            return ""
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if Path(path).suffix.lower() in SUPPORTED_DROP_SUFFIXES:
                return path
        return ""

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001, N802
        if self._supported_local_path(event):
            self._set_drag_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001, N802
        self._set_drag_active(False)
        event.accept()

    def dropEvent(self, event) -> None:  # noqa: ANN001, N802
        path = self._supported_local_path(event)
        self._set_drag_active(False)
        if not path:
            event.ignore()
            return
        self._on_drop(path)
        event.acceptProposedAction()


def _format_chip(label: str, accent: str, background: str) -> QFrame:
    chip = QFrame(objectName="ProtectFormatChip")
    chip.setStyleSheet(
        f"QFrame#ProtectFormatChip{{background:{background};border:1px solid {accent}33;"
        "border-radius:9px;}"
    )
    row = QHBoxLayout(chip)
    row.setContentsMargins(3, 4, 3, 4)
    row.setSpacing(2)

    mark = QLabel()
    mark.setFixedSize(12, 12)
    mark.setPixmap(icon("document", color=accent, size=11).pixmap(11, 11))
    mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
    text = QLabel(label)
    text.setStyleSheet(
        f"color:{accent};font-size:6px;font-weight:900;background:transparent;border:none;"
    )
    row.addWidget(mark)
    row.addWidget(text)
    return chip


def _style_source_buttons(page) -> None:
    """Keep canonical compatibility actions functional but visually quiet."""
    upload = getattr(page, "_protect_source_upload", None)
    paste = getattr(page, "_protect_source_paste", None)
    connected = getattr(page, "_protect_source_connected", None)
    for button in (upload, paste, connected):
        if button is not None:
            button.setMinimumHeight(40)


def _build_empty_state(page) -> _ProtectSourceDropZone:
    def select_dropped_file(path: str) -> None:
        page._protect_entry_force_empty = False
        document_mode = getattr(page, "_redesign_document_mode", None)
        paste_mode = getattr(page, "_redesign_paste_mode", None)
        if document_mode is not None:
            document_mode.setChecked(True)
        if paste_mode is not None:
            paste_mode.setChecked(False)
        page.pdf_path.setText(path)
        page.pdf_path.setToolTip(path)
        try:
            page.input_tabs.setCurrentIndex(1)
        except Exception:
            pass

    surface = _ProtectSourceDropZone(select_dropped_file)
    root = QVBoxLayout(surface)
    root.setContentsMargins(30, 38, 30, 32)
    root.setSpacing(12)
    root.addStretch(1)

    hero = QLabel()
    hero.setFixedSize(70, 70)
    hero.setPixmap(icon("document", color="#4B9CF5", size=42).pixmap(42, 42))
    hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hero.setStyleSheet(
        "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #EFF8FF,stop:1 #F0FAFA);"
        "border:1px solid #CFE5EF;border-radius:18px;padding:10px;"
    )
    root.addWidget(hero, 0, Qt.AlignmentFlag.AlignHCenter)

    title = QLabel("No document loaded")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(
        f"color:{NAVY};font-size:17px;font-weight:950;background:transparent;border:none;"
    )
    root.addWidget(title)

    subtitle = QLabel()
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(
        f"color:{MUTED};font-size:9px;font-weight:600;background:transparent;border:none;"
    )
    root.addWidget(subtitle)

    actions = QHBoxLayout()
    actions.setSpacing(0)
    actions.addStretch(1)

    choose = QPushButton("Choose a file")
    choose.setCursor(Qt.CursorShape.PointingHandCursor)
    choose.setMinimumSize(195, 48)
    choose.setIcon(icon("cloud", color=TEAL, size=20))
    choose.setIconSize(QSize(20, 20))
    choose.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#0B7180;border:1px solid #7BC4CA;"
        "border-radius:11px;padding:10px 18px;font-size:10px;font-weight:900;}"
        "QPushButton:hover{background:#F0FAFA;border-color:#47A9B1;color:#096E75;}"
    )

    upload_local = QPushButton("Upload local")
    upload_local.setCursor(Qt.CursorShape.PointingHandCursor)
    upload_local.setMinimumSize(145, 48)
    upload_local.setIcon(icon("upload", color=BLUE, size=19))
    upload_local.setIconSize(QSize(19, 19))
    upload_local.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#2563EB;border:1px solid #BFD1FE;"
        "border-radius:11px;padding:10px 15px;font-size:9px;font-weight:850;}"
        "QPushButton:hover{background:#EFF6FF;border-color:#9DB7F8;}"
    )

    actions.addWidget(choose)
    # Preserve the canonical local-upload callback for compatibility, but the
    # approved empty state has one context-aware "Choose" action only.
    upload_local.hide()
    upload_local.setMaximumWidth(0)
    actions.addStretch(1)
    root.addLayout(actions)

    drag_hint = QLabel("or drag & drop a local file here")
    drag_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    drag_hint.setStyleSheet(
        f"color:{TEAL_DARK};font-size:8.5px;font-weight:800;background:transparent;border:none;"
    )
    drag_hint.hide()
    drag_hint.setMaximumHeight(0)

    formats_label = QLabel("Supported local formats")
    formats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    formats_label.setStyleSheet(
        f"color:{MUTED};font-size:7.5px;font-weight:750;background:transparent;border:none;"
    )
    root.addWidget(formats_label)

    formats = QHBoxLayout()
    formats.setSpacing(6)
    formats.addStretch(1)
    for label, accent, background in (
        ("PDF", "#D92D20", "#FFF3F2"),
        ("DOCX", "#175CD3", "#EFF8FF"),
        ("PPTX", "#C4320A", "#FFF6ED"),
        ("XLSX", "#067647", "#ECFDF3"),
        ("PNG", "#7A5AF8", "#F4F3FF"),
        ("JPG", "#6941C6", "#F4F3FF"),
        ("TXT", "#475467", "#F2F4F7"),
    ):
        formats.addWidget(_format_chip(label, accent, background))
    formats.addStretch(1)
    root.addLayout(formats)

    privacy = QLabel("Files stay on this device until PrivacyGate creates the protected copy.")
    privacy.setAlignment(Qt.AlignmentFlag.AlignCenter)
    privacy.setWordWrap(True)
    privacy.setStyleSheet(
        f"color:{MUTED};font-size:7.5px;font-weight:600;background:transparent;border:none;"
    )
    root.addWidget(privacy)
    root.addStretch(1)

    context_bar = getattr(page, "_managed_workspace_context_bar", None)

    def provider_key() -> str:
        if context_bar is None:
            return ""
        return str(context_bar.source_combo.currentData() or "")

    def refresh_source_copy(*_args) -> None:
        provider = provider_key()
        if provider == "gmail":
            choose.setText("Choose an email")
            subtitle.setText(
                "Choose an email from the connected Gmail account or switch to Paste text."
            )
        elif provider == "google_drive":
            choose.setText("Choose a Drive file")
            subtitle.setText(
                "Choose a file from the connected Google Drive account or switch to Paste text."
            )
        else:
            choose.setText("Choose a file")
            subtitle.setText(
                "Choose a source above or browse to upload your document."
            )

    def choose_current_source() -> None:
        page._protect_entry_force_empty = False
        provider = provider_key()
        connected_action = getattr(page, "_protect_2026_connected_browse_action", None)
        if connected_action is None and context_bar is not None:
            connected_action = getattr(context_bar, "browse", None)
        if provider in {"gmail", "google_drive"} and connected_action is not None:
            connected_action.click()
            return
        page.browse_button.click()

    choose.clicked.connect(choose_current_source)
    upload_local.clicked.connect(page.browse_button.click)
    if context_bar is not None:
        context_bar.source_combo.currentIndexChanged.connect(refresh_source_copy)
    refresh_source_copy()

    page._protect_empty_choose = choose
    page._protect_empty_upload = upload_local
    page._protect_empty_source_subtitle = subtitle
    return surface


def _build_protected_empty_state() -> QFrame:
    surface = QFrame(objectName="ProtectProtectedEmptyState")
    surface.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    surface.setMinimumHeight(360)
    surface.setStyleSheet(
        "QFrame#ProtectProtectedEmptyState{"
        "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #FBFFFF,stop:1 #F2FBFA);"
        "border:1px solid #BFE3E1;border-radius:14px;}"
    )
    root = QVBoxLayout(surface)
    root.setContentsMargins(30, 38, 30, 32)
    root.setSpacing(12)
    root.addStretch(1)

    hero = QLabel()
    hero.setFixedSize(78, 78)
    hero.setPixmap(icon("protect", color=TEAL, size=48).pixmap(48, 48))
    hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hero.setStyleSheet(
        "background:#F0FAFA;border:1px solid #C8E8E6;border-radius:20px;padding:12px;"
    )
    root.addWidget(hero, 0, Qt.AlignmentFlag.AlignHCenter)

    title = QLabel("Protected version will appear here")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(
        f"color:{NAVY};font-size:17px;font-weight:950;background:transparent;border:none;"
    )
    root.addWidget(title)

    detail = QLabel(
        "Your content will be scanned locally and the protected version will be shown here."
    )
    detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
    detail.setWordWrap(True)
    detail.setMaximumWidth(460)
    detail.setStyleSheet(
        f"color:{MUTED};font-size:9px;font-weight:600;background:transparent;border:none;"
    )
    root.addWidget(detail, 0, Qt.AlignmentFlag.AlignHCenter)
    root.addStretch(1)
    return surface


def _install_protected_empty_state(page) -> None:
    panel = getattr(page, "protected_document_panel", None)
    stack = getattr(page, "protected_view_stack", None)
    if panel is None or stack is None or getattr(page, "_protect_protected_empty_state", None) is not None:
        return
    layout = panel.layout()
    if not isinstance(layout, QVBoxLayout):
        return

    empty = _build_protected_empty_state()
    stack_index = layout.indexOf(stack)
    layout.insertWidget(max(1, stack_index), empty, 1)
    page._protect_protected_empty_state = empty

    def has_protected_result() -> bool:
        if getattr(page, "current_result", None) is not None:
            return True
        if bool(dict(getattr(page, "_protect_session_results", {}) or {})):
            return True
        if bool(dict(getattr(page, "_gmail_component_results", {}) or {})):
            return True
        return False

    def sync(*_args) -> None:
        ready = has_protected_result()
        empty.setVisible(not ready)
        stack.setVisible(ready)
        if not ready:
            protected_text = getattr(page, "_privacygate_text_compare_protected", None)
            if protected_text is not None:
                protected_text.hide()

    def schedule(*_args) -> None:
        for delay in (0, 150, 450, 900, 1600):
            QTimer.singleShot(delay, sync)

    page.clear_button.clicked.connect(schedule)
    page.scan_button.clicked.connect(schedule)
    page.pdf_path.textChanged.connect(schedule)
    page.text_input.textChanged.connect(schedule)
    page.preview.textChanged.connect(schedule)

    # A legacy preview synchronizer can re-show the protected viewport after
    # this presentation layer has installed the empty state. Keep the two real
    # widgets mutually exclusive so no inactive grey viewport leaks underneath.
    guard_timer = QTimer(page)
    guard_timer.setInterval(300)
    guard_timer.timeout.connect(sync)
    guard_timer.start()
    page._protect_protected_empty_state_timer = guard_timer

    sync()
    page._protect_protected_empty_state_sync = sync


def _install_empty_state(page) -> None:
    panel = getattr(page, "original_document_panel", None)
    stack = getattr(page, "original_view_stack", None)
    if panel is None or stack is None or getattr(page, "_protect_source_empty_state", None) is not None:
        return

    layout = panel.layout()
    if not isinstance(layout, QVBoxLayout):
        return

    empty_state = _build_empty_state(page)
    layout.insertWidget(1, empty_state, 1)
    page._protect_source_empty_state = empty_state
    page._protect_entry_force_empty = False

    page.text_input.setMinimumHeight(360)
    page.text_input.setMaximumHeight(16777215)
    page.text_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def content_state() -> str:
        has_file = bool(str(page.pdf_path.text() or "").strip())
        has_text = bool(str(page.text_input.toPlainText() or "").strip())
        document = getattr(page, "current_document", None)
        current_kind = str(getattr(document, "source_kind", "") or "")
        has_document = document is not None
        session_sources = dict(getattr(page, "_protect_session_sources", {}) or {})
        active_key = str(getattr(page, "_privacygate_active_source_key", "") or "")
        has_gmail = bool(tuple(getattr(page, "_gmail_component_manifest", ()) or ()))
        has_external = bool(dict(getattr(page, "_external_source_metadata", {}) or {}))
        paste_mode = getattr(page, "_redesign_paste_mode", None)
        paste_active = bool(paste_mode is not None and paste_mode.isChecked())

        if bool(getattr(page, "_protect_entry_force_empty", False)) and not has_file and not has_text:
            return "EMPTY"
        if has_gmail or has_external:
            return "DOCUMENT"
        if paste_active or current_kind == "text" or active_key == "text":
            return "PASTE"
        if has_text and not has_file:
            return "PASTE"
        if has_file or has_document or bool(session_sources):
            return "DOCUMENT"
        return "EMPTY"

    def sync_entry_state(*_args) -> None:
        state = content_state()
        empty_state.setVisible(state == "EMPTY")
        page.text_input.setVisible(state == "PASTE")
        stack.setVisible(state == "DOCUMENT")

    def release_for_new_source(*_args) -> None:
        page._protect_entry_force_empty = False
        QTimer.singleShot(0, sync_entry_state)

    def text_changed() -> None:
        if str(page.text_input.toPlainText() or "").strip():
            page._protect_entry_force_empty = False
        sync_entry_state()

    def file_changed(value: str) -> None:
        if str(value or "").strip():
            page._protect_entry_force_empty = False
        sync_entry_state()

    def reset_after_clear() -> None:
        page._protect_entry_force_empty = True
        paste_mode = getattr(page, "_redesign_paste_mode", None)
        document_mode = getattr(page, "_redesign_document_mode", None)
        if paste_mode is not None:
            paste_mode.setChecked(False)
        if document_mode is not None:
            document_mode.setChecked(True)
        try:
            page.input_tabs.setCurrentIndex(1)
        except Exception:
            pass
        sync_entry_state()
        QTimer.singleShot(80, sync_entry_state)
        QTimer.singleShot(250, sync_entry_state)

    page.text_input.textChanged.connect(text_changed)
    page.pdf_path.textChanged.connect(file_changed)
    page.clear_button.clicked.connect(lambda: QTimer.singleShot(0, reset_after_clear))

    paste_mode = getattr(page, "_redesign_paste_mode", None)
    document_mode = getattr(page, "_redesign_document_mode", None)
    if paste_mode is not None:
        paste_mode.toggled.connect(release_for_new_source)
    if document_mode is not None:
        document_mode.toggled.connect(lambda _checked: QTimer.singleShot(0, sync_entry_state))

    for button in (
        getattr(page, "_protect_source_upload", None),
        getattr(page, "_protect_source_paste", None),
        getattr(page, "_protect_source_connected", None),
        getattr(page, "_protect_empty_choose", None),
        getattr(page, "_protect_empty_upload", None),
    ):
        if button is not None:
            button.clicked.connect(release_for_new_source)

    sync_entry_state()
    page._protect_source_empty_state_sync = sync_entry_state


def apply_mockup_protect_entry_surface_2026(main_window) -> None:
    """Apply the source-entry visual layer without replacing Protect behavior."""
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_privacygate_protect_entry_surface_2026", False):
        return
    page._privacygate_protect_entry_surface_2026 = True

    _style_source_buttons(page)
    _install_empty_state(page)
    _install_protected_empty_state(page)
