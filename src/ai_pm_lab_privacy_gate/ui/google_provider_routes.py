from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_file_access import (
    list_selected_file_accounts,
)
from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish, protect_source_picker
from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage, _primary_style
from ai_pm_lab_privacy_gate.ui.gmail_inbox import open_gmail_inbox
from ai_pm_lab_privacy_gate.ui.google_drive_access_center import (
    open_google_drive_access_center,
)


_INSTALLED = False


def _open_drive_access_center_from_main_window(main_window) -> None:
    """Open the one Drive entry point from Protect or other main-window callers."""
    apps_page = getattr(main_window, "apps_hub_page", None)
    if apps_page is None:
        return
    open_google_drive_access_center(apps_page)


def install_google_provider_routes() -> None:
    """Route Google providers to their import pickers and keep Drive modes distinct."""
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
            # Protect must use the same Google Drive product entry point as Apps:
            # Selected files only is recommended, Full Drive remains optional.
            _open_drive_access_center_from_main_window(main_window)
            return
        original_open(main_window, provider, title)

    connected_apps_browse_polish._open_source_browser = routed_open
    # Some managed Protect routing intentionally asks for the preserved/raw source
    # opener after workspace-policy approval.  Keep that alias pointed at the same
    # Google router so it cannot fall back to the legacy Full Drive-only browser.
    connected_apps_browse_polish._privacygate_raw_open_source_browser = routed_open
    # protect_source_picker imported the function directly, so update its alias too.
    protect_source_picker._open_source_browser = routed_open

    original_browse = AppsHubPage._browse

    def apps_browse(
        self: AppsHubPage,
        provider: str,
        title: str,
        supported: bool,
    ) -> None:
        if supported and self._connected(provider):
            if provider == "gmail":
                open_gmail_inbox(self.main_window)
                return
            if provider == "google_drive":
                open_google_drive_access_center(self)
                return
        original_browse(self, provider, title, supported)

    AppsHubPage._browse = apps_browse

    original_refresh = AppsHubPage.refresh

    def full_drive_count(self: AppsHubPage) -> int:
        service = getattr(self, "service", None)
        if service is None:
            return 0
        if hasattr(service, "account_count"):
            try:
                return int(service.account_count("google_drive"))
            except Exception:
                pass
        try:
            return 1 if self._connected("google_drive") else 0
        except Exception:
            return 0

    def selected_file_count(self: AppsHubPage) -> int:
        service = getattr(self, "service", None)
        if service is None:
            return 0
        try:
            return len(list_selected_file_accounts(service))
        except Exception:
            return 0

    def apps_refresh(self: AppsHubPage) -> None:
        original_refresh(self)
        full_count = full_drive_count(self)
        selected_count = selected_file_count(self)
        drive_connected = bool(full_count or selected_count)

        # Google Drive is now one product entry point. The access center explains
        # Selected files vs Full Drive and contains both account-management flows.
        for button in self.findChildren(QPushButton, "AppBrowse"):
            if str(button.property("provider") or "") == "google_drive":
                button.hide()
            else:
                button.setText("Import")
                button.setToolTip(
                    "Choose content from this connected app and bring it locally into Protect."
                )

        for button in self.findChildren(QPushButton, "AppConnect"):
            if str(button.property("provider") or "") == "google_drive":
                button.hide()

        for button in self.findChildren(QPushButton, "AppDriveFile"):
            button.show()
            button.setText("Open Google Drive")
            button.setStyleSheet(_primary_style())
            button.setToolTip(
                "Choose Selected files only or optional Full Drive access, and manage Google accounts."
            )
            if not bool(button.property("drive_access_center_wired")):
                try:
                    button.clicked.disconnect()
                except (RuntimeError, TypeError):
                    pass
                button.clicked.connect(
                    lambda _checked=False, page=self: open_google_drive_access_center(page)
                )
                button.setProperty("drive_access_center_wired", True)

        for status in self.findChildren(QLabel, "AppStatus"):
            if str(status.property("provider") or "") != "google_drive":
                continue
            status.setText("CONNECTED" if drive_connected else "AVAILABLE")
            status.setStyleSheet(
                (
                    "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
                    if drive_connected
                    else "background:#EAF2FA;color:#355F87;border:1px solid #C9DAEA;"
                )
                + "border-radius:8px;padding:4px 7px;font-size:9px;font-weight:900;"
            )

    AppsHubPage.refresh = apps_refresh
