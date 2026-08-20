from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton

from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage


_INSTALLED = False


def _quiet_save_to_library(page: ProtectionPage):
    """Save the current protected result using the source name as the Library title.

    The old flow asked for a second title in a modal dialog. For the primary
    Protect flow that is unnecessary friction: the source filename (or first
    text line) already gives the user a useful, editable Library title later.
    """
    if page.current_document is None or page.current_result is None:
        return None
    title = page._derive_title()
    source_name = (
        page.current_document.source_path.name
        if page.current_document.source_path
        else "Pasted text"
    )
    labels = tuple(
        part.strip() for part in page.labels_input.text().split(",") if part.strip()
    )
    document = page.library.save(
        title=title,
        source_kind=page.current_document.source_kind,
        source_name=source_name,
        profile_key=page.profile_combo.currentData(),
        result=page.current_result,
        labels=labels,
    )
    page.library_changed.emit(document.document_id)
    return document


def _status(page: ProtectionPage, message: str) -> None:
    label = getattr(page, "_redesign_review_metric", None)
    if label is not None:
        label.setText(message)


def _save_and_copy(page: ProtectionPage) -> None:
    if page.current_result is None:
        return
    page._redesign_begin_operation("verify", "Final privacy check before saving and copying…")
    try:
        if not page._confirm_residual_risk("saving and copying"):
            return
        saved = _quiet_save_to_library(page)
        if saved is None:
            return
        QApplication.clipboard().setText(page.current_result.combined_text)
        _status(page, "Saved to Library + copied")
    finally:
        page._redesign_end_operation("verify")


def _save_and_download(page: ProtectionPage) -> None:
    if page.current_result is None or page.current_document is None:
        return
    page._redesign_begin_operation("verify", "Final privacy check before saving and downloading…")
    try:
        if not page._confirm_residual_risk("saving and downloading"):
            return
        saved = _quiet_save_to_library(page)
        if saved is None:
            return

        document = page.current_document
        result = page.current_result
        title = saved.title

        if document.source_kind == "pdf":
            suggested = f"{title}_protected.pdf"
            path, _ = QFileDialog.getSaveFileName(
                page, "Download protected PDF", suggested, "PDF files (*.pdf)"
            )
            if not path:
                _status(page, "Saved to Library")
                return
            destination = Path(path)
            if destination.suffix.lower() != ".pdf":
                destination = destination.with_suffix(".pdf")
            page._redesign_begin_operation("export", "Creating protected PDF locally…")
            used_safe_layout = False
            try:
                try:
                    page.service.save_protected_pdf(
                        result, destination, source_document=document
                    )
                except ValueError:
                    # Some PDFs expose text in an order that cannot be mapped back
                    # to every visual coordinate safely. Falling back automatically
                    # is safer and much clearer than surfacing a developer error.
                    used_safe_layout = True
                    page.service.save_protected_pdf(
                        result, destination, source_document=None
                    )
            finally:
                page._redesign_end_operation("export")
            _status(
                page,
                "Saved + downloaded (safe PDF layout)"
                if used_safe_layout
                else "Saved + downloaded",
            )
            return

        if document.source_kind in {"docx", "xlsx"}:
            suffix = f".{document.source_kind}"
            label = "Word" if suffix == ".docx" else "Excel"
            suggested = f"{title}_protected{suffix}"
            path, _ = QFileDialog.getSaveFileName(
                page,
                f"Download protected {label} file",
                suggested,
                f"{label} files (*{suffix})",
            )
            if not path:
                _status(page, "Saved to Library")
                return
            destination = Path(path)
            if destination.suffix.lower() != suffix:
                destination = destination.with_suffix(suffix)
            page._redesign_begin_operation(
                "export", f"Creating protected {label} file locally…"
            )
            try:
                page.service.save_protected_office(
                    result, destination, source_document=document
                )
            finally:
                page._redesign_end_operation("export")
            _status(page, "Saved + downloaded")
            return

        suggested = f"{title}_protected.txt"
        path, _ = QFileDialog.getSaveFileName(
            page, "Download protected text", suggested, "Text files (*.txt)"
        )
        if not path:
            _status(page, "Saved to Library")
            return
        destination = Path(path)
        if destination.suffix.lower() != ".txt":
            destination = destination.with_suffix(".txt")
        page.service.save_protected_text(result, destination)
        _status(page, "Saved + downloaded")
    finally:
        page._redesign_end_operation("verify")


