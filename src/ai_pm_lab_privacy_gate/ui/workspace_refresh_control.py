from __future__ import annotations

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ai_pm_lab_privacy_gate.ui.iconography import icon

TEAL = "#0B7F89"
NAVY = "#062B4F"


def apply_workspace_refresh_control(main_window) -> None:
    """Add an explicit refresh control to the workspace context card.

    The refresh uses the existing TeamPage refresh flow, which reloads live
    workspace memberships from the control plane and rebuilds the local
    WorkspaceContext cache. No workspace semantics are changed.
    """

    if bool(getattr(main_window, "_privacygate_workspace_refresh_control", False)):
        return

    card = getattr(main_window, "workspace_sidebar_card", None)
    team_page = getattr(main_window, "team_page", None)
    if card is None or team_page is None or card.layout() is None:
        return

    outer = card.layout()
    if not isinstance(outer, QHBoxLayout) or outer.count() < 2:
        return

    icon_label = outer.itemAt(0).widget()
    if not isinstance(icon_label, QLabel):
        return

    try:
        outer.removeWidget(icon_label)
    except RuntimeError:
        return

    rail = QWidget(card)
    rail.setObjectName("WorkspaceContextRail")
    rail_layout = QVBoxLayout(rail)
    rail_layout.setContentsMargins(0, 0, 0, 0)
    rail_layout.setSpacing(5)
    rail_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

    icon_label.setParent(rail)
    rail_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignHCenter)

    refresh = QPushButton(rail)
    refresh.setObjectName("WorkspaceRefreshButton")
    refresh.setFixedSize(30, 26)
    refresh.setIcon(icon("restore", color=TEAL, size=16))
    refresh.setIconSize(QSize(16, 16))
    refresh.setCursor(Qt.CursorShape.PointingHandCursor)
    refresh.setToolTip("Refresh workspaces from PrivacyGate")
    refresh.setStyleSheet(
        "QPushButton#WorkspaceRefreshButton{background:#FFFFFF;color:#0B7F89;"
        "border:1px solid #BEE3E4;border-radius:8px;padding:3px;}"
        "QPushButton#WorkspaceRefreshButton:hover{background:#E9F7F7;border-color:#8CCBCD;}"
        "QPushButton#WorkspaceRefreshButton:pressed{background:#DDF3F3;}"
        "QPushButton#WorkspaceRefreshButton:disabled{background:#EEF3F5;border-color:#D5E0E6;}"
    )
    rail_layout.addWidget(refresh, 0, Qt.AlignmentFlag.AlignHCenter)
    outer.insertWidget(0, rail, 0, Qt.AlignmentFlag.AlignTop)

    def finish_visual(*_args) -> None:
        refresh.setEnabled(True)
        refresh.setIcon(icon("restore", color=TEAL, size=16))
        refresh.setToolTip("Refresh workspaces from PrivacyGate")
        panel = getattr(
            getattr(main_window, "settings_page", None),
            "_privacygate_workspace_settings_panel",
            None,
        )
        if panel is not None:
            panel.refresh()

    def refresh_workspaces() -> None:
        if getattr(team_page, "_active_worker", None) is not None:
            refresh.setToolTip("PrivacyGate is already syncing")
            return
        refresh.setEnabled(False)
        refresh.setIcon(icon("history", color=NAVY, size=16))
        refresh.setToolTip("Refreshing workspaces…")
        team_page.refresh_silent()
        # state_changed normally re-enables immediately after the live result.
        # Keep a fallback so a network error never leaves the small control stuck.
        QTimer.singleShot(4500, finish_visual)

    refresh.clicked.connect(refresh_workspaces)
    team_page.state_changed.connect(finish_visual)

    previous_sidebar = main_window._set_sidebar_expanded

    def set_sidebar_expanded(expanded: bool) -> None:
        previous_sidebar(expanded)
        refresh.setVisible(expanded)
        rail.setMaximumHeight(64 if expanded else 30)

    main_window._set_sidebar_expanded = set_sidebar_expanded
    main_window.workspace_refresh_button = refresh
    main_window._privacygate_workspace_refresh_control = True
    set_sidebar_expanded(bool(getattr(main_window, "sidebar_expanded", True)))
