from __future__ import annotations

"""One ordered activation point for the post-mockup Protect refinements."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout

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


def _keep_source_actions_in_unified_row(main_window) -> None:
    """Keep the styled source buttons in the visible compact command row.

    The compact workflow already moved the real Upload/Connected/Paste widgets
    out of their legacy quick bar.  The final entry-surface styling must not move
    those same widgets back into that hidden compatibility bar.  Reattach the
    existing button instances here; their original signals and behavior remain
    unchanged.
    """
    page = getattr(main_window, "protection_page", None)
    if page is None:
        return

    row_frame = getattr(page, "_protect_2026_unified_row", None)
    workflow = getattr(page, "_protect_2026_workflow_button", None)
    upload = getattr(page, "_protect_source_upload", None)
    paste = getattr(page, "_protect_source_paste", None)
    connected = getattr(page, "_protect_source_connected", None)
    if row_frame is None or workflow is None or any(
        button is None for button in (upload, paste, connected)
    ):
        return

    row = row_frame.layout()
    if not isinstance(row, QHBoxLayout):
        return

    # Remove the buttons from whichever compatibility layout currently owns
    # them, then put the exact same widgets immediately after Workflow.
    for button in (upload, paste, connected):
        parent = button.parentWidget()
        parent_layout = parent.layout() if parent is not None else None
        if parent_layout is not None:
            parent_layout.removeWidget(button)

    workflow_index = row.indexOf(workflow)
    insert_at = workflow_index + 1 if workflow_index >= 0 else 0
    for offset, button in enumerate((upload, paste, connected)):
        row.insertWidget(insert_at + offset, button)
        button.show()


def _install_back_to_options(page) -> None:
    """Add one clear return affordance while the manual Paste editor is open.

    This is presentation-only: returning delegates to the existing Clear action,
    which already resets the Protect source/session and restores the EMPTY entry
    surface. No source, scan, detector or protection behavior is duplicated here.
    """
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

    # Heading remains index 0. Put this compact return row immediately beneath
    # it and above whichever source surface (EMPTY/PASTE/DOCUMENT) is active.
    layout.insertWidget(1, row_host, 0)

    def refresh() -> None:
        # setVisible() in the entry-surface state machine changes the widget's
        # hidden flag, so this remains truthful even before the whole window is
        # exposed by Qt.
        paste_visible = not text_input.isHidden()
        empty_visible = not empty_state.isHidden()
        row_host.setVisible(paste_visible and not empty_visible)

    def schedule(*_args) -> None:
        QTimer.singleShot(0, refresh)

    def back_to_options() -> None:
        # The approved behavior is a true return to source choice, not another
        # parallel reset path. Reuse the existing Clear controller so any pasted
        # draft/result/session state is cleared consistently.
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
    # Keep those styled actions in the visible compact row, in the approved order:
    # Workflow | Upload | Paste text | Connected source | workspace context ...
    _keep_source_actions_in_unified_row(main_window)
    # When manual Paste is open, offer an explicit return to the source choices.
    _install_back_to_options(getattr(main_window, "protection_page", None))
