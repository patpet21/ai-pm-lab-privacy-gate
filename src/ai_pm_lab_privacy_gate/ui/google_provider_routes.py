from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_file_access import (
    list_selected_file_accounts,
)
from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish, protect_source_picker
from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage, _primary_style
from ai_pm_lab_privacy_gate.ui.gmail_addon_import import open_gmail_addon_import
from ai_pm_lab_privacy_gate.ui.gmail_inbox import open_gmail_inbox
from ai_pm_lab_privacy_gate.ui.google_drive_access_center import (
    open_google_drive_access_center,
)


_INSTALLED = False


class _ProtectSourceServiceProxy:
    """Expose Gmail Add-on availability to Protect without faking Apps/OAuth state."""

    def __init__(self, service) -> None:
        self._service = service
        self.data_dir = getattr(service, "data_dir", None) if service is not None else None

    def is_connected(self, provider: str) -> bool:
        if provider == "gmail":
            # Protect's Gmail entry is the Workspace Add-on path. It does not
            # depend on the legacy mailbox-wide gmail.readonly connector.
            return True
        if self._service is None:
            return False
        return bool(self._service.is_connected(provider))

    def __getattr__(self, name: str):
        if self._service is None:
            raise AttributeError(name)
        return getattr(self._service, name)


def _open_drive_access_center_from_main_window(main_window) -> None:
    """Open the one Drive entry point from Protect or other main-window callers."""
    apps_page = getattr(main_window, "apps_hub_page", None)
    if apps_page is None:
        return
    open_google_drive_access_center(apps_page)


def install_google_provider_routes() -> None:
    """Route Google providers while keeping Protect Gmail Add-on scoped to Protect."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_open = connected_apps_browse_polish._open_source_browser

    def routed_open(main_window, provider: str, title: str) -> None:
        if provider == "gmail":
            # Protect uses the current-message Gmail Add-on path. No mailbox-wide
            # gmail.readonly connection is required for this entry point.
            open_gmail_addon_import(main_window)
            return
        if provider == "google_drive":
            # Protect must use the same Google Drive product entry point as Apps:
            # Selected files only is recommended, Full Drive remains optional.
            _open_drive_access_center_from_main_window(main_window)
            return
        original_open(main_window, provider, title)

    connected_apps_browse_polish._open_source_browser = routed_open
    # Some managed Protect routing intentionally asks for the preserved/raw source
    # opener after workspace-policy approval. Keep that alias pointed at the same
    # Google router so it cannot fall back to the legacy Full Drive-only browser.
    connected_apps_browse_polish._privacygate_raw_open_source_browser = routed_open
    # protect_source_picker imported the function directly, so update its alias too.
    protect_source_picker._open_source_browser = routed_open

    # The source picker previously required service.is_connected("gmail") before it
    # called its source opener. That check belongs to the old OAuth connector. Wrap
    # only Protect's source-service lookup so Gmail Add-on can open without changing
    # the real Apps/Connected Apps connection state.
    original_source_service = protect_source_picker._source_service

    def protect_source_service(main_window):
        return _ProtectSourceServiceProxy(original_source_service(main_window))

    protect_source_picker._source_service = protect_source_service

    original_provider_status = protect_source_picker._provider_status

    def protect_provider_status(service, key: str, availability: str):
        if key == "gmail":
            return (
                "ADD-ON",
                "#E8F6F6",
                "#0B7180",
                "Select one Gmail message with the PrivacyGate Add-on; no mailbox-wide connection required.",
            )
        return original_provider_status(service, key, availability)

    protect_source_picker._provider_status = protect_provider_status

    original_browse = AppsHubPage._browse

    def apps_browse(
        self: AppsHubPage,
        provider: str,
        title: str,
        supported: bool,
    ) -> None:
        if supported and self._connected(provider):
            if provider == "gmail":
                # Keep the existing Apps Gmail browser untouched for now. The new
                # Add-on path is intentionally scoped to Protect in this release fix.
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
