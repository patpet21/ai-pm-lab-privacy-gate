from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ai_pm_lab_privacy_gate.ui.mockup_redesign_shell_2026 import _clear_layout, _page_index


_LAZY_PAGE_INDEXES = {
    "library_page": 1,
    "restore_page": 2,
    "local_automation_page": 3,
    "cloud_automation_page": 4,
    "settings_page": 5,
    "contact_page": 6,
}


def _open_governance(controller) -> None:
    if getattr(controller.main_window, "governance_page", None) is not None:
        controller._open_page("governance_page")
    else:
        controller._open_page("settings_page")


def _ensure_apps_page(main_window):
    """Materialize Apps on demand without forcing Cloud/MCP into startup."""
    existing = getattr(main_window, "apps_hub_page", None)
    pages = getattr(main_window, "pages", None)
    if existing is not None and pages is not None and pages.indexOf(existing) >= 0:
        return existing
    if pages is None:
        return None

    controller = getattr(main_window, "_unified_loading", None)
    loading_key = "page.load:apps"
    show_loading = controller is not None and bool(
        getattr(main_window, "_privacygate_startup_ready", False)
    )
    if show_loading:
        controller.begin(
            loading_key,
            "Opening Apps",
            "Preparing your connected apps and local source controls…",
        )
        QApplication.processEvents()

    try:
        cloud = getattr(main_window, "cloud_automation_page", None)
        if cloud is None:
            ensure_page = getattr(main_window, "_ensure_page", None)
            if callable(ensure_page):
                cloud = ensure_page(4)

        service = getattr(cloud, "_connected_apps_service", None) if cloud is not None else None
        if service is None:
            return None

        from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage

        apps_page = AppsHubPage(main_window, service)
        apps_index = pages.addWidget(apps_page)
        main_window.apps_hub_page = apps_page
        main_window.apps_page_index = apps_index

        # Re-apply late routing now that the real Apps page exists. These helpers
        # are idempotent and keep Organization links pointed at this same hub.
        from ai_pm_lab_privacy_gate.ui.organization_apps_safe_routing import (
            apply_organization_apps_safe_routing,
        )

        apply_organization_apps_safe_routing(main_window)
        try:
            apps_page.refresh()
        except Exception:
            pass
        return apps_page
    finally:
        if show_loading:
            QTimer.singleShot(0, lambda: controller.end(loading_key))


def _open_activity(controller) -> None:
    """Open Activity directly even when Settings/FeatureSuite are still lazy."""
    main_window = controller.main_window
    suite = getattr(main_window, "privacygate_feature_suite", None)
    if suite is None:
        ensure_page = getattr(main_window, "_ensure_page", None)
        if callable(ensure_page):
            try:
                ensure_page(5)
            except Exception:
                controller._open_page("settings_page")
                return
        suite = getattr(main_window, "privacygate_feature_suite", None)

    if suite is None:
        controller._open_page("settings_page")
        return

    try:
        from ai_pm_lab_privacy_gate.domain.plans import Capability
        from ai_pm_lab_privacy_gate.ui.feature_suite_2026 import ActivityDialog

        suite.open_feature(
            Capability.ACTIVITY_CENTER,
            "Activity Center",
            ActivityDialog,
        )
    except Exception:
        controller._open_page("settings_page")


def apply_mockup_navigation_2026(main_window) -> None:
    """Use one clear universal navigation vocabulary across Personal and Organization."""
    if bool(getattr(main_window, "_privacygate_mockup_navigation_2026", False)):
        return
    main_window._privacygate_mockup_navigation_2026 = True

    controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    if controller is None:
        return

    def open_page(self, attribute: str) -> None:
        """Open an existing page or materialize a startup-lazy page on demand."""
        index = _page_index(self.main_window, attribute)
        materialized = False

        if index < 0 and attribute == "apps_hub_page":
            pages = getattr(self.main_window, "pages", None)
            page = _ensure_apps_page(self.main_window)
            if page is not None and pages is not None:
                index = int(pages.indexOf(page))
                materialized = index >= 0

        if index < 0:
            lazy_index = _LAZY_PAGE_INDEXES.get(attribute)
            ensure_page = getattr(self.main_window, "_ensure_page", None)
            pages = getattr(self.main_window, "pages", None)
            if lazy_index is not None and callable(ensure_page) and pages is not None:
                page = ensure_page(lazy_index)
                index = int(pages.indexOf(page))
                materialized = index >= 0

        if index < 0:
            return

        self.main_window._show_page(index)
        if attribute == "apps_hub_page":
            apps_page = getattr(self.main_window, "apps_hub_page", None)
            refresh = getattr(apps_page, "refresh", None) if apps_page is not None else None
            if callable(refresh):
                QTimer.singleShot(0, refresh)

        if materialized:
            # Rebuild once after first materialization so checked-state routing maps
            # the new concrete widget index without preloading any other lazy page.
            QTimer.singleShot(0, self.rebuild)
        else:
            QTimer.singleShot(0, self._sync_checked_state)

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
        # Apps is part of both Personal and Organization navigation. The page
        # itself remains lazy and is materialized only on first click.
        self._nav_button(
            "Apps", "cloud", lambda: self._open_page("apps_hub_page"),
            page_attribute="apps_hub_page",
        )
        self._nav_button(
            "MCP & AI Direct", "workflow", lambda: self._open_page("cloud_automation_page"),
            page_attribute="cloud_automation_page",
        )
        self._nav_button(
            "Workflows", "workflow", lambda: self._open_page("local_automation_page"),
            page_attribute="local_automation_page",
        )
        self._nav_button("Activity", "history", lambda: _open_activity(self))
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

    controller._open_page = MethodType(open_page, controller)
    controller.rebuild = MethodType(rebuild, controller)
    controller._sync_checked_state = MethodType(sync_checked, controller)
    controller.rebuild()
    QTimer.singleShot(0, controller._sync_checked_state)
