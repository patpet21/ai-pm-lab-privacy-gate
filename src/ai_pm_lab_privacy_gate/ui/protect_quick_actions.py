from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage


_INSTALLED = False


def _named_save_to_library(page: ProtectionPage):
    """Save through the standard title prompt and encrypted local Library."""
    return page._save_to_library()


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
        saved = _named_save_to_library(page)
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
        saved = _named_save_to_library(page)
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


def _save_only(page: ProtectionPage) -> None:
    if page.current_result is None:
        return
    page._redesign_begin_operation("verify", "Final privacy check before saving locally…")
    try:
        if not page._confirm_residual_risk("saving to the local Library"):
            return
        saved = _named_save_to_library(page)
        if saved is not None:
            _status(page, f"Saved to Library as {saved.title}")
    finally:
        page._redesign_end_operation("verify")


def _apply_quick_actions(page: ProtectionPage) -> None:
    if not hasattr(page, "_redesign_start_card"):
        return

    results_layout = page._redesign_results_card.layout()
    bar = QFrame(objectName="ProtectQuickActions")
    bar_layout = QVBoxLayout(bar)
    bar_layout.setContentsMargins(10, 9, 10, 9)
    bar_layout.setSpacing(6)

    hint = QLabel("Protected copy ready — choose what to do next")
    hint.setStyleSheet("color:#5e7385;font-size:11px;font-weight:600;")
    save_library = QPushButton("Save to Library")
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
    save_library.setStyleSheet(
        "QPushButton{background:white;color:#087d72;border:1px solid #8fcfc9;"
        "border-radius:8px;padding:10px 16px;font-weight:800;}"
        "QPushButton:hover{background:#eefaf8;}"
    )
    for button in (save_library, save_copy, save_download, open_ai):
        button.setMinimumHeight(42)

    bar_layout.addWidget(hint)
    button_row = QHBoxLayout()
    button_row.setSpacing(8)
    button_row.addWidget(save_library, 1)
    button_row.addWidget(save_copy, 1)
    button_row.addWidget(save_download, 1)
    button_row.addWidget(open_ai, 1)
    bar_layout.addLayout(button_row)
    bar.setStyleSheet(
        "QFrame#ProtectQuickActions{background:#f8fbfc;border:1px solid #d9e4eb;"
        "border-radius:10px;}"
    )
    bar.hide()

    old_actions = getattr(page, "_redesign_final_actions", None)
    insert_at = results_layout.count()
    if old_actions is not None:
        for index in range(results_layout.count()):
            if results_layout.itemAt(index).widget() is old_actions:
                insert_at = index
                break
        old_actions.hide()
        old_actions.setMaximumHeight(0)
    # Actions belong after the document comparison so the user reviews the
    # protected output before saving, downloading or opening an AI tool.
    results_layout.insertWidget(insert_at, bar)

    page._protect_quick_actions = bar
    page._protect_save_only = save_library
    page._protect_save_copy = save_copy
    page._protect_save_download = save_download
    page._protect_open_ai = open_ai

    save_library.clicked.connect(lambda: _save_only(page))
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
    selection_timer = getattr(page, "_redesign_selection_timer", None)
    if selection_timer is not None:
        selection_timer.timeout.connect(after_protect)


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