def _copy_and_open_chatgpt(page: ProtectionPage) -> None:
    if page.current_result is None:
        return
    page._redesign_begin_operation("verify", "Final privacy check before opening ChatGPT…")
    try:
        page._copy_and_open_chatgpt()
        if page.current_result is not None:
            _status(page, "Protected text copied — ChatGPT opened")
    finally:
        page._redesign_end_operation("verify")


def _apply_quick_actions(page: ProtectionPage) -> None:
    if not hasattr(page, "_redesign_start_card"):
        return

    start_layout = page._redesign_start_card.layout()
    bar = QFrame(objectName="ProtectQuickActions")
    bar_layout = QHBoxLayout(bar)
    bar_layout.setContentsMargins(10, 9, 10, 9)
    bar_layout.setSpacing(10)

    hint = QLabel("Protected copy ready — choose what to do next")
    hint.setStyleSheet("color:#5e7385;font-size:11px;font-weight:600;")
    save_copy = QPushButton("Save + Copy")
    save_download = QPushButton("Save + Download")
    open_ai = QPushButton("Copy & Open ChatGPT")

    save_copy.setStyleSheet(
        "QPushButton{background:#078c89;color:white;border:none;border-radius:8px;"
        "padding:10px 18px;font-weight:800;}"
        "QPushButton:hover{background:#057a77;}"
    )
    save_download.setStyleSheet(
        "QPushButton{background:#c9942d;color:white;border:none;border-radius:8px;"
        "padding:10px 18px;font-weight:800;}"
        "QPushButton:hover{background:#b18125;}"
    )
    open_ai.setStyleSheet(
        "QPushButton{background:white;color:#17384e;border:1px solid #b9cad7;"
        "border-radius:8px;padding:10px 18px;font-weight:800;}"
        "QPushButton:hover{background:#f5f9fb;}"
    )
    for button in (save_copy, save_download, open_ai):
        button.setMinimumHeight(42)

    bar_layout.addWidget(hint, 1)
    bar_layout.addWidget(save_copy)
    bar_layout.addWidget(save_download)
    bar_layout.addWidget(open_ai)
    bar.setStyleSheet(
        "QFrame#ProtectQuickActions{background:#f8fbfc;border:1px solid #d9e4eb;"
        "border-radius:10px;}"
    )
    bar.hide()

    # Place the actions immediately below the Protect controls and before the
    # spinner/advanced section, rather than at the bottom of a long results view.
    busy_panel = getattr(page, "_redesign_busy_panel", None)
    insert_at = start_layout.count()
    if busy_panel is not None:
        for index in range(start_layout.count()):
            if start_layout.itemAt(index).widget() is busy_panel:
                insert_at = index
                break
    start_layout.insertWidget(insert_at, bar)

    old_actions = getattr(page, "_redesign_final_actions", None)
    if old_actions is not None:
        old_actions.hide()
        old_actions.setMaximumHeight(0)

    page._protect_quick_actions = bar
    page._protect_save_copy = save_copy
    page._protect_save_download = save_download
    page._protect_open_ai = open_ai

    save_copy.clicked.connect(lambda: _save_and_copy(page))
    save_download.clicked.connect(lambda: _save_and_download(page))
    open_ai.clicked.connect(lambda: _copy_and_open_chatgpt(page))

    def hide_actions(*_args) -> None:
        bar.hide()

    page.text_input.textChanged.connect(hide_actions)
    page.pdf_path.textChanged.connect(hide_actions)
    page.findings_table.itemChanged.connect(hide_actions)

    def after_protect() -> None:
        if page.current_result is None:
            bar.hide()
            return
        if old_actions is not None:
            old_actions.hide()
        bar.show()
        _status(page, "Protected copy ready")

    # The redesign's protect handler was connected first, so this runs after it.
    page._redesign_protect_button.clicked.connect(after_protect)


def install_protect_quick_actions() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_init = ProtectionPage.__init__

    def wrapped_init(self: ProtectionPage, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        _apply_quick_actions(self)

    ProtectionPage.__init__ = wrapped_init
