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


def apply_mockup_protect_refinement_suite_2026(main_window) -> None:
    """Apply presentation first, local manual-rule behavior last."""
    apply_mockup_protect_workspace_refinement_2026(main_window)
    apply_mockup_protect_explainability_2026(main_window)
    apply_mockup_protect_findings_refinement_2026(main_window)
    apply_mockup_protect_manual_sensitive_2026(main_window)
    # Final compacting pass: keep contextual info buttons, remove the redundant
    # four-chip policy strip and surface only a real local workflow count beside
    # the source actions.
    apply_mockup_protect_compact_workflow_2026(main_window)
