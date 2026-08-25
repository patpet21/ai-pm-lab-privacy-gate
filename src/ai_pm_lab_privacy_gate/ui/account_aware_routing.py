from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QMessageBox

from ai_pm_lab_privacy_gate.infrastructure.connectors.multi_account_registry import MULTI_ACCOUNT_PROVIDERS
from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish, protect_source_picker
from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage


_INSTALLED = False
_SPECIAL_APPS_ROUTES = {"gmail", "clickup", "asana", "trello", "notion", "monday", "jira"}


def choose_provider_account(parent, service, provider: str, title: str) -> bool:
    """Activate the account the user wants before opening provider data.

    Returns ``True`` when an account is ready. With one connected account the
    choice is automatic. With multiple accounts the user is always offered a
    picker so every data-entry point can explicitly choose the source account.
    """
    if provider not in MULTI_ACCOUNT_PROVIDERS:
        return True
    if service is None or not hasattr(service, "list_connected_accounts"):
        return True

    try:
        accounts = tuple(service.list_connected_accounts(provider))
    except Exception as exc:
        QMessageBox.warning(parent, f"{title} accounts", str(exc) or "Unable to read connected accounts.")
        return False

    if not accounts:
        QMessageBox.information(parent, f"{title} accounts", f"No {title} account is connected yet.")
        return False

    if len(accounts) == 1:
        try:
            service.activate_account(provider, accounts[0].account_id)
            return True
        except Exception as exc:
            QMessageBox.warning(parent, f"{title} account", str(exc))
            return False

    labels: list[str] = []
    by_label: dict[str, str] = {}
    active_index = 0
    for index, account in enumerate(accounts):
        marker = ""
        if account.is_default:
            marker = "  ·  Default"
        elif account.is_active:
            marker = "  ·  Selected"
        display = account.label
        if account.subtitle and account.subtitle.casefold() not in account.label.casefold():
            display += f" — {account.subtitle}"
        display += marker
        # Labels can theoretically collide. Keep the visible text unique without
        # exposing credentials or relying on email as the technical identifier.
        unique = display
        suffix = 2
        while unique in by_label:
            unique = f"{display} ({suffix})"
            suffix += 1
        labels.append(unique)
        by_label[unique] = account.account_id
        if account.is_active:
            active_index = index

    selected, ok = QInputDialog.getItem(
        parent,
        f"Choose {title} account",
        f"Which {title} account do you want to use for this data?",
        labels,
        active_index,
        False,
    )
    if not ok or not selected:
        return False

    account_id = by_label.get(str(selected), "")
    if not account_id:
        return False
    try:
        service.activate_account(provider, account_id)
        return True
    except Exception as exc:
        QMessageBox.warning(parent, f"{title} account", str(exc))
        return False


def _service_from_main_window(main_window):
    page = getattr(main_window, "cloud_automation_page", None)
    return getattr(page, "_connected_apps_service", None) if page is not None else None


def install_account_aware_routing() -> None:
    """Require an explicit account choice from every provider-data entry point."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    # At this point Gmail/ClickUp/project-platform route installers have already
    # composed their final _open_source_browser chain. Wrapping the final chain
    # covers Protect -> Connected Sources and the legacy Connected Apps surface
    # for every current multi-account provider, including Google Drive.
    previous_open = connected_apps_browse_polish._open_source_browser

    def account_aware_open(main_window, provider: str, title: str) -> None:
        service = _service_from_main_window(main_window)
        if not choose_provider_account(main_window, service, provider, title):
            return
        previous_open(main_window, provider, title)

    connected_apps_browse_polish._open_source_browser = account_aware_open
    protect_source_picker._open_source_browser = account_aware_open

    # The dedicated Apps routes for these providers open their custom browser
    # directly and therefore bypass AppsMultiAccount's generic account menu.
    # Add the same centralized selector there. Google Drive is intentionally not
    # included: AppsMultiAccount already handles it before the generic browser.
    previous_apps_browse = AppsHubPage._browse

    def apps_browse(self: AppsHubPage, provider: str, title: str, supported: bool) -> None:
        if provider in _SPECIAL_APPS_ROUTES and supported and self._connected(provider):
            if not choose_provider_account(self, self.service, provider, title):
                return
        previous_apps_browse(self, provider, title, supported)

    AppsHubPage._browse = apps_browse
