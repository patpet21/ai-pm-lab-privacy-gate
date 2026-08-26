from __future__ import annotations

import re

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QBoxLayout, QLabel, QPushButton, QTableWidget, QWidget


NAVY = "#062B4F"
INK = "#17384E"
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

SECTION_TITLES = {
    "Quick actions",
    "Protection Policy",
    "Approved AI",
    "Approved Apps",
    "Members",
    "Devices",
}

METRIC_TITLES = {"Seats", "Members", "Devices", "Policy"}


def _replace_font_size(widget: QWidget, size: int) -> None:
    style = widget.styleSheet()
    if "font-size" in style:
        widget.setStyleSheet(
            re.sub(
                r"font-size\s*:\s*\d+px",
                f"font-size:{size}px",
                style,
                count=1,
            )
        )


def _find_app_tile(overview: QWidget, app_label: str) -> QWidget | None:
    for label in overview.findChildren(QLabel):
        if label.text().strip() == app_label:
            return label.parentWidget()
    return None


def _style_icon_only_app(tile: QWidget, app_label: str) -> None:
    labels = tile.findChildren(QLabel)
    status_text = ""
    logo = None
    for label in labels:
        text = label.text().strip()
        if text in {"✓", "Allowed", "⊘", "Blocked"}:
            status_text = text
            label.hide()
        elif text == app_label:
            label.hide()
        if label.pixmap() is not None:
            logo = label

    allowed = status_text in {"✓", "Allowed"}
    state = "Allowed" if allowed else "Blocked"
    tile.setToolTip(f"{app_label} • {state}\nClick to open in Apps")
    tile.setMinimumHeight(52)
    tile.setStyleSheet(
        f"QWidget#{tile.objectName()}{{background:#FBFDFE;border:1px solid #DCE5EA;border-radius:10px;}}"
        f"QWidget#{tile.objectName()}:hover{{background:#EAF7F7;border-color:#8FC8CD;}}"
    )

    if logo is not None:
        logo.setVisible(True)
        logo.setFixedSize(34, 34)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            layout = tile.layout()
            if isinstance(layout, QBoxLayout):
                layout.setContentsMargins(6, 6, 6, 6)
                layout.setSpacing(0)
                layout.setAlignment(logo, Qt.AlignmentFlag.AlignCenter)
        except (RuntimeError, TypeError):
            pass


def _style_overview(dashboard) -> None:
    stack = getattr(dashboard, "stack", None)
    if stack is None or stack.count() == 0:
        return
    overview = stack.widget(0)
    if overview is None:
        return

    # Fixed, non-accumulating typography. The Overview refreshes often; every
    # semantic label is reset to the same compact executive scale each time.
    for label in overview.findChildren(QLabel):
        text = label.text().strip()
        if text in SECTION_TITLES:
            label.setStyleSheet(
                f"color:{NAVY};font-size:12px;font-weight:900;border:none;background:transparent;"
            )
        elif text in METRIC_TITLES:
            label.setStyleSheet(
                f"color:{NAVY};font-size:9px;font-weight:850;border:none;background:transparent;"
            )
        elif text in {"Allowed", "Blocked", "✓", "⊘"}:
            allowed = text in {"Allowed", "✓"}
            label.setStyleSheet(
                f"color:{GREEN if allowed else RED};font-size:9px;font-weight:900;border:none;background:transparent;"
            )
        elif label.pixmap() is None:
            style = label.styleSheet()
            match = re.search(r"font-size\s*:\s*(\d+)px", style)
            if match and int(match.group(1)) > 11:
                _replace_font_size(label, 10)
            elif match and int(match.group(1)) < 8:
                _replace_font_size(label, 8)

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

    for app_label in APP_LABELS:
        tile = _find_app_tile(overview, app_label)
        if tile is not None:
            _style_icon_only_app(tile, app_label)

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


def apply_organization_overview_consistency(main_window) -> None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = (
        getattr(team_page, "_privacygate_premium_dashboard", None)
        if team_page is not None
        else None
    )
    if dashboard is None:
        return

    def polish() -> None:
        _style_overview(dashboard)

    if not bool(getattr(dashboard, "_privacygate_overview_consistency_wrapped", False)):
        original_render = dashboard.render

        def render_with_consistency(*args, **kwargs):
            result = original_render(*args, **kwargs)
            QTimer.singleShot(0, polish)
            QTimer.singleShot(220, polish)
            return result

        dashboard.render = render_with_consistency
        dashboard._privacygate_overview_consistency_wrapped = True

    QTimer.singleShot(0, polish)
    QTimer.singleShot(250, polish)
    QTimer.singleShot(800, polish)
