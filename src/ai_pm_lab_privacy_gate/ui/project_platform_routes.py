from __future__ import annotations

from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish, protect_source_picker
from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage
from ai_pm_lab_privacy_gate.ui.project_platform_browser import open_project_platform_browser


_INSTALLED = False
_PROVIDERS = {"asana", "trello", "notion", "monday", "jira"}


def install_project_platform_routes() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_open = connected_apps_browse_polish._open_source_browser

    def routed_open(main_window, provider: str, title: str) -> None:
        if provider in _PROVIDERS:
            open_project_platform_browser(main_window, provider)
            return
        original_open(main_window, provider, title)

    connected_apps_browse_polish._open_source_browser = routed_open
    protect_source_picker._open_source_browser = routed_open

    original_browse = AppsHubPage._browse

    def apps_browse(self: AppsHubPage, provider: str, title: str, supported: bool) -> None:
        if provider in _PROVIDERS and supported and self._connected(provider):
            open_project_platform_browser(self.main_window, provider)
            return
        original_browse(self, provider, title, supported)

    AppsHubPage._browse = apps_browse
