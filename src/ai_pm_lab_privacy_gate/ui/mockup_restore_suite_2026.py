from __future__ import annotations

"""Single ordered activation point for the 2026 Restore experience."""

from PySide6.QtCore import QTimer

from .mockup_restore_final_2026 import apply_mockup_restore_final_2026
from .mockup_restore_edit_2026 import apply_mockup_restore_edit_2026
from .restore_completion_suite_2026 import apply_restore_completion_suite_2026
from .restore_completion_safety_2026 import apply_restore_completion_safety_2026
from .restore_final_stability_2026 import apply_restore_final_stability_2026
from .restore_fullscreen_exit_fix_2026 import apply_restore_fullscreen_exit_fix_2026


def apply_mockup_restore_suite_2026(main_window) -> None:
    # Presentation first: all existing RestorePage controllers remain authoritative.
    apply_mockup_restore_final_2026(main_window)
    # Functional edit layer second: edits are local/in-memory and reuse the real
    # restored text plus existing copy/download paths.
    apply_mockup_restore_edit_2026(main_window)
    # Product completion adds local matching suggestions, restore validation,
    # encrypted local resume metadata and a clearer text-edit working copy. It
    # does not replace DocumentRestoreService or persist document content.
    apply_restore_completion_suite_2026(main_window)
    apply_restore_completion_safety_2026(main_window)
    # Final stability handles two real Windows/PDF edge cases: unique restore-run
    # output paths avoid QPdfDocument file locks, while older image-based safe PDFs
    # can be restored from the explicitly selected local Library mapping as a
    # transparent reflow PDF fallback. It also replaces low-contrast native file
    # icons with local high-contrast file-type badges; provider logos stay official.
    apply_restore_final_stability_2026(main_window)
    # The Finder is mounted later in MainWindow.__init__. Bind it after the current
    # Qt construction turn so Review matches reuses that proven controller without
    # changing startup order or reparenting any command-bar control.
    QTimer.singleShot(
        0,
        lambda: setattr(
            getattr(main_window, "_restore_completion_controller", None),
            "finder_controller",
            getattr(main_window, "_restore_document_finder_controller", None),
        )
        if getattr(main_window, "_restore_completion_controller", None) is not None
        else None,
    )
    # The legacy fullscreen controller tries to reveal its old steps/input cards
    # when exiting. Keep the approved 2026 compact Restore surface authoritative.
    apply_restore_fullscreen_exit_fix_2026(main_window)
