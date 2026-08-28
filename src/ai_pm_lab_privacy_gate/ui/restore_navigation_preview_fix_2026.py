from __future__ import annotations

"""Final Restore usability guard for navigation and preview clarity.

This layer is deliberately small and controller-safe:
- it never replaces DocumentRestoreService or Library mappings;
- it adds an always-visible way to leave/reset Restore after a completed run;
- it keeps file restores focused on the real document preview;
- it makes text-only restores readable without pretending a text Library item has
  a format-preserving PDF/Office preview.
"""

from types import MethodType

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    BLUE,
    BLUE_SOFT,
    BORDER,
    GREEN,
    GREEN_SOFT,
    INK,
    MUTED,
    WHITE,
)


_FILE_PREVIEW_SUFFIXES = {".pdf", ".docx", ".xlsx"}


def _secondary_qss() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
        "border-radius:9px;padding:7px 11px;font-size:9px;font-weight:850;}"
        "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
        "QPushButton:pressed{background:#F2F4F7;}"
        "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
    )


def _primary_qss() -> str:
    return (
        f"QPushButton{{background:{BLUE};color:#FFFFFF;border:1px solid {BLUE};"
        "border-radius:9px;padding:7px 12px;font-size:9px;font-weight:900;}"
        "QPushButton:hover{background:#1D4ED8;border-color:#1D4ED8;}"
        "QPushButton:pressed{background:#1E40AF;border-color:#1E40AF;}"
        "QPushButton:disabled{background:#D0D5DD;border-color:#D0D5DD;color:#FFFFFF;}"
    )


def _document_source_available(page) -> bool:
    path = getattr(page, "_source_path", None)
    if path is None:
        return False
    try:
        return path.suffix.lower() in _FILE_PREVIEW_SUFFIXES
    except Exception:
        return False


def _scroll_to_top(page) -> None:
    scroll = page.findChild(QScrollArea)
    if scroll is not None:
        scroll.verticalScrollBar().setValue(0)


def _focus_preview(page, *, completed: bool) -> None:
    """Choose the useful preview without inventing a file layout that is not stored."""

    tabs = page.preview_tabs
    tabs.setTabText(0, "Text preview")
    tabs.setTabText(1, "Document preview")

    has_document = _document_source_available(page)
    has_output = bool(page.output_text.toPlainText().strip())

    if has_document:
        tabs.setTabVisible(0, True)
        tabs.setTabVisible(1, True)
        # Real file restores should land on the format-aware side-by-side preview.
        if completed or getattr(page, "_source_path", None) is not None:
            tabs.setCurrentIndex(1)
        try:
            for view in (page.input_pdf_view, page.output_pdf_view):
                view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            QTimer.singleShot(80, page._fit_pdf)
        except Exception:
            pass
        return

    # A Library-origin Gmail/text item contains protected text + encrypted mappings,
    # not a format-preserving local file artifact. Keep the honest text comparison
    # front and centre after restore. During a fresh restore, keep the document tab
    # available because its command bar owns Upload/Paste/Original controls.
    tabs.setTabVisible(0, True)
    tabs.setTabVisible(1, not has_output)
    tabs.setCurrentIndex(0 if has_output else 1)


def _polish_text_preview(page) -> None:
    """Make short text/email restores readable on large desktop windows."""

    for editor in (page.protected_result_view, page.output_text):
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        editor.setMinimumHeight(430)
        editor.setStyleSheet(
            "QPlainTextEdit{background:#FFFFFF;color:#25364A;border:1px solid #DDE3EA;"
            "border-radius:11px;padding:16px;font-size:11px;selection-background-color:#D6E4FF;}"
            f"QPlainTextEdit:focus{{border:1px solid {BLUE};}}"
        )

    # The two text cards are useful working previews, not tiny diagnostic boxes.
    for label in page.findChildren(QLabel):
        normalized = " ".join(label.text().split())
        if normalized in {"AI result with placeholders", "Restored result"}:
            label.setStyleSheet(
                f"color:{INK};font-size:11px;font-weight:900;background:transparent;border:none;"
            )


