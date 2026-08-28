from __future__ import annotations

"""Single ordered activation point for the 2026 Restore experience."""

from .mockup_restore_final_2026 import apply_mockup_restore_final_2026
from .mockup_restore_edit_2026 import apply_mockup_restore_edit_2026
from .restore_fullscreen_exit_fix_2026 import apply_restore_fullscreen_exit_fix_2026


def apply_mockup_restore_suite_2026(main_window) -> None:
    # Presentation first: all existing RestorePage controllers remain authoritative.
    apply_mockup_restore_final_2026(main_window)
    # Functional edit layer second: edits are local/in-memory and reuse the real
    # restored text plus existing copy/download paths.
    apply_mockup_restore_edit_2026(main_window)
    # The legacy fullscreen controller tries to reveal its old steps/input cards
    # when exiting. Keep the approved 2026 compact Restore surface authoritative.
    apply_restore_fullscreen_exit_fix_2026(main_window)
