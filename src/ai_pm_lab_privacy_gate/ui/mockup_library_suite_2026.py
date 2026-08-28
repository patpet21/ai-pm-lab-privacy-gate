from __future__ import annotations

from PySide6.QtCore import QTimer

from ai_pm_lab_privacy_gate.ui.mockup_library_final_2026 import (
    install_mockup_library_final_2026,
)


def install_mockup_library_suite_2026() -> None:
    """Install the final Library class wrappers after the proven legacy layers."""
    install_mockup_library_final_2026()


def apply_mockup_library_suite_2026(main_window) -> None:
    """Bind workspace changes to the single local Library repository experience."""
    if bool(getattr(main_window, "_privacygate_mockup_library_suite_2026", False)):
        return
    main_window._privacygate_mockup_library_suite_2026 = True

    page = getattr(main_window, "library_page", None)
    if page is None:
        return

    def refresh_library(*_args) -> None:
        QTimer.singleShot(0, page.refresh)

    team_page = getattr(main_window, "team_page", None)
    state_changed = getattr(team_page, "state_changed", None) if team_page is not None else None
    if state_changed is not None:
        state_changed.connect(refresh_library)

    policy_changed = getattr(team_page, "policy_changed", None) if team_page is not None else None
    if policy_changed is not None:
        policy_changed.connect(refresh_library)

    old_combo = getattr(main_window, "workspace_sidebar_combo", None)
    if old_combo is not None:
        old_combo.currentIndexChanged.connect(refresh_library)

    controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    workspace_menu = getattr(controller, "workspace_menu", None) if controller is not None else None
    if workspace_menu is not None:
        workspace_menu.aboutToHide.connect(refresh_library)

    page.refresh()
