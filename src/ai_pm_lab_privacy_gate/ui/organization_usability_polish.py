from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
RED = "#B54747"
BORDER = "#DCE5EA"

APP_SPECS = (
    ("gmail", "Gmail"),
    ("google_drive", "Google Drive"),
    ("asana", "Asana"),
    ("clickup", "ClickUp"),
    ("trello", "Trello"),
    ("notion", "Notion"),
    ("monday", "monday.com"),
    ("jira", "Jira"),
)


def _safe_set_pixmap(target: QLabel, pixmap, size: int) -> None:
    try:
        target.setPixmap(
            pixmap.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    except RuntimeError:
        # The tile may have been rebuilt while an async logo request was in flight.
        return


def _open_plugins(main_window, provider_label: str = "") -> None:
    index = getattr(main_window, "apps_page_index", None)
    if index is not None:
        main_window._show_page(int(index))
    else:
        page = getattr(main_window, "apps_hub_page", None)
        pages = getattr(main_window, "pages", None)
        if page is not None and pages is not None:
            page_index = pages.indexOf(page)
            if page_index >= 0:
                main_window._show_page(page_index)

    if not provider_label:
        return

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


class _PluginClickFilter(QObject):
    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self.main_window = main_window

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if event.type() == QEvent.Type.MouseButtonRelease:
            try:
                if event.button() != Qt.MouseButton.LeftButton:
                    return False
                label = str(watched.property("privacygatePluginLabel") or "")
            except RuntimeError:
                return False
            if label:
                _open_plugins(self.main_window, label)
                return True
        return False


def _scale_qss_font(widget: QWidget, bump: int = 2, *, maximum: int = 30) -> None:
    if bool(widget.property("privacygateOrgFontScaled")):
        return
    style = widget.styleSheet()
    match = re.search(r"font-size\s*:\s*(\d+)px", style)
    if not match:
        return
    current = int(match.group(1))
    updated = min(maximum, current + bump)
    widget.setStyleSheet(
        re.sub(
            r"font-size\s*:\s*\d+px",
            f"font-size:{updated}px",
            style,
            count=1,
        )
    )
    widget.setProperty("privacygateOrgFontScaled", True)


def _scale_text_tree(root: QWidget, bump: int = 2) -> None:
    for label in root.findChildren(QLabel):
        _scale_qss_font(label, bump)
    for button in root.findChildren(QPushButton):
        _scale_qss_font(button, bump)


def _polish_overview(main_window, dashboard, click_filter: _PluginClickFilter) -> None:
    overview = getattr(dashboard, "overview", None)
    if overview is None:
        return

    _scale_text_tree(overview, 2)

    for value in getattr(dashboard, "metric_values", {}).values():
        value.setStyleSheet(
            f"color:{NAVY};font-size:24px;font-weight:950;border:none;background:transparent;"
        )
    for detail in getattr(dashboard, "metric_details", {}).values():
        detail.setStyleSheet(
            f"color:{MUTED};font-size:11px;border:none;background:transparent;"
        )

    for button in (
        getattr(dashboard, "quick_invite", None),
        getattr(dashboard, "quick_policy", None),
        getattr(dashboard, "quick_publish", None),
    ):
        if isinstance(button, QPushButton):
            button.setMinimumHeight(70)
            button.setStyleSheet(
                "QPushButton{background:#FFFFFF;color:#062B4F;border:1px solid #DCE5EA;"
                "border-radius:11px;padding:10px 13px;text-align:left;font-size:12px;font-weight:750;}"
                "QPushButton:hover{background:#F2FAFA;border-color:#9CCFD2;}"
            )

    apps_grid = getattr(dashboard, "apps_grid", None)
    logo_loader = getattr(dashboard, "logo_loader", None)
    if apps_grid is None:
        return

    for index, (provider, label) in enumerate(APP_SPECS):
        item = apps_grid.itemAtPosition(index // 4, index % 4)
        tile = item.widget() if item is not None else None
        if tile is None:
            continue
        tile.setObjectName(f"OverviewPluginTile_{provider}")
        tile.setProperty("privacygatePluginLabel", label)
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setMinimumHeight(58)
        tile.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        tile.setToolTip(f"Open {label} in Apps")
        tile.setStyleSheet(
            f"QWidget#{tile.objectName()}{{background:#FBFDFE;border:1px solid #DCE5EA;border-radius:10px;}}"
            f"QWidget#{tile.objectName()}:hover{{background:#EAF7F7;border-color:#8FC8CD;}}"
        )
        tile.removeEventFilter(click_filter)
        tile.installEventFilter(click_filter)

        labels = tile.findChildren(QLabel)
        logo = next((child for child in labels if child.pixmap() is not None), None)
        name = next((child for child in labels if child.text().strip() == label), None)
        status = next(
            (
                child
                for child in labels
                if child.text().strip() in {"✓", "⊘", "Allowed", "Blocked"}
            ),
            None,
        )
        if logo is not None:
            logo.setFixedSize(38, 38)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            if logo_loader is not None:
                logo_loader.load(
                    provider,
                    lambda pixmap, target=logo: _safe_set_pixmap(target, pixmap, 34),
                )
        if name is not None:
            name.setStyleSheet(
                f"color:{NAVY};font-size:11px;font-weight:850;border:none;background:transparent;"
            )
            name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if status is not None:
            allowed = status.text().strip() in {"✓", "Allowed"}
            status.setStyleSheet(
                f"color:{GREEN if allowed else RED};font-size:11px;font-weight:950;border:none;background:transparent;"
            )
            status.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    for table_info in (
        getattr(dashboard, "members_preview", None),
        getattr(dashboard, "devices_preview", None),
    ):
        if isinstance(table_info, tuple) and len(table_info) > 1:
            table = table_info[1]
            if isinstance(table, QTableWidget):
                table.setStyleSheet(
                    "QTableWidget{background:#FFFFFF;color:#17384E;border:none;gridline-color:#E7EDF1;font-size:10px;}"
                    "QTableWidget::item{padding:6px;}"
                    "QHeaderView::section{background:#FFFFFF;color:#415C70;border:none;border-bottom:1px solid #E2E9EE;"
                    "padding:9px;font-size:10px;font-weight:850;}"
                )


def _add_policy_flexibility_card(policy_view: QWidget) -> None:
    if policy_view.findChild(QFrame, "OrganizationPolicyFlexibility") is not None:
        return
    root = policy_view.layout()
    if not isinstance(root, QVBoxLayout):
        return

    card = QFrame(objectName="OrganizationPolicyFlexibility")
    card.setStyleSheet(
        "QFrame#OrganizationPolicyFlexibility{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:12px;}"
    )
    box = QVBoxLayout(card)
    box.setContentsMargins(15, 11, 15, 11)
    box.setSpacing(7)

    title = QLabel("Flexible protection modes")
    title.setStyleSheet(f"color:{NAVY};font-size:14px;font-weight:900;border:none;")
    intro = QLabel(
        "Set a different level for each type of sensitive data. Strict rules can be locked by the company, "
        "while lower-risk data can stay flexible for the employee."
    )
    intro.setWordWrap(True)
    intro.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")
    box.addWidget(title)
    box.addWidget(intro)

    grid = QGridLayout()
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(6)
    modes = (
        ("Required protect", "Always protected. Employees cannot bypass the rule.", "LOCKED"),
        ("Protect by default", "PrivacyGate protects it automatically, with a clear default.", "DEFAULT"),
        ("Employee choice", "The employee decides case by case before protection.", "FLEXIBLE"),
        ("Allow visible", "The data may remain visible when company policy permits it.", "OPEN"),
    )
    for column, (heading, detail, badge) in enumerate(modes):
        tile = QFrame()
        tile.setStyleSheet(
            "QFrame{background:#F8FBFC;border:1px solid #E2E9ED;border-radius:9px;}"
        )
        tile_box = QVBoxLayout(tile)
        tile_box.setContentsMargins(10, 8, 10, 8)
        tile_box.setSpacing(3)
        head = QLabel(heading)
        head.setStyleSheet(f"color:{INK};font-size:10px;font-weight:900;border:none;")
        note = QLabel(detail)
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
        chip = QLabel(badge)
        chip.setStyleSheet(
            "background:#E8F7F7;color:#0B7F89;border:none;border-radius:7px;"
            "padding:3px 6px;font-size:8px;font-weight:900;"
        )
        tile_box.addWidget(head)
        tile_box.addWidget(note)
        tile_box.addWidget(chip, alignment=Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(tile, 0, column)
    box.addLayout(grid)
    root.insertWidget(2, card)


def _polish_policy_view(policy_view: QWidget) -> None:
    _add_policy_flexibility_card(policy_view)
    _scale_text_tree(policy_view, 2)

    for label in policy_view.findChildren(QLabel):
        text = label.text().strip()
        if text.startswith("Define what employees must protect"):
            label.setText(
                "Set the privacy guardrails for this workspace: what must always be protected, what is protected by default, "
                "what employees may decide case by case, and what may remain visible. Rules sync to managed devices and are enforced locally in Protect and Privacy Preflight."
            )
            label.setStyleSheet(f"color:{MUTED};font-size:11px;border:none;background:transparent;")
        elif text == "How this policy is used":
            label.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:900;border:none;")
        elif text.startswith("The policy is operational"):
            label.setText(
                "The policy follows the selected company workspace. Employees still work in the normal Protect page; PrivacyGate applies the company rules locally before a protected copy can be used with AI or an approved app."
            )
            label.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")
        elif text.startswith("Enforcement happens locally"):
            label.setText(
                "What stays private: Organization can manage policy and account access, but it never receives document contents, restore mappings, source item lists or connector credentials."
            )
            label.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")

    for button in policy_view.findChildren(QPushButton):
        if "Edit policy" in button.text():
            button.setMinimumHeight(40)
            button.setStyleSheet(
                "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:9px;"
                "padding:9px 15px;font-size:11px;font-weight:850;}"
                "QPushButton:hover{background:#096D76;}"
            )


def _add_apps_readiness_card(main_window, dashboard, apps_view: QWidget) -> None:
    if apps_view.findChild(QFrame, "OrganizationWorkspaceReadiness") is not None:
        return
    root = apps_view.layout()
    if not isinstance(root, QVBoxLayout):
        return

    card = QFrame(objectName="OrganizationWorkspaceReadiness")
    card.setStyleSheet(
        "QFrame#OrganizationWorkspaceReadiness{background:#F8FBFC;border:1px solid #DCE5EA;border-radius:11px;}"
    )
    row = QHBoxLayout(card)
    row.setContentsMargins(13, 10, 13, 10)
    row.setSpacing(12)

    copy = QVBoxLayout()
    copy.setSpacing(2)
    title = QLabel("Workspace readiness & next action")
    title.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:900;border:none;")
    summary = QLabel("Checking workspace readiness…")
    summary.setWordWrap(True)
    summary.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")
    copy.addWidget(title)
    copy.addWidget(summary)
    row.addLayout(copy, 1)

    review_policy = QPushButton("Review policy")
    review_policy.setCursor(Qt.CursorShape.PointingHandCursor)
    review_policy.setMinimumHeight(36)
    review_policy.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:8px;"
        "padding:8px 12px;font-size:10px;font-weight:800;}"
        "QPushButton:hover{background:#F2FAFA;border-color:#96C9CD;color:#0B7180;}"
    )
    review_policy.clicked.connect(lambda: dashboard._select_tab(2))
    row.addWidget(review_policy)

    manage_plugins = QPushButton("Manage plugins")
    manage_plugins.setCursor(Qt.CursorShape.PointingHandCursor)
    manage_plugins.setMinimumHeight(36)
    manage_plugins.setStyleSheet(
        "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:8px;"
        "padding:8px 13px;font-size:10px;font-weight:850;}"
        "QPushButton:hover{background:#096D76;}"
    )
    manage_plugins.clicked.connect(lambda: _open_plugins(main_window))
    row.addWidget(manage_plugins)

    apps_view._privacygate_readiness_summary = summary
    root.insertWidget(1, card)


def _update_apps_readiness(apps_view) -> None:
    summary = getattr(apps_view, "_privacygate_readiness_summary", None)
    if not isinstance(summary, QLabel):
        return
    try:
        policy = apps_view._policy()
        rows = list(apps_view._account_rows())
        active_key = str(apps_view.workspace_combo.currentData() or "")
        approved_accounts = sum(
            1
            for provider, _label, account_id, _account_label in rows
            if active_key and apps_view.store.is_account_available(provider, account_id, active_key)
        )
        allowed_apps = sum(
            1
            for provider, _label in APP_SPECS
            if policy
            and bool(
                policy.allowed_connectors.get(
                    provider, policy.allowed_connectors.get("*", False)
                )
            )
        )
        allowed_ai = sum(
            1
            for key in ("chatgpt", "claude", "other")
            if policy and bool(policy.allowed_ai.get(key, False))
        )
    except Exception:
        return

    if policy is None:
        summary.setText(
            "Action needed: company policy is still syncing or unavailable. Managed plugin use stays blocked until policy is available locally."
        )
        return
    if approved_accounts == 0:
        summary.setText(
            f"Policy v{policy.version} is active • {allowed_ai} AI destinations • {allowed_apps} apps approved • "
            "No connected account is authorized for this workspace yet."
        )
        return
    summary.setText(
        f"Ready • Policy v{policy.version} active • {allowed_ai} AI destinations • {allowed_apps} apps approved • "
        f"{approved_accounts} connected account{'s' if approved_accounts != 1 else ''} authorized for this workspace."
    )


def _polish_apps_view(main_window, dashboard, apps_view, click_filter: _PluginClickFilter) -> None:
    _add_apps_readiness_card(main_window, dashboard, apps_view)
    _scale_text_tree(apps_view, 2)

    combo = getattr(apps_view, "workspace_combo", None)
    if isinstance(combo, QComboBox):
        combo.setMinimumHeight(40)
        combo.setStyleSheet(
            "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:9px;"
            "padding:7px 10px;font-size:11px;}"
            "QComboBox:focus{border-color:#1595A3;}"
        )

    table = getattr(apps_view, "accounts_table", None)
    if isinstance(table, QTableWidget):
        table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#17384E;border:none;font-size:10px;}"
            "QTableWidget::item{padding:8px;border-bottom:1px solid #EEF2F4;font-size:10px;}"
            "QTableWidget::item:selected{background:#EAF7F7;color:#062B4F;}"
            "QHeaderView::section{background:#F8FBFC;color:#425D70;border:none;border-bottom:1px solid #DCE5EA;"
            "padding:8px;font-size:9px;font-weight:850;}"
        )
        for row in range(table.rowCount()):
            table.setRowHeight(row, 46)

    logo_loader = getattr(apps_view, "logo_loader", None)
    status_labels = getattr(apps_view, "app_status_labels", {})
    for provider, label in APP_SPECS:
        status = status_labels.get(provider)
        if not isinstance(status, QLabel):
            continue
        tile = status.parentWidget()
        if not isinstance(tile, QFrame):
            continue
        tile.setObjectName(f"OrgAdminPluginTile_{provider}")
        tile.setProperty("privacygatePluginLabel", label)
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setMinimumHeight(66)
        tile.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        tile.setToolTip(f"Open {label} in Apps")
        tile.setStyleSheet(
            f"QFrame#{tile.objectName()}{{background:#FBFDFE;border:1px solid #DCE5EA;border-radius:10px;}}"
            f"QFrame#{tile.objectName()}:hover{{background:#EAF7F7;border-color:#8FC8CD;}}"
        )
        tile.removeEventFilter(click_filter)
        tile.installEventFilter(click_filter)

        labels = tile.findChildren(QLabel)
        logo = next((child for child in labels if child.pixmap() is not None), None)
        name = next((child for child in labels if child.text().strip() == label), None)
        allowed = status.text().strip() == "Allowed"
        status.setStyleSheet(
            f"color:{GREEN if allowed else RED};font-size:10px;font-weight:900;border:none;background:transparent;"
        )
        status.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if name is not None:
            name.setStyleSheet(
                f"color:{INK};font-size:11px;font-weight:850;border:none;background:transparent;"
            )
            name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if logo is not None:
            logo.setFixedSize(38, 38)
            logo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            if logo_loader is not None:
                logo_loader.load(
                    provider,
                    lambda pixmap, target=logo: _safe_set_pixmap(target, pixmap, 34),
                )

    for status in getattr(apps_view, "ai_status_labels", {}).values():
        if isinstance(status, QLabel):
            allowed = status.text().strip() == "Allowed"
            status.setStyleSheet(
                f"color:{GREEN if allowed else RED};font-size:10px;font-weight:900;border:none;"
            )

    _update_apps_readiness(apps_view)


def _wrap_render(instance, polish) -> None:
    if bool(getattr(instance, "_privacygate_usability_render_wrapped", False)):
        polish()
        return
    original = instance.render

    def render_with_polish(*args, **kwargs):
        result = original(*args, **kwargs)
        QTimer.singleShot(0, polish)
        return result

    instance.render = render_with_polish
    instance._privacygate_usability_render_wrapped = True
    polish()


def apply_organization_usability_polish(main_window) -> None:
    """Make Organization easier to read and operate without changing its data model.

    This is intentionally a late visual/interaction pass. It keeps the existing
    Organization control-plane architecture, but enlarges the dense text, makes
    app tiles behave like real navigation controls, explains policy flexibility,
    and adds a compact workspace-readiness/next-action surface.
    """

    team_page = getattr(main_window, "team_page", None)
    dashboard = (
        getattr(team_page, "_privacygate_premium_dashboard", None)
        if team_page is not None
        else None
    )
    if dashboard is None:
        return

    click_filter = getattr(main_window, "_privacygate_org_plugin_click_filter", None)
    if click_filter is None:
        click_filter = _PluginClickFilter(main_window)
        main_window._privacygate_org_plugin_click_filter = click_filter

    _wrap_render(
        dashboard,
        lambda: _polish_overview(main_window, dashboard, click_filter),
    )

    if dashboard.stack.count() > 2:
        policy_view = dashboard.stack.widget(2)
        if policy_view is not None:
            render = getattr(policy_view, "render", None)
            if callable(render):
                _wrap_render(policy_view, lambda: _polish_policy_view(policy_view))
            else:
                _polish_policy_view(policy_view)

    if dashboard.stack.count() > 4:
        apps_view = dashboard.stack.widget(4)
        if apps_view is not None:
            render = getattr(apps_view, "render", None)
            if callable(render):
                _wrap_render(
                    apps_view,
                    lambda: _polish_apps_view(
                        main_window, dashboard, apps_view, click_filter
                    ),
                )
            else:
                _polish_apps_view(main_window, dashboard, apps_view, click_filter)
