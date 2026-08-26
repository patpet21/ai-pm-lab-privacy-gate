from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.domain.company_policy import ProtectionDirective
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
RED = "#B54747"
BORDER = "#DCE5EA"


def _card(name: str) -> QFrame:
    frame = QFrame(objectName=name)
    frame.setStyleSheet(
        f"QFrame#{name}{{background:#FFFFFF;border:1px solid {BORDER};border-radius:12px;}}"
    )
    return frame


def _title(text: str, size: int = 13) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color:{NAVY};font-size:{size}px;font-weight:900;")
    return label


def _muted(text: str = "", size: int = 8) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{MUTED};font-size:{size}px;")
    return label


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear(child)


def _run(page, method_name: str) -> None:
    method = getattr(page, method_name, None)
    if callable(method):
        method()


class ApprovedOrganizationOverview(QWidget):
    """Organization overview that mirrors the approved screenshot while using live state."""

    def __init__(self, main_window, team_page, dashboard, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.team_page = team_page
        self.dashboard = dashboard
        self.logo_loader = ProviderLogoLoader(team_page.state_store.data_dir, self)
        self.metric_values: dict[str, QLabel] = {}
        self.metric_details: dict[str, QLabel] = {}
        self.policy_rows = QVBoxLayout()
        self.ai_row = QHBoxLayout()
        self.apps_grid = QGridLayout()
        self._build()
        self.render()
        team_page.state_changed.connect(lambda _state: self.render())

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        specs = (
            ("seats", "Seats", "contact"),
            ("members", "Members", "contact"),
            ("devices", "Devices", "document"),
            ("policy", "Policy", "protect"),
        )
        for column, (key, label, icon_name) in enumerate(specs):
            card = _card(f"ApprovedMetric_{key}")
            card.setMinimumHeight(94)
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 12, 14, 12)
            row.setSpacing(11)
            bubble = QLabel()
            bubble.setFixedSize(46, 46)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setPixmap(icon(icon_name, color=TEAL, size=25).pixmap(25, 25))
            bubble.setStyleSheet("background:#E8F7F7;border-radius:23px;")
            row.addWidget(bubble)
            text = QVBoxLayout()
            text.setSpacing(0)
            heading = QLabel(label)
            heading.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:800;")
            value = QLabel("—")
            value.setStyleSheet(f"color:{NAVY};font-size:19px;font-weight:950;")
            detail = QLabel("")
            detail.setStyleSheet(f"color:{MUTED};font-size:8px;")
            text.addWidget(heading)
            text.addWidget(value)
            text.addWidget(detail)
            row.addLayout(text, 1)
            metrics.addWidget(card, 0, column)
            self.metric_values[key] = value
            self.metric_details[key] = detail
        root.addLayout(metrics)

        body = QHBoxLayout()
        body.setSpacing(12)

        quick = _card("ApprovedQuickActions")
        quick_box = QVBoxLayout(quick)
        quick_box.setContentsMargins(14, 12, 14, 12)
        quick_box.setSpacing(8)
        quick_box.addWidget(_title("⚡  Quick actions", 11))
        self.invite_button = self._action("Invite member", "Add people to your organization", "contact")
        self.policy_button = self._action("Edit policy", "Update protection rules", "settings")
        self.publish_button = self._action("Publish update", "Sync policy to all devices", "protect")
        self.invite_button.clicked.connect(lambda: _run(self.team_page, "_create_invite"))
        self.policy_button.clicked.connect(lambda: _run(self.team_page, "_edit_policy"))
        self.publish_button.clicked.connect(self.team_page.refresh)
        quick_box.addWidget(self.invite_button)
        quick_box.addWidget(self.policy_button)
        quick_box.addWidget(self.publish_button)
        quick_box.addStretch(1)
        body.addWidget(quick, 3)

        policy = _card("ApprovedProtectionPolicy")
        policy_box = QVBoxLayout(policy)
        policy_box.setContentsMargins(14, 12, 14, 12)
        policy_box.setSpacing(5)
        top = QHBoxLayout()
        top.addWidget(_title("🛡  Protection Policy", 11), 1)
        self.policy_version = QLabel("—")
        self.policy_version.setStyleSheet(
            "background:#E8F7F7;color:#0B7F89;border-radius:7px;padding:3px 7px;font-size:8px;font-weight:900;"
        )
        top.addWidget(self.policy_version)
        policy_box.addLayout(top)
        policy_box.addLayout(self.policy_rows)
        policy_box.addStretch(1)
        body.addWidget(policy, 4)

        destination_column = QVBoxLayout()
        destination_column.setSpacing(9)

        ai_card = _card("ApprovedAI")
        ai_box = QVBoxLayout(ai_card)
        ai_box.setContentsMargins(12, 10, 12, 10)
        ai_box.addWidget(_title("✦  Approved AI", 11))
        self.ai_row.setSpacing(7)
        ai_box.addLayout(self.ai_row)
        destination_column.addWidget(ai_card)

        apps_card = _card("ApprovedApps")
        apps_box = QVBoxLayout(apps_card)
        apps_box.setContentsMargins(12, 10, 12, 10)
        apps_box.addWidget(_title("✦  Approved Apps", 11))
        self.apps_grid.setHorizontalSpacing(10)
        self.apps_grid.setVerticalSpacing(7)
        apps_box.addLayout(self.apps_grid)
        destination_column.addWidget(apps_card)
        body.addLayout(destination_column, 5)
        root.addLayout(body)

        previews = QHBoxLayout()
        previews.setSpacing(12)
        self.members_card, self.members_table = self._table_card(
            "Members", ["Name", "Role", "Status", "Joined"]
        )
        self.devices_card, self.devices_table = self._table_card(
            "Devices", ["Device", "User", "Policy Version", "Status"]
        )
        previews.addWidget(self.members_card, 1)
        previews.addWidget(self.devices_card, 1)
        root.addLayout(previews)

        boundary = _card("ApprovedLocalBoundary")
        row = QHBoxLayout(boundary)
        row.setContentsMargins(14, 10, 14, 10)
        shield = QLabel()
        shield.setPixmap(icon("protect", color=NAVY, size=20).pixmap(20, 20))
        row.addWidget(shield)
        text = QLabel(
            "Documents, restore mappings, and connector tokens stay local on employee devices.\n"
            "No documents or connector credentials are stored in the cloud."
        )
        text.setStyleSheet(f"color:{INK};font-size:8px;font-weight:700;")
        row.addWidget(text, 1)
        root.addWidget(boundary)

    def _action(self, heading: str, detail: str, icon_name: str) -> QPushButton:
        button = QPushButton(f"{heading}\n{detail}")
        button.setIcon(icon(icon_name, color=NAVY, size=19))
        button.setMinimumHeight(57)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#062B4F;border:1px solid #DCE5EA;border-radius:9px;"
            "padding:7px 10px;text-align:left;font-size:9px;font-weight:750;}"
            "QPushButton:hover{background:#F1FAFA;border-color:#9CCFD2;}"
        )
        return button

    def _table_card(self, heading: str, columns: list[str]) -> tuple[QFrame, QTableWidget]:
        card = _card(f"Approved{heading}Table")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 9, 12, 9)
        top = QHBoxLayout()
        top.addWidget(_title(("♙  " if heading == "Members" else "▰  ") + heading, 11), 1)
        view_all = QPushButton("View all")
        view_all.setStyleSheet(
            "QPushButton{background:transparent;color:#0B7F89;border:none;font-size:8px;font-weight:800;}"
        )
        visual_index = 1 if heading == "Members" else 4
        view_all.clicked.connect(lambda _checked=False, i=visual_index: self.dashboard._select_tab(i))
        top.addWidget(view_all)
        box.addLayout(top)
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.setMinimumHeight(145)
        table.setMaximumHeight(190)
        table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#17384E;border:none;}"
            "QTableWidget::item{padding:5px;border-bottom:1px solid #EEF2F4;font-size:8px;}"
            "QHeaderView::section{background:#FFFFFF;color:#425D70;border:none;border-bottom:1px solid #E2E9ED;"
            "padding:6px;font-size:7px;font-weight:850;}"
        )
        for column in range(len(columns)):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        box.addWidget(table)
        return card, table

    def _policy_row(self, name: str, value: str, locked: bool) -> QWidget:
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 5, 0, 5)
        label = QLabel(name)
        label.setStyleSheet(f"color:{INK};font-size:8px;font-weight:750;")
        result = QLabel(value)
        result.setStyleSheet(f"color:{MUTED};font-size:8px;")
        mark = QLabel("🔒" if locked else "✓")
        mark.setStyleSheet(f"color:{GREEN};font-size:9px;")
        box.addWidget(label, 1)
        box.addWidget(result)
        box.addWidget(mark)
        return row

    def _ai_tile(self, provider: str, name: str, allowed: bool) -> QFrame:
        tile = _card(f"OverviewAI_{provider}")
        box = QVBoxLayout(tile)
        box.setContentsMargins(8, 7, 8, 7)
        box.setSpacing(2)
        logo = QLabel()
        logo.setFixedHeight(28)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_loader.load(
            provider,
            lambda pixmap, target=logo: target.setPixmap(
                pixmap.scaled(27, 27, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            ),
        )
        label = QLabel(name)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color:{NAVY};font-size:8px;font-weight:850;")
        status = QLabel("Allowed" if allowed else "⊘ Blocked")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setStyleSheet(f"color:{GREEN if allowed else RED};font-size:7px;font-weight:850;")
        box.addWidget(logo)
        box.addWidget(label)
        box.addWidget(status)
        return tile

    def _app_item(self, provider: str, name: str, allowed: bool) -> QWidget:
        item = QWidget()
        row = QHBoxLayout(item)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(5)
        logo = QLabel()
        logo.setFixedSize(19, 19)
        self.logo_loader.load(
            provider,
            lambda pixmap, target=logo: target.setPixmap(
                pixmap.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            ),
        )
        label = QLabel(name)
        label.setStyleSheet(f"color:{INK};font-size:7px;font-weight:750;")
        status = QLabel("●" if allowed else "⊘")
        status.setStyleSheet(f"color:{GREEN if allowed else RED};font-size:8px;font-weight:900;")
        row.addWidget(logo)
        row.addWidget(label, 1)
        row.addWidget(status)
        return item

    def render(self) -> None:
        state = self.team_page.state
        policy = state.policy
        active_members = [
            member for member in self.team_page._members
            if str(member.get("status") or "active").lower() == "active"
        ]
        active_devices = [
            device for device in self.team_page._devices
            if str(device.get("status") or "active").lower() == "active"
        ]
        self.metric_values["seats"].setText(
            f"{len(active_members)} / {state.seat_limit}" if state.seat_limit else str(len(active_members))
        )
        self.metric_details["seats"].setText(f"{state.plan.label} plan")
        self.metric_values["members"].setText(f"{len(active_members)} active")
        disabled = max(0, len(self.team_page._members) - len(active_members))
        self.metric_details["members"].setText(f"{disabled} disabled" if disabled else "All active")
        self.metric_values["devices"].setText(f"{len(active_devices)} managed")
        self.metric_details["devices"].setText("All up to date")
        version = policy.version if policy else 0
        self.metric_values["policy"].setText(f"v{version} synced" if version else "—")
        self.metric_details["policy"].setText("Updated recently" if version else "No active policy")
        self.policy_version.setText(f"v{version}" if version else "—")

        can_admin = state.role in {"owner", "admin"}
        self.invite_button.setVisible(can_admin)
        self.policy_button.setVisible(can_admin and policy is not None)

        _clear(self.policy_rows)
        if policy is not None:
            names = (
                ("US_SSN", "SSN"),
                ("US_BANK_NUMBER", "Bank account"),
                ("EMAIL_ADDRESS", "Email"),
                ("PERSON", "Person name"),
                ("STREET_ADDRESS", "Property address"),
            )
            labels = {
                ProtectionDirective.REQUIRED_PROTECT: "Required",
                ProtectionDirective.DEFAULT_PROTECT: "Default protect",
                ProtectionDirective.USER_CHOICE: "User choice",
                ProtectionDirective.ALLOW: "Allowed",
            }
            for entity, name in names:
                directive = policy.protection_rules.get(entity, ProtectionDirective.USER_CHOICE)
                self.policy_rows.addWidget(
                    self._policy_row(name, labels[directive], directive is ProtectionDirective.REQUIRED_PROTECT)
                )

        _clear(self.ai_row)
        for provider, name, key in (
            ("chatgpt", "ChatGPT", "chatgpt"),
            ("claude", "Claude", "claude"),
            ("gemini", "Gemini", "other"),
        ):
            allowed = bool(policy and policy.allowed_ai.get(key, False)) if policy else True
            self.ai_row.addWidget(self._ai_tile(provider, name, allowed), 1)

        _clear(self.apps_grid)
        for index, (provider, name) in enumerate(
            (
                ("gmail", "Gmail"),
                ("google_drive", "Google Drive"),
                ("asana", "Asana"),
                ("clickup", "ClickUp"),
                ("trello", "Trello"),
                ("notion", "Notion"),
                ("monday", "monday.com"),
                ("jira", "Jira"),
            )
        ):
            allowed = bool(
                policy and policy.allowed_connectors.get(
                    provider, policy.allowed_connectors.get("*", False)
                )
            ) if policy else True
            self.apps_grid.addWidget(self._app_item(provider, name, allowed), index // 4, index % 4)

        member_rows = self.team_page._members[:4]
        self.members_table.setRowCount(len(member_rows))
        for row, member in enumerate(member_rows):
            name = str(member.get("display_name") or member.get("email") or member.get("user_id") or "Member")
            role = str(member.get("role") or "member").title()
            status = str(member.get("status") or "active").title()
            joined = str(member.get("created_at") or member.get("joined_at") or "")[:10] or "—"
            for column, value in enumerate((name, role, status, joined)):
                self.members_table.setItem(row, column, QTableWidgetItem(value))

        device_rows = self.team_page._devices[:4]
        self.devices_table.setRowCount(len(device_rows))
        for row, device in enumerate(device_rows):
            name = str(device.get("display_name") or "Device")
            user = str(device.get("email") or device.get("user_id") or "Member")
            policy_version = device.get("last_policy_version")
            version_text = f"v{policy_version}" if policy_version else "—"
            status = str(device.get("status") or "active").replace("_", " ").title()
            for column, value in enumerate((name, user, version_text, status)):
                self.devices_table.setItem(row, column, QTableWidgetItem(value))


def _replace_overview(main_window) -> ApprovedOrganizationOverview | None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = getattr(team_page, "_privacygate_premium_dashboard", None) if team_page else None
    if team_page is None or dashboard is None:
        return None
    if getattr(dashboard, "_approved_overview", None) is not None:
        return dashboard._approved_overview
    stack = getattr(dashboard, "stack", None)
    if stack is None or stack.count() == 0:
        return None
    old = stack.widget(0)
    view = ApprovedOrganizationOverview(main_window, team_page, dashboard, dashboard)
    stack.removeWidget(old)
    old.hide()
    stack.insertWidget(0, view)
    dashboard.overview = view
    dashboard._approved_overview = view
    dashboard._approved_old_overview = old
    dashboard._select_tab(0)
    return view


def _polish_dashboard_header(main_window) -> None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = getattr(team_page, "_privacygate_premium_dashboard", None) if team_page else None
    if dashboard is None:
        return

    plan_badge = getattr(dashboard, "plan_badge", None)
    if plan_badge is not None:
        plan_badge.hide()
    role_badge = getattr(dashboard, "role_badge", None)
    if role_badge is None:
        return

    def render_header(*_args) -> None:
        controller = getattr(main_window, "_privacygate_account_menu_controller", None)
        display_name = "Your Account"
        if controller is not None:
            try:
                display_name = controller._display_name()
            except Exception:
                pass
        if not display_name or display_name == "Your Account":
            email = str(getattr(controller, "email", "") or "") if controller is not None else ""
            display_name = email.split("@", 1)[0].replace(".", " ").title() if email else "PrivacyGate User"
        role = str(getattr(team_page.state, "role", "") or "Member").title()
        initials = "".join(part[0].upper() for part in display_name.split()[:2] if part) or "PG"
        role_badge.setText(f"{initials}    {display_name}\n        {role}")
        role_badge.setStyleSheet(
            "background:transparent;color:#17384E;border:none;padding:3px 8px;"
            "font-size:9px;font-weight:800;"
        )
        role_badge.setToolTip("Account and organization role")

    render_header()
    team_page.state_changed.connect(render_header)
    QTimer.singleShot(1600, render_header)


def _polish_sidebar(main_window) -> None:
    sidebar = getattr(main_window, "sidebar", None)
    if sidebar is None:
        return
    toggle = getattr(main_window, "sidebar_toggle", None)
    if toggle is not None:
        toggle.hide()
    if getattr(main_window, "sidebar_expanded", True):
        sidebar.setFixedWidth(270)
    workspace = getattr(main_window, "workspace_sidebar_card", None)
    if workspace is not None:
        workspace.setMinimumHeight(72)
        workspace.setStyleSheet(
            "QFrame#WorkspaceSwitcherCard{background:#0A5268;border:1px solid #157C8F;border-radius:10px;}"
        )
    for button in getattr(main_window, "nav_buttons", []):
        button.setMinimumHeight(43)
        button.setStyleSheet(
            "QPushButton{background:transparent;color:#DCE7EF;border:none;border-radius:8px;"
            "padding:10px 13px;text-align:left;font-size:10px;font-weight:700;}"
            "QPushButton:hover{background:#0D3A5C;color:#FFFFFF;}"
            "QPushButton:checked{background:#0B7180;color:#FFFFFF;border-left:3px solid #D3A13B;}"
        )
    privacy_note = getattr(main_window, "privacy_note", None)
    if privacy_note is not None:
        privacy_note.setStyleSheet(
            "background:#103C5D;color:#FFFFFF;border:1px solid #315C78;border-radius:9px;"
            "padding:10px;font-size:9px;font-weight:800;"
        )
    account_controller = getattr(main_window, "_privacygate_account_menu_controller", None)
    if account_controller is not None:
        button = getattr(account_controller, "button", None)
        if button is not None:
            button.hide()


def _managed_protect_header(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    team_page = getattr(main_window, "team_page", None)
    if page is None or team_page is None:
        return

    def render(*_args) -> None:
        policy = getattr(team_page.state, "policy", None)
        managed = bool(getattr(team_page.state, "organization_id", "") and policy is not None)
        for label in page.findChildren(QLabel):
            text = label.text().strip()
            if text in {"Protect a document", "Protect & Preflight"}:
                label.setText("Protect & Preflight" if managed else "Protect a document")
            elif text in {
                "Review every detected item before anything leaves this PC.",
                "Managed content follows the active workspace policy before AI handoff.",
            }:
                label.setText(
                    "Managed content follows the active workspace policy before AI handoff."
                    if managed
                    else "Review every detected item before anything leaves this PC."
                )
        badge = getattr(page, "local_badge", None)
        if badge is not None and managed:
            badge.setText(f"{policy.organization_name}  •  POLICY v{policy.version}")

    render()
    team_page.state_changed.connect(render)
    team_page.policy_changed.connect(render)


def apply_approved_mockup_override(main_window) -> None:
    if getattr(main_window, "_approved_mockup_override_applied", False):
        return
    main_window._approved_mockup_override_applied = True
    _replace_overview(main_window)
    _polish_dashboard_header(main_window)
    _polish_sidebar(main_window)
    _managed_protect_header(main_window)
