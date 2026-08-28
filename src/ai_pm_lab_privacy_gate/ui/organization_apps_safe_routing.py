from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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


def _safe_policy_history_layout(team_page, dashboard):
    """Return a visible parent/layout for Policy history, never a detached layout."""

    if dashboard is None:
        return None, None, None
    stack = getattr(dashboard, "stack", None)
    if stack is None or stack.count() <= 2:
        return None, None, None
    policy_view = stack.widget(2)
    if policy_view is None:
        return None, None, None

    # Prefer the same action row that already owns the visible Edit policy button.
    for candidate in policy_view.findChildren(QPushButton):
        try:
            text = candidate.text().strip().lower()
        except RuntimeError:
            continue
        if "edit policy" not in text:
            continue
        parent = candidate.parentWidget()
        layout = parent.layout() if parent is not None else None
        if isinstance(layout, QBoxLayout) and layout.indexOf(candidate) >= 0:
            return parent, layout, candidate

    # Safe fallback: place a compact action row inside the visible policy page.
    root = policy_view.layout()
    if isinstance(root, QVBoxLayout):
        action_host = QWidget(policy_view)
        action_row = QHBoxLayout(action_host)
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch(1)
        root.insertWidget(0, action_host)
        return action_host, action_row, None
    return None, None, None


def _repair_policy_history_control(main_window) -> None:
    """Keep Policy history inside Organization instead of becoming a top-level window.

    Governance hardening historically creates the button without a parent and then
    tries to locate a pre-redesign Edit policy layout. After the premium Organization
    rebuild that lookup can fail; calling setVisible(True) on the orphan then turns it
    into an independent top-level Qt window. Remove any such orphan and expose one
    safely parented control in the visible Policy page.
    """

    team_page = getattr(main_window, "team_page", None)
    if team_page is None:
        return
    dashboard = getattr(team_page, "_privacygate_premium_dashboard", None)

    # Remove the legacy orphan (and any duplicate outside the visible policy page).
    app = QApplication.instance()
    if app is not None:
        for widget in tuple(app.allWidgets()):
            if not isinstance(widget, QPushButton):
                continue
            try:
                if widget.text().strip().lower() != "policy history":
                    continue
                is_top_level = widget.parentWidget() is None or widget.window() is widget
            except RuntimeError:
                continue
            if is_top_level:
                try:
                    widget.hide()
                    widget.clicked.disconnect()
                except (RuntimeError, TypeError):
                    pass
                widget.deleteLater()

    parent, layout, edit_button = _safe_policy_history_layout(team_page, dashboard)
    if parent is None or layout is None:
        return

    # Avoid duplicates if a previous safe pass already created the control.
    for existing in parent.findChildren(QPushButton):
        try:
            if existing.text().strip().lower() == "policy history":
                return
        except RuntimeError:
            continue

    from ai_pm_lab_privacy_gate.ui.governance_hardening_2026 import PolicyHistoryDialog

    button = QPushButton("Policy history", parent)
    button.setObjectName("SafePolicyHistoryButton")
    button.setToolTip(
        "Compare policy versions or republish an older version as a new immutable version."
    )
    if edit_button is not None:
        try:
            button.setStyleSheet(edit_button.styleSheet())
            button.setMinimumHeight(edit_button.minimumHeight())
            layout.insertWidget(layout.indexOf(edit_button) + 1, button)
        except (RuntimeError, TypeError):
            layout.addWidget(button)
    else:
        layout.addWidget(button)

    def open_history(_checked=False) -> None:
        if not team_page.state.organization_id or team_page.state.role not in {"owner", "admin"}:
            return
        team_page._run_team_action(
            lambda session: team_page.team_client.list_policy_versions(
                session, team_page.state.organization_id
            ),
            result_handler=lambda rows: PolicyHistoryDialog(
                team_page, list(rows or [])
            ).exec(),
            refresh_after=False,
        )

    button.clicked.connect(open_history)

    def update_visibility(_state=None) -> None:
        button.setVisible(
            bool(
                button.parentWidget() is not None
                and team_page.state.organization_id
                and team_page.state.role in {"owner", "admin"}
            )
        )

    team_page.state_changed.connect(update_visibility)
    update_visibility()


def apply_organization_apps_safe_routing(main_window) -> None:
    """Repair late Organization navigation/window ownership without mutating stacks.

    Organization owns policy/governance surfaces. Links that explicitly say Apps
    must open the top-level AppsHubPage. This runtime intentionally does not add,
    remove or reorder Team/Organization pages, and it also repairs the legacy
    parentless Policy history control so it can never appear as a second window.
    """

    live_index = resolve_apps_page_index(main_window)
    if live_index >= 0:
        main_window.apps_page_index = live_index

    # Organization plugin tiles call this module-level helper at click time.
    from ai_pm_lab_privacy_gate.ui import organization_usability_polish

    organization_usability_polish._open_plugins = open_apps_provider
    _rewire_personal_manage_apps(main_window)
    _repair_policy_history_control(main_window)
