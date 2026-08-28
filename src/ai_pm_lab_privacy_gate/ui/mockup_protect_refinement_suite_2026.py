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


def apply_mockup_protect_refinement_suite_2026(main_window) -> None:
    """Apply presentation first, local manual-rule behavior last."""
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
    # Safety bridge must be last: manual rules are merged into the authoritative
    # ProtectSession analysis before the ordinary render, preventing the previous
    # double-preview regeneration on re-scan.
    apply_mockup_protect_manual_sensitive_runtime_fix_2026(main_window)
