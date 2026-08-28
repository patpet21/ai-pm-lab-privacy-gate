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


def apply_mockup_protect_refinement_suite_2026(main_window) -> None:
    """Apply the approved presentation and local-only review behavior in order."""
    apply_mockup_protect_workspace_refinement_2026(main_window)
    apply_mockup_protect_explainability_2026(main_window)
    apply_mockup_protect_findings_refinement_2026(main_window)
    apply_mockup_protect_manual_sensitive_2026(main_window)
    # Keep contextual info buttons, remove the redundant policy strip and surface
    # only the real local workflow count beside the source actions.
    apply_mockup_protect_compact_workflow_2026(main_window)
    # Final vertical-space pass: move the four guidance steps + How it works into
    # the Document workspace header and collapse the dedicated full-width step card.
    apply_mockup_protect_compact_steps_2026(main_window)
    # Manual rules must first be synchronized with the authoritative ProtectSession
    # analysis so the review layer never creates a parallel findings state.
    apply_mockup_protect_manual_sensitive_runtime_fix_2026(main_window)
    # Product review layer: local rule management, truthful review summary,
    # why-detected context and final safe-copy actions.
    apply_mockup_protect_review_experience_2026(main_window)
