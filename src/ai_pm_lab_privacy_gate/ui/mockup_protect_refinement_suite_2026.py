from __future__ import annotations

"""One ordered activation point for the post-mockup Protect refinements."""

from PySide6.QtWidgets import QHBoxLayout

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