def _add_navigation_bar(main_window, page) -> None:
    if getattr(page, "_restore_navigation_bar_2026", None) is not None:
        return

    layout = page.result_section.layout()
    if not isinstance(layout, QVBoxLayout):
        return

    frame = QFrame(objectName="RestoreNavigationBar2026")
    frame.setStyleSheet(
        f"QFrame#RestoreNavigationBar2026{{background:{WHITE};border:1px solid {BORDER};border-radius:10px;}}"
    )
    row = QHBoxLayout(frame)
    row.setContentsMargins(9, 7, 9, 7)
    row.setSpacing(7)

    back = QPushButton("Back to Library")
    back.setMinimumHeight(34)
    back.setStyleSheet(_secondary_qss())
    back.setIcon(icon("library", color=BLUE, size=14))
    back.setIconSize(QSize(14, 14))
    back.setToolTip("Return to the Local Library. The completed restore remains local on this device.")

    status = QLabel("Restore is local · You can return to Library or start another restore at any time.")
    status.setWordWrap(True)
    status.setStyleSheet(
        f"color:{MUTED};font-size:8px;font-weight:700;background:transparent;border:none;"
    )

    again = QPushButton("Start new restore")
    again.setMinimumHeight(34)
    again.setStyleSheet(_primary_qss())
    again.setIcon(icon("restore", color="#FFFFFF", size=14))
    again.setIconSize(QSize(14, 14))
    again.setToolTip("Clear this restore result and return to the Upload / Paste / Match controls.")

    def go_library() -> None:
        library_page = getattr(main_window, "library_page", None)
        pages = getattr(main_window, "pages", None)
        if library_page is None or pages is None:
            return
        index = int(pages.indexOf(library_page))
        if index >= 0:
            main_window._show_page(index)

    def new_restore() -> None:
        if getattr(page, "_active_worker", None) is not None:
            return
        page.clear()
        try:
            page.document_combo.setCurrentIndex(0)
        except Exception:
            pass
        page.result_metric.setText("Ready for a new restore")
        page.restore_status.setText(
            "Upload the AI result or paste protected text, then choose its original Library mapping."
        )
        status.setText("New restore ready · Upload a file or paste protected text below.")
        _focus_preview(page, completed=False)
        QTimer.singleShot(0, lambda: _scroll_to_top(page))

    back.clicked.connect(lambda _checked=False: go_library())
    again.clicked.connect(lambda _checked=False: new_restore())

    row.addWidget(back)
    row.addWidget(status, 1)
    row.addWidget(again)

    # Keep navigation immediately below the Restore workspace header, before the
    # completion/match strips and preview area. It remains visible after success.
    layout.insertWidget(1, frame)
    page._restore_navigation_bar_2026 = frame
    page._restore_navigation_status_2026 = status
    page._restore_back_library_2026 = back
    page._restore_start_new_2026 = again


def _wrap_restore_runtime(page) -> None:
    if bool(getattr(page, "_restore_navigation_runtime_wrapped_2026", False)):
        return
    page._restore_navigation_runtime_wrapped_2026 = True

    previous_restore_ready = page._restore_ready
    previous_file_loaded = page._file_loaded

    def restore_ready(page_self, payload: object) -> None:
        previous_restore_ready(payload)
        status = getattr(page_self, "_restore_navigation_status_2026", None)
        if status is not None and page_self.output_text.toPlainText().strip():
            if _document_source_available(page_self):
                status.setText(
                    "Restore complete · Review the real document preview below, return to Library, or start another restore."
                )
            else:
                status.setText(
                    "Restore complete · This item is text-based, so the readable text comparison is shown below."
                )
        _focus_preview(page_self, completed=True)
        QTimer.singleShot(0, lambda: _scroll_to_top(page_self))

    def file_loaded(page_self, payload: object) -> None:
        previous_file_loaded(payload)
        status = getattr(page_self, "_restore_navigation_status_2026", None)
        if status is not None:
            status.setText(
                "AI result loaded · Match the original mapping and restore locally."
            )
        _focus_preview(page_self, completed=False)

    page._restore_ready = MethodType(restore_ready, page)
    page._file_loaded = MethodType(file_loaded, page)


def apply_restore_navigation_preview_fix_2026(main_window) -> None:
    page = getattr(main_window, "restore_page", None)
    if page is None or bool(getattr(page, "_restore_navigation_preview_fix_2026", False)):
        return
    page._restore_navigation_preview_fix_2026 = True

    _add_navigation_bar(main_window, page)
    _polish_text_preview(page)
    _wrap_restore_runtime(page)
    _focus_preview(page, completed=bool(page.output_text.toPlainText().strip()))
