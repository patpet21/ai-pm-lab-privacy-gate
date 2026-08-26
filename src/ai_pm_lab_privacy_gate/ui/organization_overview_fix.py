from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget, QWidget

from ai_pm_lab_privacy_gate.ui.organization_usability_polish import _open_plugins


NAVY = "#062B4F"
MUTED = "#61798A"
GREEN = "#23824B"
RED = "#B54747"

APP_LABELS = (
    "Gmail",
    "Google Drive",
    "Asana",
    "ClickUp",
    "Trello",
    "Notion",
    "monday.com",
    "Jira",
)


class _OverviewPluginFilter(QObject):
    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self.main_window = main_window

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        try:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            label = str(watched.property("privacygateOverviewPlugin") or "")
        except RuntimeError:
            return False
        if not label:
            return False
        _open_plugins(self.main_window, label)
        return True


def _install_click_target(widget: QWidget, label: str, click_filter: _OverviewPluginFilter) -> None:
    widget.setProperty("privacygateOverviewPlugin", label)
    widget.installEventFilter(click_filter)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    for child in widget.findChildren(QWidget):
        child.setProperty("privacygateOverviewPlugin", label)
        child.installEventFilter(click_filter)
        child.setCursor(Qt.CursorShape.PointingHandCursor)


def _find_tile_for_label(overview: QWidget, app_label: str) -> QWidget | None:
    for label in overview.findChildren(QLabel):
        if label.text().strip() != app_label:
            continue
        candidate = label.parentWidget()
        if candidate is not None:
            return candidate
    return None


def _polish_overview(main_window, dashboard, click_filter: _OverviewPluginFilter) -> None:
    stack = getattr(dashboard, "stack", None)
    if stack is None or stack.count() == 0:
        return
    overview = stack.widget(0)
    if overview is None:
        return

    # IMPORTANT: never increment font sizes here. Overview is rendered and refreshed
    # repeatedly, so additive font bumps accumulate and eventually make the cards
    # unusable. Typography is normalized to fixed values by
    # organization_overview_consistency.
    for button in overview.findChildren(QPushButton):
        button.setMinimumHeight(max(button.minimumHeight(), 36))

    for value in getattr(dashboard, "metric_values", {}).values():
        value.setStyleSheet(
            f"color:{NAVY};font-size:20px;font-weight:950;border:none;background:transparent;"
        )
    for detail in getattr(dashboard, "metric_details", {}).values():
        detail.setStyleSheet(
            f"color:{MUTED};font-size:9px;border:none;background:transparent;"
        )

    for button in (
        getattr(dashboard, "quick_invite", None),
        getattr(dashboard, "quick_policy", None),
        getattr(dashboard, "quick_publish", None),
    ):
        if isinstance(button, QPushButton):
            button.setMinimumHeight(52)
            button.setStyleSheet(
                "QPushButton{background:#FFFFFF;color:#062B4F;border:1px solid #DCE5EA;"
                "border-radius:10px;padding:8px 11px;text-align:left;font-size:10px;font-weight:750;}"
                "QPushButton:hover{background:#F2FAFA;border-color:#9CCFD2;}"
            )

    # Provider navigation remains clickable. The later consistency pass hides the
    # provider text/status so the visible result stays icon-only.
    for app_label in APP_LABELS:
        tile = _find_tile_for_label(overview, app_label)
        if tile is None:
            continue
        tile.setObjectName("OverviewPluginCard_" + re.sub(r"[^A-Za-z0-9]", "", app_label))
        tile.setMinimumHeight(52)
        tile.setToolTip(f"Open {app_label} in Apps")
        tile.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        tile.setStyleSheet(
            f"QWidget#{tile.objectName()}{{background:#FBFDFE;border:1px solid #DCE5EA;border-radius:10px;}}"
            f"QWidget#{tile.objectName()}:hover{{background:#EAF7F7;border-color:#8FC8CD;}}"
        )
        _install_click_target(tile, app_label, click_filter)

        for child_label in tile.findChildren(QLabel):
            text = child_label.text().strip()
            if text == app_label:
                child_label.setStyleSheet(
                    f"color:{NAVY};font-size:10px;font-weight:850;border:none;background:transparent;"
                )
            elif text in {"✓", "Allowed"}:
                child_label.setStyleSheet(
                    f"color:{GREEN};font-size:9px;font-weight:950;border:none;background:transparent;"
                )
            elif text in {"⊘", "Blocked"}:
                child_label.setStyleSheet(
                    f"color:{RED};font-size:9px;font-weight:950;border:none;background:transparent;"
                )
            if child_label.pixmap() is not None:
                child_label.setMinimumSize(30, 30)

    for table_info in (
        getattr(dashboard, "members_preview", None),
        getattr(dashboard, "devices_preview", None),
    ):
        if isinstance(table_info, tuple) and len(table_info) > 1:
            table = table_info[1]
            if isinstance(table, QTableWidget):
                table.setStyleSheet(
                    "QTableWidget{background:#FFFFFF;color:#17384E;border:none;gridline-color:#E7EDF1;font-size:9px;}"
                    "QTableWidget::item{padding:6px;}"
                    "QHeaderView::section{background:#FFFFFF;color:#415C70;border:none;border-bottom:1px solid #E2E9EE;"
                    "padding:7px;font-size:9px;font-weight:850;}"
                )


def apply_organization_overview_fix(main_window) -> None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = (
        getattr(team_page, "_privacygate_premium_dashboard", None)
        if team_page is not None
        else None
    )
    if dashboard is None:
        return

    click_filter = getattr(main_window, "_privacygate_overview_plugin_filter", None)
    if click_filter is None:
        click_filter = _OverviewPluginFilter(main_window)
        main_window._privacygate_overview_plugin_filter = click_filter

    def polish() -> None:
        _polish_overview(main_window, dashboard, click_filter)

    if not bool(getattr(dashboard, "_privacygate_overview_fix_wrapped", False)):
        original_render = dashboard.render

        def render_with_overview_fix(*args, **kwargs):
            result = original_render(*args, **kwargs)
            QTimer.singleShot(0, polish)
            QTimer.singleShot(180, polish)
            return result

        dashboard.render = render_with_overview_fix
        dashboard._privacygate_overview_fix_wrapped = True

    QTimer.singleShot(0, polish)
    QTimer.singleShot(200, polish)
    QTimer.singleShot(700, polish)
