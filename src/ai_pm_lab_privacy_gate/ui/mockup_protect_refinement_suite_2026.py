from __future__ import annotations

"""One ordered activation point for the post-mockup Protect refinements."""

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
    # Final source-entry presentation: reorder/style the existing source buttons
    # and add the empty-state upload/paste/drop surface without replacing any
    # Protect callbacks or engine behavior.
    apply_mockup_protect_entry_surface_2026(main_window)
