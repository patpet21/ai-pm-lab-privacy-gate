from __future__ import annotations

"""Final source-entry polish for Protect.

Presentation only. Existing Upload/Paste/Connected Source callbacks remain
canonical. This layer styles those controls and owns only the visual state of the
large Original document entry surface: EMPTY, PASTE, or DOCUMENT.
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
GREEN = "#16794D"
GREEN_DARK = "#11623F"
GREEN_SOFT = "#EAF8F0"
GREEN_BORDER = "#A9DCC0"
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
        self.setMinimumHeight(420)
        self.setStyleSheet(
            "QFrame#ProtectSourceEmptyState{background:#FBFDFF;border:1px dashed #B9CBEA;"
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
    row.setContentsMargins(8, 6, 8, 6)
    row.setSpacing(5)

    mark = QLabel()
    mark.setFixedSize(18, 18)
    mark.setPixmap(icon("document", color=accent, size=16).pixmap(16, 16))
    mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
    text = QLabel(label)
    text.setStyleSheet(
        f"color:{accent};font-size:7.5px;font-weight:900;background:transparent;border:none;"
    )
    row.addWidget(mark)
    row.addWidget(text)
    return chip


def _style_source_buttons(page) -> None:
    """Style only; never reparent the command-row buttons."""
    upload = getattr(page, "_protect_source_upload", None)
    paste = getattr(page, "_protect_source_paste", None)
    connected = getattr(page, "_protect_source_connected", None)
    if upload is None or paste is None or connected is None:
        return

    upload.setMinimumHeight(40)
    upload.setMinimumWidth(108)
    upload.setIcon(icon("upload", color="#FFFFFF", size=17))
    upload.setIconSize(QSize(17, 17))
    upload.setStyleSheet(
        f"QPushButton{{background:{BLUE};color:#FFFFFF;border:1px solid {BLUE};"
        "border-radius:9px;padding:8px 14px;font-size:9px;font-weight:900;}"
        f"QPushButton:hover{{background:{BLUE_DARK};border-color:{BLUE_DARK};}}"
        "QPushButton:disabled{background:#D0D5DD;color:#FFFFFF;border-color:#D0D5DD;}"
    )

    paste.setMinimumHeight(40)
    paste.setMinimumWidth(112)
    paste.setIcon(icon("paste", color=GREEN, size=17))
    paste.setIconSize(QSize(17, 17))
    paste.setStyleSheet(
        f"QPushButton{{background:{GREEN_SOFT};color:{GREEN};border:1px solid {GREEN_BORDER};"
        "border-radius:9px;padding:8px 14px;font-size:9px;font-weight:900;}"
        f"QPushButton:hover{{background:#DDF3E7;color:{GREEN_DARK};border-color:#7FC99E;}}"
        "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
    )

    connected.setMinimumHeight(40)
    connected.setIcon(icon("cloud", color=BLUE, size=17))
    connected.setIconSize(QSize(17, 17))
    connected.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
        "border-radius:9px;padding:8px 13px;font-size:9px;font-weight:800;}"
        f"QPushButton:hover{{background:{BLUE_SOFT};color:{BLUE_DARK};border-color:#AFC7FA;}}"
        "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
    )


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
    root.setContentsMargins(28, 36, 28, 30)
    root.setSpacing(12)
    root.addStretch(1)

    hero = QLabel()
    hero.setFixedSize(52, 52)
    hero.setPixmap(icon("upload", color=BLUE, size=34).pixmap(34, 34))
    hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hero.setStyleSheet(
        f"background:{BLUE_SOFT};border:1px solid #C7D7FE;border-radius:14px;padding:8px;"
    )
    root.addWidget(hero, 0, Qt.AlignmentFlag.AlignHCenter)

    title = QLabel("Add content to protect")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(
        f"color:{NAVY};font-size:17px;font-weight:950;background:transparent;border:none;"
    )
    root.addWidget(title)

    subtitle = QLabel("Upload a document, paste text, or drag and drop a file into this area.")
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(
        f"color:{MUTED};font-size:9px;font-weight:600;background:transparent;border:none;"
    )
    root.addWidget(subtitle)

    actions = QHBoxLayout()
    actions.setSpacing(10)
    actions.addStretch(1)

    upload = QPushButton("Upload file")
    upload.setCursor(Qt.CursorShape.PointingHandCursor)
    upload.setMinimumSize(170, 48)
    upload.setIcon(icon("upload", color="#FFFFFF", size=20))
    upload.setIconSize(QSize(20, 20))
    upload.setStyleSheet(
        f"QPushButton{{background:{BLUE};color:#FFFFFF;border:1px solid {BLUE};"
        "border-radius:11px;padding:10px 18px;font-size:11px;font-weight:900;}"
        f"QPushButton:hover{{background:{BLUE_DARK};border-color:{BLUE_DARK};}}"
    )

    paste = QPushButton("Paste text")
    paste.setCursor(Qt.CursorShape.PointingHandCursor)
    paste.setMinimumSize(170, 48)
    paste.setIcon(icon("paste", color=GREEN, size=20))
    paste.setIconSize(QSize(20, 20))
    paste.setStyleSheet(
        f"QPushButton{{background:{GREEN_SOFT};color:{GREEN};border:1px solid {GREEN_BORDER};"
        "border-radius:11px;padding:10px 18px;font-size:11px;font-weight:900;}"
        f"QPushButton:hover{{background:#DDF3E7;color:{GREEN_DARK};border-color:#7FC99E;}}"
    )

    actions.addWidget(upload)
    actions.addWidget(paste)
    actions.addStretch(1)
    root.addLayout(actions)

    drag_hint = QLabel("Drag & drop files here")
    drag_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    drag_hint.setStyleSheet(
        f"color:{BLUE_DARK};font-size:8.5px;font-weight:850;background:transparent;border:none;"
    )
    root.addWidget(drag_hint)

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
        ("WORD", "#175CD3", "#EFF8FF"),
        ("PPT", "#C4320A", "#FFF6ED"),
        ("EXCEL", "#067647", "#ECFDF3"),
        ("PNG/JPG", "#7A5AF8", "#F4F3FF"),
        ("TXT", "#475467", "#F2F4F7"),
    ):
        formats.addWidget(_format_chip(label, accent, background))
    formats.addStretch(1)
    root.addLayout(formats)

    privacy = QLabel("Files stay on this device until PrivacyGate creates the protected copy.")
    privacy.setAlignment(Qt.AlignmentFlag.AlignCenter)
    privacy.setStyleSheet(
        f"color:{MUTED};font-size:7.5px;font-weight:600;background:transparent;border:none;"
    )
    root.addWidget(privacy)
    root.addStretch(1)

    top_upload = getattr(page, "_protect_source_upload", None)
    top_paste = getattr(page, "_protect_source_paste", None)
    if top_upload is not None:
        upload.clicked.connect(top_upload.click)
    else:
        upload.clicked.connect(page.browse_button.click)
    if top_paste is not None:
        paste.clicked.connect(top_paste.click)
    else:
        paste.clicked.connect(lambda: page.text_input.setFocus())

    page._protect_empty_upload = upload
    page._protect_empty_paste = paste
    return surface


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

    # The existing text editor already belongs to the proven Protect runtime.
    # We only control whether it or the document preview is visible.
    page.text_input.setMinimumHeight(420)
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

        # Clear is authoritative for the entry surface even if an older runtime
        # still clears compatibility/session metadata a few milliseconds later.
        if bool(getattr(page, "_protect_entry_force_empty", False)) and not has_file and not has_text:
            return "EMPTY"

        # Connected sources own their own document/body presentation. Do not turn
        # those into the manual paste editor merely because they contain text.
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
        # Some compatibility clear handlers finish asynchronously. Reassert the
        # same visual state after they have completed without polling forever.
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
        getattr(page, "_protect_empty_upload", None),
        getattr(page, "_protect_empty_paste", None),
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
