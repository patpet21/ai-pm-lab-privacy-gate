from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.ui.plan_account_ui import install_plan_account_panel


def _install_lazy_settings_hook(main_window) -> None:
    """Apply deferred page layers whenever a lazy page is first materialized."""
    if bool(getattr(main_window, "_privacygate_organization_lazy_settings_hook", False)):
        return
    original_ensure_page = getattr(main_window, "_ensure_page", None)
    if not callable(original_ensure_page):
        return

    def ensure_page(index: int):
        page = original_ensure_page(index)
        # Import at call time: ui.__init__ is fully initialized by the time a lazy
        # page can be opened, avoiding a package-import cycle during bootstrap.
        from ai_pm_lab_privacy_gate.ui import apply_lazy_page_layers

        apply_lazy_page_layers(main_window, index)
        return page

    main_window._ensure_page = ensure_page
    main_window._privacygate_organization_lazy_settings_hook = True


def apply_organization_polish(main_window) -> None:
    """Finish the Business/Enterprise UX after Team and Settings are available."""
    page = getattr(main_window, "team_page", None)
    if page is None or getattr(main_window, "_privacygate_organization_polish", False):
        return

    # Navigation can be polished immediately because TeamPage is created by the
    # business foundation. The Settings-dependent plan panel is deferred below.
    for button in getattr(main_window, "nav_buttons", []):
        if button.text() == "Team & Plans":
            button.setText("Organization")
            button.setToolTip("Organization privacy policy, members and managed devices")
            break

    for index, label in enumerate(getattr(main_window, "nav_labels", [])):
        if label == "Team & Plans":
            main_window.nav_labels[index] = "Organization"
            break

    # Startup lazy loading intentionally leaves SettingsPage unconstructed. Do not
    # force it (or Local Automation) into the startup path just for this panel.
    if getattr(main_window, "settings_page", None) is None:
        _install_lazy_settings_hook(main_window)
        return

    state = getattr(page, "state", TeamState())
    panel = install_plan_account_panel(main_window, state)

    state_changed = getattr(page, "state_changed", None)
    if state_changed is not None:
        state_changed.connect(panel.update_state)
        state_changed.connect(main_window.plans_page.update_state)

    main_window._privacygate_organization_polish = True