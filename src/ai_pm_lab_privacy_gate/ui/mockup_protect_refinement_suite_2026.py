from __future__ import annotations

"""One ordered activation point for the post-mockup Protect refinements."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLayout,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

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


def _move_scan_settings(page, row: QHBoxLayout, context_bar) -> None:
    """Reuse the existing Advanced panel as the compact Scan settings control."""
    settings_strip = page.findChild(QFrame, "RedesignSettingsStrip")
    advanced_panel = page.findChild(QFrame, "RedesignAdvanced")
    if settings_strip is None or advanced_panel is None:
        return

    toggles = tuple(settings_strip.findChildren(QToolButton))
    toggle = next(
        (
            item
            for item in toggles
            if "advanced protection settings" in " ".join(item.text().split()).lower()
        ),
        toggles[0] if toggles else None,
    )
    if toggle is None:
        return

    # Move only the real toggle into the compact command row.  The real settings
    # panel stays a single instance and is mounted directly below that row.
    strip_layout = settings_strip.layout()
    if strip_layout is not None:
        strip_layout.removeWidget(toggle)
    toggle.setParent(page.preview_card)
    toggle.setCheckable(True)
    toggle.setMinimumHeight(39)
    toggle.setMinimumWidth(130)
    toggle.setMaximumWidth(155)
    toggle.setToolTip("Change scan profile, protection scope, protection mode, or confidence threshold.")
    toggle.setStyleSheet(
        "QToolButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
        "border-radius:9px;padding:7px 10px;font-size:9px;font-weight:850;text-align:left;}"
        "QToolButton:hover{background:#F8FAFC;border-color:#AFC7FA;color:#1D4ED8;}"
        "QToolButton:checked{background:#EFF6FF;border-color:#AFC7FA;color:#1D4ED8;}"
    )

    browse = getattr(context_bar, "browse", None) if context_bar is not None else None
    insert_at = row.indexOf(browse) if browse is not None else -1
    if insert_at < 0:
        scan = getattr(page, "_protect_source_scan", None)
        insert_at = row.indexOf(scan) if scan is not None else row.count()
    row.insertWidget(max(0, insert_at), toggle)

    # Mount the existing settings strip directly under the command row instead of
    # leaving an Advanced section detached at the bottom of Protect.
    old_parent = settings_strip.parentWidget()
    old_layout = old_parent.layout() if old_parent is not None else None
    if old_layout is not None:
        old_layout.removeWidget(settings_strip)
    settings_strip.setParent(page.preview_card)
    preview_layout = page.preview_card.layout()
    command = getattr(page, "_protect_2026_unified_row", None)
    command_index = preview_layout.indexOf(command) if preview_layout is not None else -1
    if preview_layout is not None:
        preview_layout.insertWidget(command_index + 1 if command_index >= 0 else 1, settings_strip)

    settings_strip.setStyleSheet(
        "QFrame#RedesignSettingsStrip{background:#FFFFFF;border:1px solid #D7E2EA;"
        "border-radius:11px;}"
    )
    if strip_layout is not None:
        strip_layout.setContentsMargins(10, 8, 10, 9)
        strip_layout.setSpacing(5)

    try:
        toggle.toggled.disconnect()
    except (RuntimeError, TypeError):
        pass

    def sync_scan_settings(opened: bool) -> None:
        advanced_panel.setVisible(opened)
        settings_strip.setVisible(opened)
        toggle.setText("Hide scan settings" if opened else "Scan settings")

    toggle.toggled.connect(sync_scan_settings)
    toggle.setChecked(False)
    sync_scan_settings(False)
    page._protect_2026_scan_settings_toggle = toggle


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
    if not isinstance(row, QHBoxLayout):
        return

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
        if row.indexOf(button) >= 0:
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

    _move_scan_settings(page, row, context_bar)

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
    # Final layout reconciliation. This stays inside the existing refinement suite
    # rather than adding another UI patch file.
    _finalize_command_and_view_rows(main_window)
