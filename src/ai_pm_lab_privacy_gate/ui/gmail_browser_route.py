from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish, protect_source_picker
from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage
from ai_pm_lab_privacy_gate.ui.drive_browser import open_drive_browser
from ai_pm_lab_privacy_gate.ui.gmail_inbox import open_gmail_inbox


_INSTALLED = False


def install_gmail_browser_route() -> None:
    """Route Google providers to familiar import pickers and clarify Apps actions."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_open = connected_apps_browse_polish._open_source_browser

    def routed_open(main_window, provider: str, title: str) -> None:
        if provider == "gmail":
            open_gmail_inbox(main_window)
            return
        if provider == "google_drive":
            open_drive_browser(main_window)
            return
        original_open(main_window, provider, title)

    connected_apps_browse_polish._open_source_browser = routed_open
    # protect_source_picker imported the function directly, so update its alias too.
    protect_source_picker._open_source_browser = routed_open

    original_browse = AppsHubPage._browse

    def apps_browse(self: AppsHubPage, provider: str, title: str, supported: bool) -> None:
        if supported and self._connected(provider):
            if provider == "gmail":
                open_gmail_inbox(self.main_window)
                return
            if provider == "google_drive":
                open_drive_browser(self.main_window)
                return
        original_browse(self, provider, title, supported)

    AppsHubPage._browse = apps_browse

    original_refresh = AppsHubPage.refresh

    def apps_refresh(self: AppsHubPage) -> None:
        original_refresh(self)
        for button in self.findChildren(QPushButton, "AppBrowse"):
            provider = str(button.property("provider") or "")
            if provider == "google_drive":
                button.setText("Full Drive")
                button.setToolTip("Existing drive.readonly browser — full folder navigation")
            else:
                button.setText("Import")
                button.setToolTip("Choose content from this connected app and bring it locally into Protect.")

    AppsHubPage.refresh = apps_refresh
