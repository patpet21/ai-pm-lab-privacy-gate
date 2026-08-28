from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLineEdit, QPushButton, QWidget


def resolve_apps_page_index(main_window) -> int:
    """Resolve the live Apps page instead of trusting a cached numeric index."""

    pages = getattr(main_window, "pages", None)
    apps_page = getattr(main_window, "apps_hub_page", None)
    if pages is None or apps_page is None:
        return -1
    try:
        return int(pages.indexOf(apps_page))
    except (RuntimeError, TypeError, ValueError):
        return -1


def open_apps_page(main_window) -> bool:
    """Open the real Apps hub even when later runtime pages changed navigation state."""

    index = resolve_apps_page_index(main_window)
    if index < 0:
        return False
    # Keep the legacy attribute accurate for compatibility, but never use it as
    # the source of truth for routing.
    main_window.apps_page_index = index
    main_window._show_page(index)
    return True


def _focus_provider(main_window, provider_label: str) -> None:
    if not provider_label:
        return
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


def open_apps_provider(main_window, provider_label: str = "") -> bool:
    opened = open_apps_page(main_window)
    if opened and provider_label:
        QTimer.singleShot(0, lambda: _focus_provider(main_window, provider_label))
    return opened


def ensure_team_apps_slot(dashboard) -> bool:
    """Guarantee the historic Team stack has the Apps & AI slot at index 4."""

    stack = getattr(dashboard, "stack", None)
    if stack is None:
        return False
    changed = False
    while stack.count() <= 4:
        stack.addWidget(QWidget())
        changed = True
    return changed


def _rewire_button(button: QPushButton, callback) -> None:
    try:
        button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    button.clicked.connect(callback)


def _rewire_team_apps_buttons(main_window, dashboard, apps_view) -> None:
    # Personal-workspace quick action created by premium_organization_rebuild.py.
    for button in dashboard.findChildren(QPushButton):
        text = button.text().strip().lower()
        if text.startswith("manage connected apps"):
            _rewire_button(
                button,
                lambda _checked=False, window=main_window: open_apps_page(window),
            )

    # Managed Organization Apps page action created by workspace suite v2.
    if apps_view is not None:
        for button in apps_view.findChildren(QPushButton):
            if button.text().strip().lower() == "connect / manage apps":
                _rewire_button(
                    button,
                    lambda _checked=False, window=main_window: open_apps_page(window),
                )


def apply_organization_apps_routing_fix(main_window) -> None:
    """Keep Team/Organization Apps navigation stable across runtime page additions."""

    team_page = getattr(main_window, "team_page", None)
    dashboard = (
        getattr(team_page, "_privacygate_premium_dashboard", None)
        if team_page is not None
        else None
    )
    if dashboard is None:
        return

    # TeamPage historically owns four stack pages. Premium Organization exposes
    # a fifth visual tab (Apps & AI), so create its slot before applying the
    # existing v2 governance view. Without this, clicking Apps & AI can leave the
    # previous Policy page visible and look like Apps opened Privacy.
    ensure_team_apps_slot(dashboard)

    from ai_pm_lab_privacy_gate.ui.organization_workspace_suite_v2 import (
        apply_organization_workspace_suite_v2,
    )

    apps_view = apply_organization_workspace_suite_v2(main_window)
    if apps_view is None:
        apps_view = getattr(dashboard, "_organization_apps_suite_v2", None)
        if apps_view is None and dashboard.stack.count() > 4:
            apps_view = dashboard.stack.widget(4)

    # App tiles in the Organization overview/readiness surfaces resolve this
    # module-level function at click time, so replace the stale-index version.
    from ai_pm_lab_privacy_gate.ui import organization_usability_polish

    organization_usability_polish._open_plugins = open_apps_provider

    _rewire_team_apps_buttons(main_window, dashboard, apps_view)

    # Keep compatibility metadata synchronized for any untouched legacy caller.
    live_index = resolve_apps_page_index(main_window)
    if live_index >= 0:
        main_window.apps_page_index = live_index
