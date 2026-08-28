from __future__ import annotations

"""Lifecycle hardening for the final Restore completion layer.

The legacy RestorePage connected some button signals to bound methods during
construction. Later method wrappers therefore cannot assume those signals will
resolve the new method. These small post-layer hooks keep session/validation state
correct without disconnecting or replacing any proven Restore callback.
"""

from types import MethodType



def apply_restore_completion_safety_2026(main_window) -> None:
    controller = getattr(main_window, "_restore_completion_controller", None)
    page = getattr(main_window, "restore_page", None)
    if controller is None or page is None:
        return
    if bool(getattr(page, "_restore_completion_safety_2026", False)):
        return
    page._restore_completion_safety_2026 = True

    # Clear was connected to the original bound page.clear during construction.
    # Add a side-effect-only listener instead of disconnecting that proven action.
    def after_clear(_checked=False) -> None:
        controller.store.clear()
        controller._validation_active = False
        controller._last_restored_count = 0
        controller._schedule_refresh()

    page.clear_button.clicked.connect(after_clear)

    # A user-authored paste/new text starts a new restore attempt. Uploads are
    # already handled by the completion layer's _file_loaded wrapper.
    def input_changed() -> None:
        if page.input_text.hasFocus():
            controller._validation_active = False
            controller._last_restored_count = 0
            controller._schedule_refresh()

    page.input_text.textChanged.connect(input_changed)

    # If a restore attempt finds zero matching occurrences, do not leave a prior
    # successful validation banner active just because output_text still contains
    # an older result.
    previous_restore_ready = page._restore_ready

    def restore_ready_guard(page_self, payload: object) -> None:
        try:
            restored_count = int(payload.get("restored_count", 0))
        except Exception:
            restored_count = 0
        previous_restore_ready(payload)
        if restored_count <= 0:
            controller._validation_active = False
            controller._last_restored_count = 0
            controller._schedule_refresh()

    page._restore_ready = MethodType(restore_ready_guard, page)
