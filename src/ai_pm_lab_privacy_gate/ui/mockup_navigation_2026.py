from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QTimer

from ai_pm_lab_privacy_gate.ui.mockup_redesign_shell_2026 import _clear_layout, _page_index


def _open_governance(controller) -> None:
    if getattr(controller.main_window, "governance_page", None) is not None:
        controller._open_page("governance_page")
    else:
        controller._open_page("settings_page")


def apply_mockup_navigation_2026(main_window) -> None:
    """Use one clear universal navigation vocabulary across Personal and Organization."""
    if bool(getattr(main_window, "_privacygate_mockup_navigation_2026", False)):
        return
    main_window._privacygate_mockup_navigation_2026 = True

    controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    if controller is None:
        return

    def rebuild(self) -> None:
        _clear_layout(self.nav_layout)
        self._buttons.clear()
        self._page_buttons.clear()
        self._org_tab_buttons = {}
        self._update_workspace_copy()
        self._update_account_copy()

        if self._is_organization():
            overview = self._nav_button(
                "Overview", "document", lambda: self._open_org_tab(0)
            )
            self._org_tab_buttons[0] = overview
            self._section_label("WORKSPACE")

        self._nav_button(
            "Protect", "protect", lambda: self._open_page("protection_page"),
            page_attribute="protection_page",
        )
        self._nav_button(
            "Restore", "restore", lambda: self._open_page("restore_page"),
            page_attribute="restore_page",
        )
        self._nav_button(
            "Library", "library", lambda: self._open_page("library_page"),
            page_attribute="library_page",
        )
        if getattr(self.main_window, "apps_hub_page", None) is not None:
            self._nav_button(
                "Apps", "cloud", lambda: self._open_page("apps_hub_page"),
                page_attribute="apps_hub_page",
            )
        self._nav_button(
            "MCP", "workflow", lambda: self._open_page("cloud_automation_page"),
            page_attribute="cloud_automation_page",
        )
        self._nav_button(
            "Automation", "workflow", lambda: self._open_page("local_automation_page"),
            page_attribute="local_automation_page",
        )
        self._nav_button("Activity", "history", self._open_activity)
        self._nav_button(
            "Governance",
            "protect",
            lambda: _open_governance(self),
            page_attribute="governance_page",
        )

        self._divider()

        if self._is_organization():
            self._section_label("ORGANIZATION")
            ai_apps = self._nav_button("AI & Apps", "workflow", lambda: self._open_org_tab(3))
            self._org_tab_buttons[3] = ai_apps
            policy = self._nav_button("Policy Center", "protect", lambda: self._open_org_tab(2))
            self._org_tab_buttons[2] = policy
            self._collapsible_group(
                "Team",
                "contact",
                [("Members & roles", "contact", lambda: self._open_org_tab(1))],
            )
            devices = self._nav_button("Devices", "document", lambda: self._open_org_tab(4))
            self._org_tab_buttons[4] = devices

        self._nav_button(
            "Settings", "settings", lambda: self._open_page("settings_page"),
            page_attribute="settings_page",
        )
        self.nav_layout.addStretch(1)
        self._sync_checked_state()

    def sync_checked(self) -> None:
        pages = getattr(self.main_window, "pages", None)
        current = int(pages.currentIndex()) if pages is not None else -1
        for button in self._buttons:
            if button.isCheckable():
                button.setChecked(False)

        team_index = _page_index(self.main_window, "team_page")
        if current == team_index:
            dashboard = getattr(self.team_page, "_privacygate_premium_dashboard", None)
            stack = getattr(dashboard, "stack", None) if dashboard is not None else None
            stack_index = int(stack.currentIndex()) if stack is not None else 0
            visual = {0: 0, 1: 1, 2: 2, 4: 3, 3: 4}.get(stack_index, 0)
            button = getattr(self, "_org_tab_buttons", {}).get(visual)
            if button is not None:
                button.setChecked(True)
            return

        button = self._page_buttons.get(current)
        if button is not None:
            button.setChecked(True)

    controller.rebuild = MethodType(rebuild, controller)
    controller._sync_checked_state = MethodType(sync_checked, controller)
    controller.rebuild()
    QTimer.singleShot(0, controller._sync_checked_state)
