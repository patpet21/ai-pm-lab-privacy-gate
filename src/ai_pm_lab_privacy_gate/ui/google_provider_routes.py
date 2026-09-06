from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton

from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_transport import (
    GmailAddonTransport,
    MODE_ACTION,
)
from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_file_access import (
    list_selected_file_accounts,
)
from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish, protect_source_picker
from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage, _primary_style
from ai_pm_lab_privacy_gate.ui.gmail_addon_mode_picker import (
    open_configured_gmail_import,
    open_gmail_mode_picker,
)
from ai_pm_lab_privacy_gate.ui.google_drive_access_center import (
    open_google_drive_access_center,
)


_INSTALLED = False


class _ProtectSourceServiceProxy:
    """Expose Gmail Add-on availability to Protect without using the old Apps OAuth route."""

    def __init__(self, service) -> None:
        self._service = service
        self.data_dir = getattr(service, "data_dir", None) if service is not None else None

    def is_connected(self, provider: str) -> bool:
        if provider == "gmail":
            return True
        if self._service is None:
            return False
        return bool(self._service.is_connected(provider))

    def __getattr__(self, name: str):
        if self._service is None:
            raise AttributeError(name)
        return getattr(self._service, name)


def _open_drive_access_center_from_main_window(main_window) -> None:
    apps_page = getattr(main_window, "apps_hub_page", None)
    if apps_page is None:
        return
    open_google_drive_access_center(apps_page)


def _gmail_addon_state(page: AppsHubPage) -> tuple[bool, str]:
    service = getattr(page, "service", None)
    data_dir = getattr(service, "data_dir", None) if service is not None else None
    if data_dir is None:
        return False, MODE_ACTION
    try:
        from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_accounts import GmailAccountRegistry
        accounts = GmailAccountRegistry(data_dir).accounts()
        count = sum(bool(a.get('endpoint') and a.get('paired')) for a in accounts)
        return bool(count), str(count)
    except Exception:
        return False, MODE_ACTION


def install_google_provider_routes() -> None:
    """Keep Gmail setup in Apps and let Protect use the configured Gmail mode."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_open = connected_apps_browse_polish._open_source_browser

    def routed_open(main_window, provider: str, title: str) -> None:
        if provider == "gmail":
            # Protect does not configure Gmail. It simply uses the mode selected in Apps.
            open_configured_gmail_import(main_window)
            return
        if provider == "google_drive":
            _open_drive_access_center_from_main_window(main_window)
            return
        original_open(main_window, provider, title)

    connected_apps_browse_polish._open_source_browser = routed_open
    connected_apps_browse_polish._privacygate_raw_open_source_browser = routed_open
    protect_source_picker._open_source_browser = routed_open

    original_source_service = protect_source_picker._source_service

    def protect_source_service(main_window):
        return _ProtectSourceServiceProxy(original_source_service(main_window))

    protect_source_picker._source_service = protect_source_service

    original_provider_status = protect_source_picker._provider_status

    def protect_provider_status(service, key: str, availability: str):
        if key == "gmail":
            return (
                "GMAIL",
                "#E8F6F6",
                "#0B7180",
                "Choose a connected account and send one message from the Gmail sidebar.",
            )
        return original_provider_status(service, key, availability)

    protect_source_picker._provider_status = protect_provider_status

    original_connect = AppsHubPage._connect

    def apps_connect(
        self: AppsHubPage,
        provider: str,
        title: str,
        supported: bool,
        integration_path: str,
    ) -> None:
        if provider == "gmail":
            open_gmail_mode_picker(self.main_window)
            self.refresh()
            return
        original_connect(self, provider, title, supported, integration_path)

    AppsHubPage._connect = apps_connect

    original_browse = AppsHubPage._browse

    def apps_browse(
        self: AppsHubPage,
        provider: str,
        title: str,
        supported: bool,
    ) -> None:
        if provider == "gmail":
            open_configured_gmail_import(self.main_window)
            return
        if supported and self._connected(provider) and provider == "google_drive":
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
        gmail_connected, gmail_mode = _gmail_addon_state(self)

        for button in self.findChildren(QPushButton, "AppBrowse"):
            provider = str(button.property("provider") or "")
            if provider == "google_drive":
                button.hide()
            elif provider == "gmail":
                button.show()
                button.setText("Import")
                button.setEnabled(True)
                button.setToolTip(
                    "Choose a Gmail account and receive the message you explicitly send."
                )
            else:
                button.setText("Import")
                button.setToolTip(
                    "Choose content from this connected app and bring it locally into Protect."
                )

        for button in self.findChildren(QPushButton, "AppConnect"):
            provider = str(button.property("provider") or "")
            if provider == "google_drive":
                button.hide()
            elif provider == "gmail":
                button.show()
                button.setEnabled(True)
                button.setText("Manage Gmail")
                button.setStyleSheet(_primary_style())
                button.setToolTip(
                    "Add and manage separately paired Gmail accounts."
                )

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
            provider = str(status.property("provider") or "")
            if provider == "google_drive":
                status.setText("CONNECTED" if drive_connected else "AVAILABLE")
                status.setStyleSheet(
                    (
                        "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
                        if drive_connected
                        else "background:#EAF2FA;color:#355F87;border:1px solid #C9DAEA;"
                    )
                    + "border-radius:8px;padding:4px 7px;font-size:9px;font-weight:900;"
                )
            elif provider == "gmail":
                mode_label = gmail_mode + (" ACCOUNT" if gmail_mode == "1" else " ACCOUNTS")
                status.setText(mode_label if gmail_connected else "SETUP")
                status.setStyleSheet(
                    (
                        "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
                        if gmail_connected
                        else "background:#EAF2FA;color:#355F87;border:1px solid #C9DAEA;"
                    )
                    + "border-radius:8px;padding:4px 7px;font-size:9px;font-weight:900;"
                )

    AppsHubPage.refresh = apps_refresh
