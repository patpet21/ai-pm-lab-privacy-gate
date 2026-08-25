from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.automatic_temp_cleanup import (
    cleanup_after_completed_save,
    prepare_managed_save,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage


_INSTALLED = False


def _named_save_to_library(page: ProtectionPage):
    """Save through the standard PrivacyGate Library save flow."""
    return page._save_to_library()


def _status(page: ProtectionPage, message: str) -> None:
    label = getattr(page, "_redesign_review_metric", None)
    if label is not None:
        label.setText(message)


def _save_and_copy(page: ProtectionPage) -> None:
    if page.current_result is None:
        return
    prepare_managed_save(page)
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
        cleanup_after_completed_save(page)
        page._redesign_end_operation("verify")


def _save_and_download(page: ProtectionPage) -> None:
    if page.current_result is None or page.current_document is None:
        return
    prepare_managed_save(page)
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
        cleanup_after_completed_save(page)
        page._redesign_end_operation("verify")


def _ai_handoff(page: ProtectionPage, destination_key: str) -> None:
    if page.current_result is None:
        return
    handler = getattr(page, "_privacygate_ai_handoff", None)
    if not callable(handler):
        return
    page._redesign_begin_operation("verify", "Running AI Privacy Preflight…")
    try:
        handler(destination_key)
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


def _ai_menu(page: ProtectionPage) -> QMenu:
    menu = QMenu(page)
    menu.setMinimumWidth(235)
    menu.setStyleSheet(
        "QMenu{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E1;"
        "border-radius:9px;padding:7px;}"
        "QMenu::item{padding:9px 18px 9px 10px;border-radius:6px;font-weight:700;}"
        "QMenu::item:selected{background:#EAF6F7;color:#0B7180;}"
        "QMenu::separator{height:1px;background:#E2E9EE;margin:6px 5px;}"
    )
    menu.addSection("Choose AI destination")

    chatgpt = menu.addAction(icon("external", color="#0B7180", size=17), "ChatGPT / GPT")
    chatgpt.setToolTip("Preflight → save to Library → copy protected text → open ChatGPT")
    chatgpt.triggered.connect(lambda _checked=False: _ai_handoff(page, "chatgpt"))

    claude = menu.addAction(icon("external", color="#0B7180", size=17), "Claude")
    claude.setToolTip("Preflight → save to Library → copy protected text → open Claude")
    claude.triggered.connect(lambda _checked=False: _ai_handoff(page, "claude"))

    other = menu.addAction(icon("copy", color="#0B7180", size=17), "Other AI tool")
    other.setToolTip("Preflight → save to Library → copy protected text for another AI")
    other.triggered.connect(lambda _checked=False: _ai_handoff(page, "other"))

    return menu


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

    open_ai = QToolButton()
    open_ai.setText("Save + Copy for AI")
    open_ai.setIcon(icon("copy", color="#17384E", size=18))
    open_ai.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    open_ai.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    open_ai.setMenu(_ai_menu(page))
    open_ai.setMinimumWidth(245)
    open_ai.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    open_ai.setToolTip(
        "Choose ChatGPT / GPT, Claude or another AI tool. PrivacyGate runs Preflight, "
        "asks how to name the protected copy, saves it locally, then copies it for AI."
    )

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
        "QToolButton{background:white;color:#17384e;border:1px solid #8fc3c9;"
        "border-radius:8px;padding:9px 22px 9px 14px;font-weight:850;text-align:left;}"
        "QToolButton:hover{background:#eef8f9;border-color:#63aeb6;}"
        "QToolButton::menu-indicator{subcontrol-origin:padding;subcontrol-position:right center;"
        "right:8px;width:12px;}"
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
    button_row.addWidget(open_ai, 2)
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

    results_layout.insertWidget(insert_at, bar)

    page._protect_quick_actions = bar
    page._protect_save_only = save_library
    page._protect_save_copy = save_copy
    page._protect_save_download = save_download
    page._protect_open_ai = open_ai

    save_library.clicked.connect(lambda: _save_only(page))
    save_copy.clicked.connect(lambda: _save_and_copy(page))
    save_download.clicked.connect(lambda: _save_and_download(page))

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
