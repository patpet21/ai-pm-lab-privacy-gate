from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.domain.company_policy import ProtectionDirective
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader

NAVY = "#062B4F"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
RED = "#B54747"
WHITE = "#FFFFFF"

# Visual order versus the historic TeamPage QStackedWidget order.
# TeamPage stack: Overview, Members, Policy, Devices, Apps & AI.
VISUAL_TO_STACK = (0, 1, 2, 4, 3)
STACK_TO_VISUAL = {stack: visual for visual, stack in enumerate(VISUAL_TO_STACK)}


class OrganizationDashboardView(QWidget):
    def __init__(self, team_page, parent=None) -> None:
        super().__init__(parent)
        self.team_page = team_page
        self.logo_loader = ProviderLogoLoader(team_page.state_store.data_dir, self)
        self.setObjectName("PremiumOrganizationDashboard")
        self._build()
        self.render()
        team_page.state_changed.connect(lambda _state: self.render())

    def _card(self) -> QFrame:
        card = QFrame(objectName="PremiumCard")
        card.setStyleSheet(
            "QFrame#PremiumCard{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:16px;}"
        )
        return card

    def _section_title(self, text: str, icon_name: str | None = None) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        if icon_name:
            ico = QLabel()
            ico.setPixmap(icon(icon_name, color=NAVY, size=20).pixmap(20, 20))
            layout.addWidget(ico)
        title = QLabel(text)
        title.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:800;")
        layout.addWidget(title)
        layout.addStretch(1)
        return row

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 18)
        root.setSpacing(14)

        header_widget = QWidget()
        header_widget.setMaximumHeight(72)
        header = QHBoxLayout(header_widget)
        header.setContentsMargins(0, 0, 0, 0)
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title = QLabel("Organization")
        title.setStyleSheet(f"color:{NAVY};font-size:28px;font-weight:900;")
        subtitle = QLabel("Company privacy control for managed AI workflows.")
        subtitle.setStyleSheet(f"color:{MUTED};font-size:12px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self.role_badge = QLabel()
        self.role_badge.setStyleSheet(
            "background:#F1F5F7;color:#50697A;border:1px solid #D7E2E8;border-radius:10px;"
            "padding:6px 12px;font-size:9px;font-weight:800;"
        )
        self.plan_badge = QLabel()
        self.plan_badge.setStyleSheet(
            "background:#E8F7F7;color:#0B7F89;border:1px solid #B8E1E4;border-radius:10px;"
            "padding:6px 12px;font-size:9px;font-weight:900;"
        )
        header.addWidget(self.role_badge, alignment=Qt.AlignmentFlag.AlignTop)
        header.addWidget(self.plan_badge, alignment=Qt.AlignmentFlag.AlignTop)
        root.addWidget(header_widget)

        self.tabs_widget = QWidget()
        self.tabs = QHBoxLayout(self.tabs_widget)
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.setSpacing(4)
        self.tab_buttons: list[QPushButton] = []
        for index, label in enumerate(("Overview", "Members", "Policy", "Apps & AI", "Devices")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, i=index: self._select_tab(i))
            self.tab_buttons.append(button)
            self.tabs.addWidget(button)
        self.tabs.addStretch(1)
        root.addWidget(self.tabs_widget)

        self.tabs_line = QFrame()
        self.tabs_line.setFixedHeight(1)
        self.tabs_line.setStyleSheet("background:#DCE5EA;border:none;")
        root.addWidget(self.tabs_line)

        self.personal_panel = self._build_personal_panel()
        root.addWidget(self.personal_panel)

        self.stack = team_page.sections
        self.stack.setParent(self)
        root.addWidget(self.stack, 1)
        self.personal_tail = QWidget()
        self.personal_tail.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self.personal_tail, 1)

        old_overview = self.stack.widget(0)
        self.overview = QWidget()
        self.overview.setObjectName("PremiumOverview")
        self._build_overview(self.overview)
        self.stack.removeWidget(old_overview)
        old_overview.hide()
        self.stack.insertWidget(0, self.overview)
        self.stack.currentChanged.connect(self._sync_tab_from_stack)
        self._select_tab(0)

        self.setStyleSheet(
            "QWidget#PremiumOrganizationDashboard{background:#F7FAFC;}"
            "QWidget#PremiumOrganizationDashboard QLabel{background:transparent;border:none;}"
            "QTableWidget{background:#FFFFFF;border:none;gridline-color:#E7EDF1;color:#17384E;}"
            "QHeaderView::section{background:#FFFFFF;color:#415C70;border:none;border-bottom:1px solid #E2E9EE;"
            "padding:9px;font-size:9px;font-weight:800;}"
        )

    def _build_personal_panel(self) -> QFrame:
        card = self._card()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        card.setMaximumHeight(350)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        hero = QHBoxLayout()
        hero.setSpacing(14)
        bubble = QLabel()
        bubble.setFixedSize(46, 46)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setPixmap(icon("protect", color=TEAL, size=24).pixmap(24, 24))
        bubble.setStyleSheet("background:#E8F7F7;border-radius:23px;")
        hero.addWidget(bubble)
        text = QVBoxLayout()
        heading = QLabel("Personal workspace")
        heading.setStyleSheet(f"color:{NAVY};font-size:18px;font-weight:900;")
        note = QLabel(
            "Your private workspace for protecting documents, managing local files and connecting approved apps. "
            "No company policy is active and document content never appears in Organization."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};font-size:9px;")
        text.addWidget(heading)
        text.addWidget(note)
        hero.addLayout(text, 1)
        refresh = QPushButton("Refresh")
        join = QPushButton("Join company")
        create = QPushButton("Create Business workspace")
        for button in (refresh, join, create):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton{background:white;color:#17384E;border:1px solid #C9D7E0;border-radius:9px;padding:9px 12px;font-weight:750;}"
                "QPushButton:hover{background:#F2FAFA;border-color:#95C8CC;}"
            )
        create.setStyleSheet(
            "QPushButton{background:#0B7F89;color:white;border:none;border-radius:9px;padding:9px 12px;font-weight:800;}"
            "QPushButton:hover{background:#096D76;}"
        )
        refresh.clicked.connect(self.team_page.refresh)
        join.clicked.connect(team_page_safe(self.team_page, "_join_company"))
        create.clicked.connect(team_page_safe(self.team_page, "_create_workspace"))
        hero.addWidget(refresh)
        hero.addWidget(join)
        hero.addWidget(create)
        layout.addLayout(hero)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#E6EDF1;border:none;")
        layout.addWidget(line)

        quick = QGridLayout()
        quick.setHorizontalSpacing(12)
        quick.setVerticalSpacing(12)
        specs = (
            ("protect", "Protect a document", "Detect sensitive data and compare original with protected output.", 0),
            ("document", "Open local Library", "Review protected files saved on this device.", 1),
            ("cloud", "Manage connected Apps", "Choose which external account is active for this workspace.", getattr(self.team_page.window(), "apps_page_index", 4)),
        )
        for column, (icon_name, title, detail, page_index) in enumerate(specs):
            action = QPushButton(f"{title}\n{detail}")
            action.setIcon(icon(icon_name, color=TEAL, size=23))
            action.setIconSize(QSize(23, 23))
            action.setMinimumHeight(86)
            action.setCursor(Qt.CursorShape.PointingHandCursor)
            action.setStyleSheet(
                "QPushButton{background:#FBFDFE;color:#062B4F;border:1px solid #DCE5EA;"
                "border-radius:11px;padding:11px 13px;text-align:left;font-size:9px;font-weight:700;}"
                "QPushButton:hover{background:#F1FBFB;border-color:#9CCFD2;}"
            )
            action.clicked.connect(
                lambda _checked=False, index=page_index: self.team_page.window()._show_page(index)
            )
            quick.addWidget(action, 0, column)
        layout.addLayout(quick)

        boundary = QFrame()
        boundary.setMaximumHeight(70)
        boundary.setStyleSheet("QFrame{background:#F2FAFA;border:1px solid #CDE7E9;border-radius:11px;}")
        boundary_row = QHBoxLayout(boundary)
        boundary_row.setContentsMargins(14, 11, 14, 11)
        boundary_icon = QLabel()
        boundary_icon.setFixedSize(24, 24)
        boundary_icon.setPixmap(icon("protect", color=TEAL, size=21).pixmap(21, 21))
        boundary_row.addWidget(boundary_icon)
        boundary_text = QLabel(
            "Personal privacy boundary: originals, protected files, restore mappings and connector tokens stay on this computer."
        )
        boundary_text.setWordWrap(True)
        boundary_text.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:700;")
        boundary_row.addWidget(boundary_text, 1)
        layout.addWidget(boundary)
        return card

    def _build_overview(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(14)
        self.metric_values: dict[str, QLabel] = {}
        self.metric_details: dict[str, QLabel] = {}
        for col, (key, title, icon_name) in enumerate(
            (("seats", "Seats", "workflow"), ("members", "Members", "contact"), ("devices", "Devices", "document"), ("policy", "Policy", "protect"))
        ):
            card = self._card()
            card.setMinimumHeight(104)
            box = QHBoxLayout(card)
            box.setContentsMargins(16, 14, 16, 14)
            box.setSpacing(13)
            circle = QLabel()
            circle.setFixedSize(48, 48)
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            circle.setPixmap(icon(icon_name, color=TEAL, size=26).pixmap(26, 26))
            circle.setStyleSheet("background:#E8F7F7;border-radius:24px;")
            box.addWidget(circle)
            text = QVBoxLayout()
            text.setSpacing(1)
            title_label = QLabel(title)
            title_label.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:800;")
            value = QLabel("—")
            value.setStyleSheet(f"color:{NAVY};font-size:20px;font-weight:900;")
            detail = QLabel("")
            detail.setStyleSheet(f"color:{MUTED};font-size:9px;")
            text.addWidget(title_label)
            text.addWidget(value)
            text.addWidget(detail)
            box.addLayout(text, 1)
            metrics.addWidget(card, 0, col)
            self.metric_values[key] = value
            self.metric_details[key] = detail
        layout.addLayout(metrics)

        body = QHBoxLayout()
        body.setSpacing(14)
        quick = self._card()
        quick_layout = QVBoxLayout(quick)
        quick_layout.setContentsMargins(16, 15, 16, 15)
        quick_layout.setSpacing(10)
        quick_layout.addWidget(self._section_title("Quick actions", "workflow"))
        self.quick_invite = self._action_button("Invite member", "Add people to your organization", "contact")
        self.quick_policy = self._action_button("Edit policy", "Update protection rules", "settings")
        self.quick_publish = self._action_button("Refresh policy", "Sync latest company controls", "protect")
        self.quick_invite.clicked.connect(team_page_safe(self.team_page, "_create_invite"))
        self.quick_policy.clicked.connect(team_page_safe(self.team_page, "_edit_policy"))
        self.quick_publish.clicked.connect(self.team_page.refresh)
        quick_layout.addWidget(self.quick_invite)
        quick_layout.addWidget(self.quick_policy)
        quick_layout.addWidget(self.quick_publish)
        quick_layout.addStretch(1)
        body.addWidget(quick, 3)

        policy_card = self._card()
        policy_layout = QVBoxLayout(policy_card)
        policy_layout.setContentsMargins(16, 15, 16, 15)
        policy_layout.setSpacing(7)
        top = QHBoxLayout()
        top.addWidget(self._section_title("Protection Policy", "protect"), 1)
        self.policy_version = QLabel("—")
        self.policy_version.setStyleSheet(
            "background:#E8F7F7;color:#0B7F89;border-radius:8px;padding:4px 8px;font-size:9px;font-weight:900;"
        )
        top.addWidget(self.policy_version)
        policy_layout.addLayout(top)
        self.policy_rows = QVBoxLayout()
        self.policy_rows.setSpacing(0)
        policy_layout.addLayout(self.policy_rows)
        policy_layout.addStretch(1)
        body.addWidget(policy_card, 4)

        destinations = QVBoxLayout()
        destinations.setSpacing(10)
        ai_card = self._card()
        ai_layout = QVBoxLayout(ai_card)
        ai_layout.setContentsMargins(14, 13, 14, 13)
        ai_layout.addWidget(self._section_title("Approved AI", "workflow"))
        self.ai_row = QHBoxLayout()
        self.ai_row.setSpacing(8)
        ai_layout.addLayout(self.ai_row)
        destinations.addWidget(ai_card)
        apps_card = self._card()
        apps_layout = QVBoxLayout(apps_card)
        apps_layout.setContentsMargins(14, 13, 14, 13)
        apps_layout.addWidget(self._section_title("Approved Apps", "cloud"))
        self.apps_grid = QGridLayout()
        self.apps_grid.setHorizontalSpacing(12)
        self.apps_grid.setVerticalSpacing(8)
        apps_layout.addLayout(self.apps_grid)
        destinations.addWidget(apps_card)
        body.addLayout(destinations, 5)
        layout.addLayout(body)

        previews = QHBoxLayout()
        previews.setSpacing(14)
        self.members_preview = self._preview_table_card("Members", ["Name", "Role", "Status"])
        self.devices_preview = self._preview_table_card("Devices", ["Device", "User", "Policy", "Status"])
        previews.addWidget(self.members_preview[0], 1)
        previews.addWidget(self.devices_preview[0], 1)
        layout.addLayout(previews)

        boundary = self._card()
        row = QHBoxLayout(boundary)
        row.setContentsMargins(16, 13, 16, 13)
        shield = QLabel()
        shield.setPixmap(icon("protect", color=NAVY, size=22).pixmap(22, 22))
        row.addWidget(shield)
        text = QLabel(
            "Documents, restore mappings, and connector tokens stay local on employee devices. "
            "No document content is stored in the Organization control plane."
        )
        text.setWordWrap(True)
        text.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:700;")
        row.addWidget(text, 1)
        layout.addWidget(boundary)

    def _action_button(self, title: str, subtitle: str, icon_name: str) -> QPushButton:
        button = QPushButton(f"{title}\n{subtitle}")
        button.setIcon(icon(icon_name, color=NAVY, size=20))
        button.setIconSize(QSize(20, 20))
        button.setMinimumHeight(62)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#062B4F;border:1px solid #DCE5EA;border-radius:10px;"
            "padding:8px 12px;text-align:left;font-size:10px;font-weight:700;}"
            "QPushButton:hover{background:#F2FAFA;border-color:#9CCFD2;}"
        )
        return button

    def _preview_table_card(self, title: str, headers: list[str]) -> tuple[QFrame, QTableWidget]:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(self._section_title(title, "contact" if title == "Members" else "document"))
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setMinimumHeight(145)
        for column in range(len(headers)):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        return card, table

    def _select_tab(self, visual_index: int) -> None:
        if visual_index >= len(VISUAL_TO_STACK):
            return
        stack_index = VISUAL_TO_STACK[visual_index]
        if stack_index < self.stack.count():
            self.stack.setCurrentIndex(stack_index)
        self._style_tabs(visual_index)

    def _sync_tab_from_stack(self, stack_index: int) -> None:
        self._style_tabs(STACK_TO_VISUAL.get(stack_index, 0))

    def _style_tabs(self, selected_visual: int) -> None:
        for i, button in enumerate(self.tab_buttons):
            selected = i == selected_visual
            button.setChecked(selected)
            button.setStyleSheet(
                (
                    "QPushButton{background:transparent;color:#0B7F89;border:none;border-bottom:2px solid #0B7F89;"
                    "padding:9px 12px;font-weight:800;}"
                )
                if selected
                else
                    "QPushButton{background:transparent;color:#17384E;border:none;padding:9px 12px;font-weight:700;}"
                    "QPushButton:hover{color:#0B7F89;}"
            )

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def _policy_row(self, name: str, value: str, locked: bool) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 7, 0, 7)
        name_label = QLabel(name)
        name_label.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:700;")
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color:{MUTED};font-size:9px;")
        layout.addWidget(name_label, 1)
        layout.addWidget(value_label)
        status = QLabel("🔒" if locked else "✓")
        status.setStyleSheet(f"color:{GREEN};font-size:11px;")
        layout.addWidget(status)
        return row

    def _ai_tile(self, provider: str, label: str, allowed: bool) -> QFrame:
        tile = QFrame()
        tile.setStyleSheet("QFrame{background:#FBFDFE;border:1px solid #E0E8ED;border-radius:10px;}")
        box = QVBoxLayout(tile)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(3)
        logo = QLabel(); logo.setFixedSize(30, 30); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_loader.load(provider, lambda pix, target=logo: target.setPixmap(pix.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
        name = QLabel(label); name.setAlignment(Qt.AlignmentFlag.AlignCenter); name.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:800;")
        status = QLabel("Allowed" if allowed else "Blocked"); status.setAlignment(Qt.AlignmentFlag.AlignCenter); status.setStyleSheet(f"color:{GREEN if allowed else RED};font-size:8px;font-weight:800;")
        box.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter); box.addWidget(name); box.addWidget(status)
        return tile

    def _app_item(self, provider: str, label: str, allowed: bool) -> QWidget:
        item = QWidget(); row = QHBoxLayout(item); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(7)
        logo = QLabel(); logo.setFixedSize(22, 22)
        self.logo_loader.load(provider, lambda pix, target=logo: target.setPixmap(pix.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
        name = QLabel(label); name.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:700;")
        status = QLabel("✓" if allowed else "⊘"); status.setStyleSheet(f"color:{GREEN if allowed else RED};font-size:10px;font-weight:900;")
        row.addWidget(logo); row.addWidget(name, 1); row.addWidget(status)
        return item

    def render(self) -> None:
        state = self.team_page.state
        has_org = bool(state.organization_id)
        self.personal_panel.setVisible(not has_org)
        self.stack.setVisible(has_org)
        self.personal_tail.setVisible(not has_org)
        self.tabs_widget.setVisible(has_org)
        self.tabs_line.setVisible(has_org)
        for button in self.tab_buttons:
            button.setVisible(has_org)

        self.role_badge.setText((state.role or "Individual").upper())
        self.plan_badge.setText(state.plan.label.upper())
        if not has_org:
            return

        active_members = [r for r in self.team_page._members if str(r.get("status") or "") == "active"]
        active_devices = [r for r in self.team_page._devices if str(r.get("status") or "") == "active"]
        self.metric_values["seats"].setText(f"{len(active_members)} / {state.seat_limit}" if state.seat_limit else str(len(active_members)))
        self.metric_details["seats"].setText(f"{state.plan.label} plan")
        self.metric_values["members"].setText(str(len(active_members)))
        disabled = max(0, len(self.team_page._members) - len(active_members))
        self.metric_details["members"].setText(f"{disabled} disabled" if disabled else "All active")
        self.metric_values["devices"].setText(str(len(active_devices)))
        self.metric_details["devices"].setText("Managed endpoints")
        version = state.policy.version if state.policy else 0
        self.metric_values["policy"].setText(f"v{version}" if version else "—")
        self.metric_details["policy"].setText("Synced company policy" if version else "No active policy")
        self.policy_version.setText(f"v{version}" if version else "—")

        can_admin = state.role in {"owner", "admin"}
        self.quick_invite.setVisible(can_admin)
        self.quick_policy.setVisible(can_admin and state.policy is not None)

        self._clear_layout(self.policy_rows)
        policy = state.policy
        if policy:
            labels = {"US_SSN": "SSN", "US_BANK_NUMBER": "Bank account", "EMAIL_ADDRESS": "Email", "PERSON": "Person name", "STREET_ADDRESS": "Property address"}
            for entity in ("US_SSN", "US_BANK_NUMBER", "EMAIL_ADDRESS", "PERSON", "STREET_ADDRESS"):
                directive = policy.protection_rules.get(entity, ProtectionDirective.USER_CHOICE)
                value = {ProtectionDirective.REQUIRED_PROTECT: "Required", ProtectionDirective.DEFAULT_PROTECT: "Default protect", ProtectionDirective.USER_CHOICE: "User choice", ProtectionDirective.ALLOW: "Allowed"}[directive]
                self.policy_rows.addWidget(self._policy_row(labels[entity], value, directive is ProtectionDirective.REQUIRED_PROTECT))

        self._clear_layout(self.ai_row)
        for provider, label, key in (("chatgpt", "ChatGPT", "chatgpt"), ("claude", "Claude", "claude"), ("gemini", "Gemini", "other")):
            allowed = bool(policy and policy.allowed_ai.get(key, False)) if policy else True
            self.ai_row.addWidget(self._ai_tile(provider, label, allowed))

        self._clear_layout(self.apps_grid)
        app_specs = (("gmail", "Gmail"), ("google_drive", "Google Drive"), ("asana", "Asana"), ("clickup", "ClickUp"), ("trello", "Trello"), ("notion", "Notion"), ("monday", "monday.com"), ("jira", "Jira"))
        for index, (provider, label) in enumerate(app_specs):
            allowed = bool(policy and policy.allowed_connectors.get(provider, policy.allowed_connectors.get("*", False))) if policy else True
            self.apps_grid.addWidget(self._app_item(provider, label, allowed), index // 4, index % 4)

        members_table = self.members_preview[1]
        rows = self.team_page._members[:4]
        members_table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            members_table.setItem(r, 0, QTableWidgetItem(str(item.get("email") or item.get("user_id") or "Member")))
            members_table.setItem(r, 1, QTableWidgetItem(str(item.get("role") or "member").title()))
            members_table.setItem(r, 2, QTableWidgetItem(str(item.get("status") or "active").title()))

        devices_table = self.devices_preview[1]
        rows = self.team_page._devices[:4]
        devices_table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            devices_table.setItem(r, 0, QTableWidgetItem(str(item.get("display_name") or "Device")))
            devices_table.setItem(r, 1, QTableWidgetItem(str(item.get("email") or "Member")))
            pv = item.get("last_policy_version")
            devices_table.setItem(r, 2, QTableWidgetItem(f"v{pv}" if pv else "—"))
            devices_table.setItem(r, 3, QTableWidgetItem(str(item.get("status") or "active").title()))

        manager = state.role in {"owner", "admin", "manager"}
        self.tab_buttons[1].setVisible(manager)
        self.tab_buttons[4].setVisible(manager)


def team_page_safe(page, name: str):
    def invoke():
        method = getattr(page, name, None)
        if callable(method):
            method()
    return invoke


def apply_premium_organization_rebuild(main_window) -> OrganizationDashboardView | None:
    page = getattr(main_window, "team_page", None)
    if page is None:
        return None
    existing = getattr(page, "_privacygate_premium_dashboard", None)
    if existing is not None:
        return existing
    root = page.layout()
    if root is None:
        return None

    def hide_item(item) -> None:
        widget = item.widget()
        layout = item.layout()
        if widget is not None:
            widget.hide()
        elif layout is not None:
            for i in range(layout.count()):
                hide_item(layout.itemAt(i))

    for i in range(root.count()):
        hide_item(root.itemAt(i))

    dashboard = OrganizationDashboardView(page, page)
    root.addWidget(dashboard, 1)
    dashboard.show()
    page._privacygate_premium_dashboard = dashboard
    return dashboard
