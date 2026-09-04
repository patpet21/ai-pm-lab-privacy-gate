from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_file_access import (
    list_selected_file_accounts,
)
from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish, protect_source_picker
from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage
from ai_pm_lab_privacy_gate.ui.drive_browser import open_drive_browser
from ai_pm_lab_privacy_gate.ui.gmail_inbox import open_gmail_inbox


_INSTALLED = False


def install_gmail_browser_route() -> None:
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
            open_drive_browser(main_window)
            return
        original_open(main_window, provider, title)

    connected_apps_browse_polish._open_source_browser = routed_open
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
                # This route is deliberately Full Drive only. The independent
                # drive.file Picker is AppDriveFile/open_drive_file_browser.
                open_drive_browser(self.main_window)
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

        for button in self.findChildren(QPushButton, "AppBrowse"):
            provider = str(button.property("provider") or "")
            if provider == "google_drive":
                button.setText("Browse Full Drive")
                button.setToolTip(
                    "Optional Full Drive mode (drive.readonly). "
                    "Browse folders and choose files inside PrivacyGate."
                )
                button.setEnabled(bool(full_count))
            else:
                button.setText("Import")
                button.setToolTip(
                    "Choose content from this connected app and bring it locally into Protect."
                )

        for button in self.findChildren(QPushButton, "AppConnect"):
            provider = str(button.property("provider") or "")
            if provider != "google_drive":
                continue
            button.setText(
                "Full Drive accounts" if full_count else "Connect Full Drive"
            )
            button.setToolTip(
                "Optional Full Drive mode (drive.readonly). "
                "Connect or manage accounts that can browse Drive inside PrivacyGate."
            )

        for button in self.findChildren(QPushButton, "AppDriveFile"):
            button.setText(
                "Selected files only"
                if not selected_count
                else f"Selected files only · {selected_count}"
            )
            button.setToolTip(
                "Recommended privacy mode (drive.file). "
                "Google grants PrivacyGate access only to files you explicitly select."
            )
            button.setEnabled(True)

        for status in self.findChildren(QLabel, "AppStatus"):
            if str(status.property("provider") or "") != "google_drive":
                continue
            if full_count and selected_count:
                status.setText(f"FULL {full_count} · SELECTED {selected_count}")
            elif full_count:
                suffix = "ACCOUNT" if full_count == 1 else "ACCOUNTS"
                status.setText(f"FULL DRIVE · {full_count} {suffix}")
            elif selected_count:
                suffix = "ACCOUNT" if selected_count == 1 else "ACCOUNTS"
                status.setText(f"SELECTED FILES · {selected_count} {suffix}")
            else:
                continue
            status.setStyleSheet(
                "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
                "border-radius:8px;padding:4px 7px;font-size:9px;font-weight:900;"
            )

    AppsHubPage.refresh = apps_refresh
