from __future__ import annotations

"""Local-only editing for the restored text layer.

The authoritative format-preserving restore remains owned by RestorePage and
DocumentRestoreService. This feature lets the user edit the already-restored text
in memory, then copy/download that edited text. It deliberately does not claim to
rewrite arbitrary PDF/Word/Excel layouts from plain text.
"""

from types import MethodType

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    AMBER,
    AMBER_SOFT,
    BLUE,
    BLUE_SOFT,
    BORDER,
    GREEN,
    GREEN_SOFT,
    INK,
    MUTED,
    TEXT,
)
from ai_pm_lab_privacy_gate.ui.organization_product_experience_2026 import (
    PrivacyGateProductDialog,
)


def _secondary_qss() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
        "border-radius:9px;padding:8px 11px;font-size:8.5px;font-weight:800;}"
        "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
        "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
    )


def _primary_qss() -> str:
    return (
        f"QPushButton{{background:{BLUE};color:#FFFFFF;border:1px solid {BLUE};"
        "border-radius:9px;padding:8px 11px;font-size:8.5px;font-weight:850;}"
        "QPushButton:hover{background:#1D4ED8;border-color:#1D4ED8;}"
        "QPushButton:disabled{background:#D0D5DD;border-color:#D0D5DD;color:#FFFFFF;}"
    )


class RestoreEditDialog(PrivacyGateProductDialog):
    def __init__(self, parent, *, text: str, source_suffix: str) -> None:
        super().__init__(
            parent,
            title="Edit restored result",
            subtitle="Make local changes to the restored text before copying or downloading it.",
            icon_name="document",
            width=820,
        )
        self._source_suffix = source_suffix.lower()

        toolbar = QFrame(objectName="RestoreEditToolbar")
        toolbar.setStyleSheet(
            "QFrame#RestoreEditToolbar{background:#F8FAFC;border:1px solid #EAECF0;border-radius:10px;}"
        )
        toolbar_row = QHBoxLayout(toolbar)
        toolbar_row.setContentsMargins(8, 7, 8, 7)
        toolbar_row.setSpacing(6)

        undo = QPushButton("Undo")
        redo = QPushButton("Redo")
        for button in (undo, redo):
            button.setStyleSheet(_secondary_qss())
            button.setMinimumHeight(34)
        toolbar_row.addWidget(undo)
        toolbar_row.addWidget(redo)
        toolbar_row.addSpacing(4)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find")
        self.find_input.setMinimumWidth(140)
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with")
        self.replace_input.setMinimumWidth(140)
        find_next = QPushButton("Find next")
        replace_one = QPushButton("Replace")
        replace_all = QPushButton("Replace all")
        for button in (find_next, replace_one, replace_all):
            button.setStyleSheet(_secondary_qss())
            button.setMinimumHeight(34)

        toolbar_row.addWidget(self.find_input, 1)
        toolbar_row.addWidget(self.replace_input, 1)
        toolbar_row.addWidget(find_next)
        toolbar_row.addWidget(replace_one)
        toolbar_row.addWidget(replace_all)
        self.body.addWidget(toolbar)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(text)
        self.editor.setMinimumHeight(360)
        self.editor.setStyleSheet(
            "QPlainTextEdit{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
            "border-radius:11px;padding:12px;font-size:10px;selection-background-color:#D6E4FF;}"
            f"QPlainTextEdit:focus{{border:1px solid {BLUE};}}"
        )
        self.body.addWidget(self.editor, 1)

        undo.clicked.connect(self.editor.undo)
        redo.clicked.connect(self.editor.redo)
        find_next.clicked.connect(self._find_next)
        replace_one.clicked.connect(self._replace_one)
        replace_all.clicked.connect(self._replace_all)
        self.find_input.returnPressed.connect(self._find_next)

        self.add_notice(
            "Privacy boundary: editing happens only in memory on this PC. PrivacyGate does not upload restored or edited content and does not create a cloud draft.",
            privacy=True,
        )
        if self._source_suffix in {".pdf", ".docx", ".xlsx"}:
            self.add_notice(
                "Format note: these edits apply to Copy restored text and Download edited text. The format-preserving restored PDF/Word/Excel file remains the locally restored file from the restore pass; PrivacyGate does not pretend plain-text edits preserve that document layout."
            )
        else:
            self.add_notice(
                "For a text result, your edits are used directly by Copy and Download after you apply them."
            )

        self.add_actions(
            primary_text="Apply edits locally",
            primary_callback=self.accept,
            secondary_text="Cancel",
        )
        self.editor.setFocus()

    def _find_next(self) -> None:
        term = self.find_input.text()
        if not term:
            self.find_input.setFocus()
            return
        if self.editor.find(term):
            return
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        self.editor.find(term)

    def _replace_one(self) -> None:
        term = self.find_input.text()
        if not term:
            return
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == term:
            cursor.insertText(self.replace_input.text())
            self.editor.setTextCursor(cursor)
        self._find_next()

    def _replace_all(self) -> None:
        term = self.find_input.text()
        if not term:
            return
        current = self.editor.toPlainText()
        updated = current.replace(term, self.replace_input.text())
        if updated == current:
            return
        position = self.editor.textCursor().position()
        self.editor.setPlainText(updated)
        cursor = self.editor.textCursor()
        cursor.setPosition(min(position, len(updated)))
        self.editor.setTextCursor(cursor)

    @property
    def edited_text(self) -> str:
        return self.editor.toPlainText()


