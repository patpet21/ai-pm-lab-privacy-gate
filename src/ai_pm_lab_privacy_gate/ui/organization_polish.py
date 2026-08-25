from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.ui.plan_account_ui import install_plan_account_panel


def apply_organization_polish(main_window) -> None:
    """Finish the Business/Enterprise UX after the Team foundation is installed."""
    page = getattr(main_window, "team_page", None)
    if page is None or getattr(main_window, "_privacygate_organization_polish", False):
        return
    main_window._privacygate_organization_polish = True

    for button in getattr(main_window, "nav_buttons", []):
        if button.text() == "Team & Plans":
            button.setText("Organization")
            button.setToolTip("Organization privacy policy, members and managed devices")
            break

    for index, label in enumerate(getattr(main_window, "nav_labels", [])):
        if label == "Team & Plans":
            main_window.nav_labels[index] = "Organization"
            break

    state = getattr(page, "state", TeamState())
    panel = install_plan_account_panel(main_window.settings_page, state)

    state_changed = getattr(page, "state_changed", None)
    if state_changed is not None:
        state_changed.connect(panel.update_state)
