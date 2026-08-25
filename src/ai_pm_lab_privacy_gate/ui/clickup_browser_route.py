from __future__ import annotations

from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish, protect_source_picker
from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage
from ai_pm_lab_privacy_gate.ui.clickup_browser import open_clickup_browser


_INSTALLED = False


def install_clickup_browser_route() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_open = connected_apps_browse_polish._open_source_browser

    def routed_open(main_window, provider: str, title: str) -> None:
        if provider == "clickup":
            open_clickup_browser(main_window)
            return
        original_open(main_window, provider, title)

    connected_apps_browse_polish._open_source_browser = routed_open
    protect_source_picker._open_source_browser = routed_open

    original_browse = AppsHubPage._browse

    def apps_browse(self: AppsHubPage, provider: str, title: str, supported: bool) -> None:
        if provider == "clickup" and supported and self._connected(provider):
            open_clickup_browser(self.main_window)
            return
        original_browse(self, provider, title, supported)

    AppsHubPage._browse = apps_browse
