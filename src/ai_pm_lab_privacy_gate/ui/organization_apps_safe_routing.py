from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLineEdit, QPushButton


def resolve_apps_page_index(main_window) -> int:
    """Resolve the live top-level Apps page without changing any page stack."""

    pages = getattr(main_window, "pages", None)
    apps_page = getattr(main_window, "apps_hub_page", None)
    if pages is None or apps_page is None:
        return -1
    try:
        return int(pages.indexOf(apps_page))
    except (RuntimeError, TypeError, ValueError):
        return -1


def open_apps_page(main_window) -> bool:
    index = resolve_apps_page_index(main_window)
    if index < 0:
        return False
    # Keep the legacy compatibility attribute accurate, but never use it as the
    # source of truth in this helper.
    main_window.apps_page_index = index
    main_window._show_page(index)
    return True


def open_apps_provider(main_window, provider_label: str = "") -> bool:
    if not open_apps_page(main_window):
        return False
    if not provider_label:
        return True

    def focus_provider() -> None:
        page = getattr(main_window, "apps_hub_page", None)
        if page is None:
            return
        for search in page.findChildren(QLineEdit):
            try:
                if "search apps" in search.placeholderText().lower():
                    search.setText(provider_label)
                    search.setFocus()
                    search.selectAll()
                    return
            except RuntimeError:
                return
        filter_cards = getattr(page, "_filter_cards", None)
        if callable(filter_cards):
            filter_cards(provider_label)

    QTimer.singleShot(0, focus_provider)
    return True


def _rewire_personal_manage_apps(main_window) -> None:
    """Fix the one button that captured apps_page_index during UI construction."""

    team_page = getattr(main_window, "team_page", None)
    dashboard = (
        getattr(team_page, "_privacygate_premium_dashboard", None)
        if team_page is not None
        else None
    )
    if dashboard is None:
        return

    for button in dashboard.findChildren(QPushButton):
        try:
            text = button.text().strip().lower()
        except RuntimeError:
            continue
        if not text.startswith("manage connected apps"):
            continue
        try:
            button.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        button.clicked.connect(
            lambda _checked=False, window=main_window: open_apps_page(window)
        )


def apply_organization_apps_safe_routing(main_window) -> None:
    """Repair Apps navigation without adding/removing/reordering any UI page.

    Organization owns policy/governance surfaces. Links that explicitly say Apps
    must open the top-level AppsHubPage. This runtime intentionally does not touch
    TeamPage.sections, dashboard.stack, Organization tabs, Protect, or loading.
    """

    live_index = resolve_apps_page_index(main_window)
    if live_index >= 0:
        main_window.apps_page_index = live_index

    # Organization plugin tiles call this module-level helper at click time.
    from ai_pm_lab_privacy_gate.ui import organization_usability_polish

    organization_usability_polish._open_plugins = open_apps_provider
    _rewire_personal_manage_apps(main_window)