class FormatFileBoundaryDialog(PrivacyGateProductDialog):
    def __init__(self, parent, *, label: str) -> None:
        super().__init__(
            parent,
            title=f"Download restored {label}",
            subtitle="Your local text edits and the format-preserving restored file are intentionally kept as separate outputs.",
            icon_name="download",
            width=620,
        )
        self.add_notice(
            "The edited text is available through Download edited text. This file download keeps the original restored document layout and therefore does not include later plain-text edits."
        )
        self.add_notice(
            "Both outputs remain local. No restored or edited content is sent to Supabase or any AI service.",
            privacy=True,
        )
        self.add_actions(
            primary_text=f"Download restored {label}",
            primary_callback=self.accept,
            secondary_text="Cancel",
        )


def _source_suffix(page) -> str:
    path = getattr(page, "_source_path", None)
    return str(getattr(path, "suffix", "") or "").lower()


def _sync_edit_state(page) -> None:
    edited = bool(getattr(page, "_restore_2026_edited_locally", False))
    notice = getattr(page, "_restore_2026_edit_notice", None)
    edit_button = getattr(page, "_restore_2026_edit_button", None)
    frame = getattr(page, "_restore_2026_final_actions", None)
    has_result = bool(page.output_text.toPlainText())

    if frame is not None:
        frame.setVisible(has_result)
    if edit_button is not None:
        edit_button.setEnabled(has_result)
        edit_button.setText("Edit again" if edited else "Edit restored result")

    suffix = _source_suffix(page)
    if edited:
        page.download_text_button.setText("Download edited text")
        if suffix in {".pdf", ".docx", ".xlsx"}:
            labels = {".pdf": "PDF", ".docx": "Word", ".xlsx": "Excel"}
            page.download_button.setText(f"Download restored {labels[suffix]} · layout")
            page.download_button.setToolTip(
                "Downloads the format-preserving restored file. Later text edits are available through Download edited text."
            )
            if notice is not None:
                notice.setText(
                    "Edited locally · Copy and Download edited text include your changes. The format-preserving document remains the original restored output."
                )
                notice.show()
        else:
            if notice is not None:
                notice.setText("Edited locally · Copy and Download use your current text.")
                notice.show()
    else:
        page.download_text_button.setText("Download text")
        if notice is not None:
            notice.hide()


def _open_editor(page) -> None:
    current = page.output_text.toPlainText()
    if not current:
        return
    dialog = RestoreEditDialog(page, text=current, source_suffix=_source_suffix(page))
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    updated = dialog.edited_text
    if updated == current:
        return
    page.output_text.setPlainText(updated)
    page._restore_2026_edited_locally = True
    page.result_metric.setText("Restored locally · edited locally")
    page.result_metric.setStyleSheet(
        f"background:{GREEN_SOFT};color:{GREEN};border:1px solid #BBF7D0;"
        "border-radius:8px;padding:5px 8px;font-size:7.5px;font-weight:900;"
    )
    _sync_edit_state(page)


