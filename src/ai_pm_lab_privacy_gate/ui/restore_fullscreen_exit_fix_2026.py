from __future__ import annotations

"""Restore 2026 fullscreen lifecycle guard.

The legacy RestorePage fullscreen toggle predates the 2026 presentation layer and,
when leaving full-screen preview, explicitly makes the old steps/input cards visible
again. Those cards are intentionally replaced by the compact Restore workspace and
finder toolbar. This guard only restores the 2026 visibility contract after the
existing fullscreen handler runs; preview/restore behavior remains authoritative.
"""

from PySide6.QtCore import QTimer


def _enforce_restore_2026_visibility(page) -> None:
    # These are legacy presentation containers. Their real controls were already
    # reused in the compact Restore toolbar/document workspace, so the containers
    # themselves must never return after Full screen -> Exit.
    for widget in (
        getattr(page, "steps_card", None),
        getattr(page, "input_card", None),
        getattr(page, "match_card", None),
    ):
        if widget is None:
            continue
        widget.hide()
        widget.setMinimumHeight(0)
        widget.setMaximumHeight(0)

    # The legacy fullscreen handler also restores the pre-redesign page margins.
    # Reapply the approved Restore 2026 shell when returning to normal view.
    full_button = getattr(page, "full_preview_button", None)
    if full_button is not None and not full_button.isChecked():
        outer = getattr(page, "_outer_layout", None)
        if outer is not None:
            outer.setContentsMargins(20, 14, 20, 12)
            outer.setSpacing(8)


def apply_restore_fullscreen_exit_fix_2026(main_window) -> None:
    page = getattr(main_window, "restore_page", None)
    if page is None or bool(getattr(page, "_restore_fullscreen_exit_fix_2026", False)):
        return
    page._restore_fullscreen_exit_fix_2026 = True

    button = getattr(page, "full_preview_button", None)
    if button is None:
        return

    # The core RestorePage connection was installed during construction. This
    # connection is added later, and the zero-delay callback guarantees the 2026
    # visibility state is restored after every fullscreen transition completes.
    button.toggled.connect(
        lambda _focused=False: QTimer.singleShot(
            0, lambda: _enforce_restore_2026_visibility(page)
        )
    )

    _enforce_restore_2026_visibility(page)
