from __future__ import annotations

"""One ordered activation point for the post-mockup Protect refinements."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLayout, QPushButton, QVBoxLayout

from .mockup_protect_workspace_refinement_2026 import (
    apply_mockup_protect_workspace_refinement_2026,
)
from .mockup_protect_explainability_2026 import (
    apply_mockup_protect_explainability_2026,
)
from .mockup_protect_findings_refinement_2026 import (
    apply_mockup_protect_findings_refinement_2026,
)
from .mockup_protect_manual_sensitive_2026 import (
    apply_mockup_protect_manual_sensitive_2026,
)
from .mockup_protect_compact_workflow_2026 import (
    apply_mockup_protect_compact_workflow_2026,
)
from .mockup_protect_compact_steps_2026 import (
    apply_mockup_protect_compact_steps_2026,
)
from .mockup_protect_manual_sensitive_runtime_fix_2026 import (
    apply_mockup_protect_manual_sensitive_runtime_fix_2026,
)
from .mockup_protect_review_experience_2026 import (
    apply_mockup_protect_review_experience_2026,
)
from .mockup_protect_review_controls_2026 import (
    apply_mockup_protect_review_controls_2026,
)
from .protect_image_review_regression_fix import (
    apply_protect_image_review_regression_fix,
)
from .mockup_protect_entry_surface_2026 import (
    apply_mockup_protect_entry_surface_2026,
)


BLUE = "#2563EB"
BLUE_SOFT = "#EFF6FF"
BORDER = "#D0D5DD"
MUTED = "#667085"
TEXT = "#344054"
TEAL = "#0B858A"
TEAL_DARK = "#096E75"


def _find_layout(layout: QLayout | None, widget) -> QLayout | None:
    if layout is None:
        return None
    if layout.indexOf(widget) >= 0:
        return layout
    for index in range(layout.count()):
        child = layout.itemAt(index).layout()
        found = _find_layout(child, widget)
        if found is not None:
            return found
    return None


def _remove_from_parent_layout(widget) -> None:
    if widget is None:
        return
    parent = widget.parentWidget()
    layout = parent.layout() if parent is not None else None
    if layout is not None:
        layout.removeWidget(widget)


def _finalize_command_and_view_rows(main_window) -> None:
    """Apply the approved final Protect hierarchy using existing real widgets.

    No source, connector, scan, review or clear behavior is recreated here.  The
    existing Upload/Paste/Connected buttons remain alive as compatibility actions
    because the large Original-document entry surface delegates to them.  They are
    simply removed from the compact command row so the same actions are not shown
    twice.  The authoritative Clear button is moved beside Document/Paste text.
    """

    page = getattr(main_window, "protection_page", None)
    if page is None:
        return

    row_frame = getattr(page, "_protect_2026_unified_row", None)
    row = row_frame.layout() if row_frame is not None else None
    context_bar = getattr(page, "_managed_workspace_context_bar", None)

    # The large Original-document surface already exposes Upload and Paste text,
    # and connected content has its dedicated Source selector + Browse action.
    # Keep the canonical buttons alive but hidden instead of cloning/reconnecting
    # their callbacks or adding another compatibility file.
    for name in (
        "_protect_2026_workflow_button",
        "_protect_source_upload",
        "_protect_source_paste",
        "_protect_source_connected",
    ):
        button = getattr(page, name, None)
        if button is None:
            continue
        if isinstance(row, QHBoxLayout) and row.indexOf(button) >= 0:
            row.removeWidget(button)
        button.hide()
        button.setMaximumWidth(0)

    if context_bar is not None:
        # Provider identity must remain readable even while an asynchronous brand
        # logo is still loading.  Previous final styling made the text transparent,
        # which produced a blank Source field whenever the logo was delayed.
        source = context_bar.source_combo
        source.setMinimumWidth(150)
        source.setMaximumWidth(190)
        source.view().setMinimumWidth(220)
        source.setStyleSheet(
            "QComboBox{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
            "border-radius:9px;padding:7px 9px;font-size:9px;font-weight:750;}"
            "QComboBox:hover{border-color:#AFC7FA;background:#FCFDFF;}"
            f"QComboBox:focus{{border:1px solid {BLUE};}}"
            "QComboBox::drop-down{border:none;width:25px;}"
            "QComboBox QAbstractItemView{background:#FFFFFF;color:#344054;"
            "border:1px solid #D0D5DD;selection-background-color:#EEF4FF;"
            "selection-color:#101828;padding:4px;}"
        )

        context_bar.workspace_combo.setMinimumWidth(175)
        context_bar.workspace_combo.setMaximumWidth(225)
        context_bar.account_combo.setMinimumWidth(205)
        context_bar.account_combo.setMaximumWidth(265)
        context_bar.browse.setText("Browse connected content")
        context_bar.browse.setMinimumWidth(170)
        context_bar.browse.setMaximumWidth(205)

    # Add flags without changing the language codes used by the detector runtime.
    language = getattr(page, "document_language_combo", None)
    language_panel = getattr(page, "_protect_document_language_panel", None)
    if language is not None:
        for index in range(language.count()):
            code = str(language.itemData(index) or "")
            if code == "en":
                language.setItemText(index, "🇺🇸  English")
            elif code == "it":
                language.setItemText(index, "🇮🇹  Italiano")
        language.setMinimumWidth(125)
        language.setMaximumWidth(145)
    if language_panel is not None:
        language_panel.setMinimumWidth(125)
        language_panel.setMaximumWidth(145)

    scan = getattr(page, "_protect_source_scan", None)
    if scan is not None:
        scan.setText("Scan + Protect")
        scan.setMinimumWidth(155)
        scan.setMaximumWidth(180)

    # Reuse the existing EmbeddedSourceToolbar.  It already owns Document/Paste
    # and the real Protected text / Original + Protected view controls; placing
    # Clear here keeps every source/view action in one coherent row.
    toolbar = page.findChild(QFrame, "EmbeddedSourceToolbar")
    document = getattr(page, "_redesign_document_mode", None)
    paste = getattr(page, "_redesign_paste_mode", None)
    clear = getattr(page, "clear_button", None)
    if toolbar is not None and paste is not None and clear is not None:
        source_row = _find_layout(toolbar.layout(), paste)
        if isinstance(source_row, QHBoxLayout):
            _remove_from_parent_layout(clear)
            clear.setParent(toolbar)
            insert_at = source_row.indexOf(paste) + 1
            source_row.insertWidget(max(0, insert_at), clear)
            clear.setText("Clear")
            clear.setMinimumHeight(36)
            clear.setMinimumWidth(74)
            clear.setMaximumWidth(88)
            clear.setToolTip("Clear the current Protect source and return to the empty source choices.")
            clear.setStyleSheet(
                "QPushButton{background:#FFFFFF;color:#475467;border:1px solid #D0D5DD;"
                "border-radius:8px;padding:6px 10px;font-size:9px;font-weight:800;}"
                "QPushButton:hover{background:#F8FAFC;color:#344054;border-color:#98A2B3;}"
                "QPushButton:pressed{background:#F2F4F7;}"
            )
            clear.show()

        if document is not None:
            document.setMinimumWidth(122)
            document.setMaximumWidth(145)
        paste.setMinimumWidth(122)
        paste.setMaximumWidth(145)

    # Keep the two document panels as the visual center and do not let this final
    # compaction shrink the real text/document workspace established earlier.
    splitter = getattr(page, "document_preview_splitter", None)
    if splitter is not None:
        splitter.setMinimumHeight(520)
        splitter.setSizes([650, 650])
    empty_state = getattr(page, "_protect_source_empty_state", None)
    if empty_state is not None:
        empty_state.setMinimumHeight(420)
    text_input = getattr(page, "text_input", None)
    if text_input is not None:
        text_input.setMinimumHeight(420)


def _install_back_to_options(page) -> None:
    """Compatibility helper retained for older surfaces, but not used by v2026 final UI."""
    if page is None or getattr(page, "_protect_back_to_options_row", None) is not None:
        return

    panel = getattr(page, "original_document_panel", None)
    empty_state = getattr(page, "_protect_source_empty_state", None)
    text_input = getattr(page, "text_input", None)
    clear_button = getattr(page, "clear_button", None)
    if panel is None or empty_state is None or text_input is None or clear_button is None:
        return

    layout = panel.layout()
    if not isinstance(layout, QVBoxLayout):
        return

    row_host = QFrame(objectName="ProtectBackToOptionsRow")
    row_host.setStyleSheet(
        "QFrame#ProtectBackToOptionsRow{background:transparent;border:none;}"
    )
    row = QHBoxLayout(row_host)
    row.setContentsMargins(0, 0, 0, 2)
    row.setSpacing(0)
    row.addStretch(1)

    button = QPushButton("←  Back to options")
    button.setObjectName("ProtectBackToOptionsButton")
    button.setMinimumHeight(32)
    button.setToolTip("Return to Upload, Paste text, and drag & drop options.")
    button.setStyleSheet(
        "QPushButton#ProtectBackToOptionsButton{background:#FFFFFF;color:#344054;"
        "border:1px solid #D0D5DD;border-radius:8px;padding:5px 10px;"
        "font-size:8px;font-weight:850;}"
        "QPushButton#ProtectBackToOptionsButton:hover{background:#F8FAFC;"
        "color:#1D4ED8;border-color:#AFC7FA;}"
    )
    row.addWidget(button)
    layout.insertWidget(1, row_host, 0)

    def refresh() -> None:
        paste_visible = not text_input.isHidden()
        empty_visible = not empty_state.isHidden()
        row_host.setVisible(paste_visible and not empty_visible)

    def schedule(*_args) -> None:
        QTimer.singleShot(0, refresh)

    def back_to_options() -> None:
        clear_button.click()
        QTimer.singleShot(0, refresh)
        QTimer.singleShot(120, refresh)

    button.clicked.connect(back_to_options)
    text_input.textChanged.connect(schedule)
    page.pdf_path.textChanged.connect(schedule)
    clear_button.clicked.connect(schedule)

    for toggle_name in ("_redesign_paste_mode", "_redesign_document_mode"):
        toggle = getattr(page, toggle_name, None)
        if toggle is not None:
            toggle.toggled.connect(schedule)

    for action_name in (
        "_protect_source_upload",
        "_protect_source_paste",
        "_protect_source_connected",
        "_protect_empty_upload",
        "_protect_empty_paste",
    ):
        action = getattr(page, action_name, None)
        if action is not None:
            action.clicked.connect(schedule)

    row_host.hide()
    QTimer.singleShot(0, refresh)
    page._protect_back_to_options_row = row_host
    page._protect_back_to_options_button = button


def apply_mockup_protect_refinement_suite_2026(main_window) -> None:
    """Apply the approved presentation and local-only review behavior in order."""
    apply_mockup_protect_workspace_refinement_2026(main_window)
    apply_mockup_protect_explainability_2026(main_window)
    apply_mockup_protect_findings_refinement_2026(main_window)
    apply_mockup_protect_manual_sensitive_2026(main_window)
    apply_mockup_protect_compact_workflow_2026(main_window)
    apply_mockup_protect_compact_steps_2026(main_window)
    # Synchronize manual rules with the authoritative ProtectSession before any
    # higher-level review controls are installed.
    apply_mockup_protect_manual_sensitive_runtime_fix_2026(main_window)
    # Complete product review experience: local rule management, truthful metrics,
    # why-detected context and final safe-copy actions.
    apply_mockup_protect_review_experience_2026(main_window)
    # Guaranteed placement for Edit/Remove when the legacy action row is nested.
    apply_mockup_protect_review_controls_2026(main_window)
    # Image/OCR support extends the engine only. Never let its compatibility
    # preview hooks hide the established tags/review/manual-sensitive surface.
    apply_protect_image_review_regression_fix(main_window)
    # Final source-entry presentation: style the existing source buttons and add
    # the empty-state upload/paste/drop surface without replacing any Protect
    # callbacks or engine behavior.
    apply_mockup_protect_entry_surface_2026(main_window)
    # Final layout reconciliation.  This is deliberately inside the existing
    # refinement suite rather than another UI patch file: duplicate upper source
    # actions are hidden, Source remains logo+text, and the real Clear action is
    # moved beside Document/Paste while all callbacks stay authoritative.
    _finalize_command_and_view_rows(main_window)