def _build_final_actions(page) -> None:
    result_layout = page.result_section.layout()
    if not isinstance(result_layout, QVBoxLayout):
        return

    frame = QFrame(objectName="Restore2026FinalActions")
    frame.setStyleSheet(
        f"QFrame#Restore2026FinalActions{{background:#F8FAFC;border:1px solid {BORDER};border-radius:11px;}}"
    )
    box = QVBoxLayout(frame)
    box.setContentsMargins(10, 8, 10, 8)
    box.setSpacing(6)

    heading = QHBoxLayout()
    title = QLabel("Restored result ready — choose the next action")
    title.setStyleSheet(
        f"color:{TEXT};font-size:8px;font-weight:850;background:transparent;border:none;"
    )
    local = QLabel("LOCAL")
    local.setStyleSheet(
        f"background:{GREEN_SOFT};color:{GREEN};border:1px solid #BBF7D0;"
        "border-radius:7px;padding:3px 7px;font-size:7px;font-weight:900;"
    )
    heading.addWidget(title)
    heading.addStretch(1)
    heading.addWidget(local)
    box.addLayout(heading)

    row = QHBoxLayout()
    row.setSpacing(7)
    page.copy_button.setText("Copy restored text")
    page.download_text_button.setText("Download text")
    for button in (page.copy_button, page.download_text_button):
        button.setStyleSheet(_secondary_qss())
        button.setMinimumHeight(39)
        row.addWidget(button, 1)

    page.download_button.setStyleSheet(_secondary_qss())
    page.download_button.setMinimumHeight(39)
    row.addWidget(page.download_button, 1)

    edit = QPushButton("Edit restored result")
    edit.setStyleSheet(_primary_qss())
    edit.setMinimumHeight(39)
    edit.setIcon(icon("edit", color="#FFFFFF", size=15))
    edit.clicked.connect(lambda _checked=False: _open_editor(page))
    row.addWidget(edit, 1)
    box.addLayout(row)

    edit_notice = QLabel()
    edit_notice.setWordWrap(True)
    edit_notice.setStyleSheet(
        f"background:{AMBER_SOFT};color:{AMBER};border:1px solid #FED7AA;border-radius:8px;"
        "padding:6px 8px;font-size:7.5px;font-weight:750;"
    )
    edit_notice.hide()
    box.addWidget(edit_notice)

    index = result_layout.indexOf(page.preview_tabs)
    result_layout.insertWidget(index + 1 if index >= 0 else result_layout.count(), frame)

    page._restore_2026_final_actions = frame
    page._restore_2026_edit_button = edit
    page._restore_2026_edit_notice = edit_notice
    frame.hide()


def apply_mockup_restore_edit_2026(main_window) -> None:
    page = getattr(main_window, "restore_page", None)
    if page is None or bool(getattr(page, "_privacygate_mockup_restore_edit_2026", False)):
        return
    page._privacygate_mockup_restore_edit_2026 = True
    page._restore_2026_edited_locally = False

    _build_final_actions(page)

    previous_set_actions = page._set_result_actions

    def set_actions_with_edit(self, enabled: bool) -> None:
        previous_set_actions(enabled)
        edit_button = getattr(self, "_restore_2026_edit_button", None)
        frame = getattr(self, "_restore_2026_final_actions", None)
        if edit_button is not None:
            edit_button.setEnabled(enabled)
        if frame is not None:
            frame.setVisible(bool(enabled and self.output_text.toPlainText()))
        if enabled:
            _sync_edit_state(self)

    page._set_result_actions = MethodType(set_actions_with_edit, page)

    previous_restore_ready = page._restore_ready

    def restore_ready_with_edit_reset(self, payload: object) -> None:
        self._restore_2026_edited_locally = False
        previous_restore_ready(payload)
        _sync_edit_state(self)

    page._restore_ready = MethodType(restore_ready_with_edit_reset, page)

    previous_clear = page.clear

    def clear_with_edit_reset(self) -> None:
        self._restore_2026_edited_locally = False
        previous_clear()
        frame = getattr(self, "_restore_2026_final_actions", None)
        if frame is not None:
            frame.hide()
        _sync_edit_state(self)

    page.clear = MethodType(clear_with_edit_reset, page)

    # The original signal captured the old bound _download method during
    # RestorePage construction. Reconnect only this one button so an edited text
    # result cannot be mistaken for an edited layout-preserving file.
    original_download = page._download
    try:
        page.download_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass

    def download_with_edit_boundary() -> None:
        edited = bool(getattr(page, "_restore_2026_edited_locally", False))
        suffix = _source_suffix(page)
        if edited and suffix in {".pdf", ".docx", ".xlsx"}:
            labels = {".pdf": "PDF", ".docx": "Word", ".xlsx": "Excel"}
            if FormatFileBoundaryDialog(page, label=labels[suffix]).exec() != QDialog.DialogCode.Accepted:
                return
        if edited and suffix == ".txt":
            page._download_text()
            return
        original_download()

    page.download_button.clicked.connect(download_with_edit_boundary)
    _sync_edit_state(page)
