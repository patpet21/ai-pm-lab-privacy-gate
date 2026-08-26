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

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
RED = "#B54747"
BORDER = "#DCE5EA"
SOFT = "#F7FAFC"


def _card(name: str) -> QFrame:
    frame = QFrame(objectName=name)
    frame.setStyleSheet(
        f"QFrame#{name}{{background:#FFFFFF;border:1px solid {BORDER};border-radius:12px;}}"
    )
    return frame


def _title(text: str, size: int = 14) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color:{NAVY};font-size:{size}px;font-weight:900;border:none;background:transparent;")
    return label


def _muted(text: str = "", size: int = 9) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{MUTED};font-size:{size}px;border:none;background:transparent;")
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


def _secondary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(34)
    button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:8px;"
        "padding:7px 12px;font-size:9px;font-weight:800;}"
        "QPushButton:hover{background:#F2FAFA;border-color:#96C9CD;color:#0B7180;}"
    )
    return button


def _primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(34)
    button.setStyleSheet(
        "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:8px;"
        "padding:7px 12px;font-size:9px;font-weight:850;}"
        "QPushButton:hover{background:#096D76;}"
    )
    return button


class CleanPolicyView(QWidget):
    def __init__(self, team_page, parent=None) -> None:
        super().__init__(parent)
        self.team_page = team_page
        self.rules_layout = QVBoxLayout()
        self.ai_layout = QVBoxLayout()
        self.apps_layout = QGridLayout()
        self._build()
        self.render()
        team_page.state_changed.connect(lambda _state: self.render())

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(_title("Company privacy policy", 16))
        titles.addWidget(_muted("Company rules are enforced locally before protection and AI handoff.", 8))
        header.addLayout(titles, 1)
        self.version_chip = QLabel("NO POLICY")
        self.version_chip.setStyleSheet(
            "background:#E8F7F7;color:#0B7F89;border:1px solid #B8E1E4;border-radius:9px;"
            "padding:5px 9px;font-size:8px;font-weight:900;"
        )
        header.addWidget(self.version_chip)
        self.edit_button = _primary_button("Edit policy")
        self.edit_button.clicked.connect(self.team_page._edit_policy)
        header.addWidget(self.edit_button)
        root.addLayout(header)

        columns = QHBoxLayout()
        columns.setSpacing(12)

        rules_card = _card("CleanPolicyRules")
        rules_box = QVBoxLayout(rules_card)
        rules_box.setContentsMargins(14, 12, 14, 12)
        rules_box.setSpacing(4)
        rules_box.addWidget(_title("Sensitive data rules", 12))
        rules_box.addWidget(_muted("Required rules are locked. Other rules follow the company default or employee choice.", 8))
        rules_box.addLayout(self.rules_layout)
        rules_box.addStretch(1)
        columns.addWidget(rules_card, 5)

        dest_card = _card("CleanPolicyDestinations")
        dest_box = QVBoxLayout(dest_card)
        dest_box.setContentsMargins(14, 12, 14, 12)
        dest_box.setSpacing(8)
        dest_box.addWidget(_title("AI & Apps", 12))
        dest_box.addWidget(_muted("Approved destinations for the active workspace.", 8))
        dest_box.addWidget(_title("AI", 9))
        dest_box.addLayout(self.ai_layout)
        dest_box.addSpacing(4)
        dest_box.addWidget(_title("Apps", 9))
        self.apps_layout.setHorizontalSpacing(8)
        self.apps_layout.setVerticalSpacing(6)
        dest_box.addLayout(self.apps_layout)
        dest_box.addStretch(1)
        columns.addWidget(dest_card, 4)
        root.addLayout(columns, 1)

        note = QFrame(objectName="CleanPolicyNote")
        note.setStyleSheet(
            "QFrame#CleanPolicyNote{background:#EDF8F4;border:1px solid #B9DECD;border-radius:9px;}"
        )
        row = QHBoxLayout(note)
        row.setContentsMargins(12, 9, 12, 9)
        shield = QLabel()
        shield.setPixmap(icon("protect", color=GREEN, size=18).pixmap(18, 18))
        row.addWidget(shield)
        row.addWidget(_muted("The company policy is checked again immediately before save and AI handoff. UI state alone is never the security boundary.", 8), 1)
        root.addWidget(note)

    def _rule_row(self, label: str, value: str, locked: bool) -> QWidget:
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 5, 0, 5)
        name = QLabel(label)
        name.setStyleSheet(f"color:{INK};font-size:8px;font-weight:750;border:none;background:transparent;")
        status = QLabel(value)
        status.setStyleSheet(
            ("background:#EDF8F4;color:#23824B;border:none;border-radius:7px;padding:3px 7px;font-size:7px;font-weight:850;" if locked else
             "background:#F1F5F7;color:#50697A;border:none;border-radius:7px;padding:3px 7px;font-size:7px;font-weight:800;")
        )
        mark = QLabel("🔒" if locked else "✓")
        mark.setStyleSheet(f"color:{GREEN};font-size:9px;border:none;background:transparent;")
        box.addWidget(name, 1)
        box.addWidget(status)
        box.addWidget(mark)
        return row

    def _destination_row(self, name: str, allowed: bool) -> QWidget:
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 2, 0, 2)
        label = QLabel(name)
        label.setStyleSheet(f"color:{INK};font-size:8px;font-weight:750;border:none;background:transparent;")
        status = QLabel("Allowed" if allowed else "Blocked")
        status.setStyleSheet(f"color:{GREEN if allowed else RED};font-size:8px;font-weight:850;border:none;background:transparent;")
        box.addWidget(label, 1)
        box.addWidget(status)
        return row

    def render(self) -> None:
        policy = self.team_page.state.policy
        can_admin = self.team_page.state.role in {"owner", "admin"}
        self.edit_button.setVisible(can_admin and policy is not None)
        self.version_chip.setText(f"ACTIVE • v{policy.version}" if policy else "NO POLICY")
        _clear(self.rules_layout)
        _clear(self.ai_layout)
        _clear(self.apps_layout)
        if policy is None:
            self.rules_layout.addWidget(_muted("No active company policy.", 8))
            return

        labels = {
            "CREDIT_CARD": "Credit card",
            "CUSTOMER_ID": "Customer ID",
            "EMAIL_ADDRESS": "Email address",
            "EMPLOYEE_ID": "Employee ID",
            "LOCATION": "Location",
            "MONEY_AMOUNT": "Money amount",
            "PERSON": "Person name",
            "PHONE_NUMBER": "Phone number",
            "STREET_ADDRESS": "Street address",
            "US_BANK_NUMBER": "Bank account",
            "US_ROUTING_NUMBER": "Routing number",
            "US_SSN": "Social Security Number",
        }
        directive_labels = {
            ProtectionDirective.REQUIRED_PROTECT: "Required protect",
            ProtectionDirective.DEFAULT_PROTECT: "Protect by default",
            ProtectionDirective.USER_CHOICE: "Employee choice",
            ProtectionDirective.ALLOW: "Allowed visible",
        }
        for entity, name in labels.items():
            directive = policy.protection_rules.get(entity, ProtectionDirective.USER_CHOICE)
            self.rules_layout.addWidget(
                self._rule_row(name, directive_labels[directive], directive is ProtectionDirective.REQUIRED_PROTECT)
            )

        for key, name in (("chatgpt", "ChatGPT"), ("claude", "Claude"), ("other", "Other AI")):
            self.ai_layout.addWidget(self._destination_row(name, bool(policy.allowed_ai.get(key, False))))

        app_specs = (("gmail", "Gmail"), ("google_drive", "Google Drive"), ("asana", "Asana"), ("clickup", "ClickUp"), ("trello", "Trello"), ("notion", "Notion"), ("monday", "monday.com"), ("jira", "Jira"))
        for index, (key, name) in enumerate(app_specs):
            allowed = bool(policy.allowed_connectors.get(key, policy.allowed_connectors.get("*", False)))
            item = self._destination_row(name, allowed)
            self.apps_layout.addWidget(item, index // 2, index % 2)


class CleanMembersView(QWidget):
    def __init__(self, team_page, parent=None) -> None:
        super().__init__(parent)
        self.team_page = team_page
        self._build()
        self.render()
        team_page.state_changed.connect(lambda _state: self.render())

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(_title("Members", 16))
        titles.addWidget(_muted("Manage organization access and roles. Member documents and Libraries remain private on each device.", 8))
        header.addLayout(titles, 1)
        self.invite = _primary_button("Invite member")
        self.invite.clicked.connect(self.team_page._create_invite)
        header.addWidget(self.invite)
        root.addLayout(header)

        card = _card("CleanMembersCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Role", "Status", "Joined"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#17384E;border:none;}"
            "QTableWidget::item{padding:8px;border-bottom:1px solid #EEF2F4;font-size:8px;}"
            "QTableWidget::item:selected{background:#EAF7F7;color:#062B4F;}"
            "QHeaderView::section{background:#F8FBFC;color:#425D70;border:none;border-bottom:1px solid #DCE5EA;padding:8px;font-size:8px;font-weight:850;}"
        )
        for col in range(4):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        box.addWidget(self.table, 1)
        self.empty = _muted("No organization members are available yet.", 9)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.empty)
        root.addWidget(card, 1)

        actions = QHBoxLayout()
        self.role_button = _secondary_button("Change role")
        self.toggle_button = _secondary_button("Disable / reactivate")
        self.revoke_button = _secondary_button("Revoke member")
        self.role_button.clicked.connect(self._change_role)
        self.toggle_button.clicked.connect(self._toggle)
        self.revoke_button.clicked.connect(self._revoke)
        actions.addWidget(self.role_button)
        actions.addWidget(self.toggle_button)
        actions.addWidget(self.revoke_button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.table.currentCellChanged.connect(lambda row, _col, _pr, _pc: self._sync_old_row(row))

    def _sync_old_row(self, row: int) -> None:
        old = getattr(self.team_page, "members_table", None)
        if old is not None and row >= 0 and row < old.rowCount():
            old.setCurrentCell(row, 0)

    def _change_role(self) -> None:
        self._sync_old_row(self.table.currentRow())
        self.team_page._change_member_role()

    def _toggle(self) -> None:
        self._sync_old_row(self.table.currentRow())
        self.team_page._toggle_member_status()

    def _revoke(self) -> None:
        self._sync_old_row(self.table.currentRow())
        self.team_page._revoke_member()

    def render(self) -> None:
        rows = self.team_page._members
        self.table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            values = (
                str(item.get("display_name") or item.get("email") or item.get("user_id") or "Member"),
                str(item.get("role") or "member").title(),
                str(item.get("status") or "active").title(),
                (str(item.get("created_at") or item.get("joined_at") or "")[:10] or "—"),
            )
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(value))
        self.empty.setVisible(not rows)
        admin = self.team_page.state.role in {"owner", "admin"}
        self.invite.setVisible(admin)
        for button in (self.role_button, self.toggle_button, self.revoke_button):
            button.setVisible(admin)
            button.setEnabled(bool(rows))


class CleanDevicesView(QWidget):
    def __init__(self, team_page, parent=None) -> None:
        super().__init__(parent)
        self.team_page = team_page
        self._build()
        self.render()
        team_page.state_changed.connect(lambda _state: self.render())

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(_title("Managed devices", 16))
        titles.addWidget(_muted("Organization admins can manage endpoint access and policy sync status without seeing employee documents.", 8))
        header.addLayout(titles, 1)
        root.addLayout(header)

        card = _card("CleanDevicesCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Device", "User", "Platform", "Policy", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#17384E;border:none;}"
            "QTableWidget::item{padding:8px;border-bottom:1px solid #EEF2F4;font-size:8px;}"
            "QTableWidget::item:selected{background:#EAF7F7;color:#062B4F;}"
            "QHeaderView::section{background:#F8FBFC;color:#425D70;border:none;border-bottom:1px solid #DCE5EA;padding:8px;font-size:8px;font-weight:850;}"
        )
        for col in range(5):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        box.addWidget(self.table, 1)
        self.empty = _muted("No managed devices have been registered yet.", 9)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.empty)
        root.addWidget(card, 1)

        actions = QHBoxLayout()
        self.toggle_button = _secondary_button("Disable / reactivate")
        self.revoke_button = _secondary_button("Revoke device")
        self.toggle_button.clicked.connect(self._toggle)
        self.revoke_button.clicked.connect(self._revoke)
        actions.addWidget(self.toggle_button)
        actions.addWidget(self.revoke_button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.table.currentCellChanged.connect(lambda row, _col, _pr, _pc: self._sync_old_row(row))

    def _sync_old_row(self, row: int) -> None:
        old = getattr(self.team_page, "devices_table", None)
        if old is not None and row >= 0 and row < old.rowCount():
            old.setCurrentCell(row, 0)

    def _toggle(self) -> None:
        self._sync_old_row(self.table.currentRow())
        self.team_page._toggle_device_status()

    def _revoke(self) -> None:
        self._sync_old_row(self.table.currentRow())
        self.team_page._revoke_device()

    def render(self) -> None:
        rows = self.team_page._devices
        self.table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            pv = item.get("last_policy_version")
            values = (
                str(item.get("display_name") or "Device"),
                str(item.get("email") or item.get("user_id") or "Member"),
                str(item.get("platform") or item.get("os") or "—"),
                f"v{pv}" if pv else "—",
                str(item.get("status") or "active").replace("_", " ").title(),
            )
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(value))
        self.empty.setVisible(not rows)
        admin = self.team_page.state.role in {"owner", "admin"}
        for button in (self.toggle_button, self.revoke_button):
            button.setVisible(admin)
            button.setEnabled(bool(rows))


def _replace_stack_page(dashboard, index: int, view: QWidget, attr_name: str) -> None:
    stack = dashboard.stack
    if getattr(dashboard, attr_name, None) is not None:
        return
    old = stack.widget(index)
    stack.removeWidget(old)
    old.hide()
    stack.insertWidget(index, view)
    setattr(dashboard, attr_name, view)
    setattr(dashboard, f"{attr_name}_old", old)


def _polish_organization(main_window) -> None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = getattr(team_page, "_privacygate_premium_dashboard", None) if team_page is not None else None
    if team_page is None or dashboard is None:
        return

    # The historic Organization shell is still the controller, but it must never
    # render above the premium dashboard. TeamPage._render() re-shows it after sync,
    # which caused the duplicated AI PM LAB header and duplicated tab bar.
    def hide_legacy(*_args) -> None:
        shell = getattr(team_page, "organization_shell", None)
        if shell is not None:
            shell.hide()
            shell.setMaximumHeight(0)
        individual = getattr(team_page, "individual_card", None)
        if individual is not None:
            individual.hide()
            individual.setMaximumHeight(0)

    hide_legacy()
    team_page.state_changed.connect(lambda _state: QTimer.singleShot(0, hide_legacy))

    _replace_stack_page(dashboard, 1, CleanMembersView(team_page, dashboard), "_clean_members")
    _replace_stack_page(dashboard, 2, CleanPolicyView(team_page, dashboard), "_clean_policy")
    _replace_stack_page(dashboard, 3, CleanDevicesView(team_page, dashboard), "_clean_devices")

    # Re-assert the currently selected visual tab after replacing stack pages.
    current = dashboard.stack.currentIndex()
    visual = {0: 0, 1: 1, 2: 2, 4: 3, 3: 4}.get(current, 0)
    dashboard._style_tabs(visual)


def _force_two_panel_protect(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None:
        return

    def enforce() -> None:
        # The normal Protect workspace is always a side-by-side comparison:
        # original/imported document on the left, protected result on the right.
        if hasattr(page, "_managed_preview_mode"):
            page._managed_preview_mode = "compare"
        compare = getattr(page, "_managed_compare_button", None)
        if compare is not None:
            compare.setChecked(True)
        switch = getattr(page, "_managed_preview_switch", None)
        if switch is not None:
            switch.hide()
            switch.setMaximumHeight(0)
        original = getattr(page, "original_document_panel", None)
        protected = getattr(page, "protected_document_panel", None)
        if original is not None:
            original.show()
        if protected is not None:
            protected.show()
        splitter = getattr(page, "document_preview_splitter", None)
        if splitter is not None:
            splitter.setChildrenCollapsible(False)
            splitter.setMinimumHeight(700)
            splitter.setSizes([700, 700])
        tabs = getattr(page, "preview_tabs", None)
        if tabs is not None and tabs.count() > 1:
            tabs.setTabVisible(1, True)
            tabs.setCurrentIndex(1)

    for name in ("_refresh_preview", "_update_document_comparison"):
        original = getattr(page, name, None)
        if callable(original) and not getattr(page, f"_two_panel_wrapped_{name}", False):
            def wrapped(*args, _callback=original, **kwargs):
                result = _callback(*args, **kwargs)
                QTimer.singleShot(0, enforce)
                return result
            setattr(page, name, wrapped)
            setattr(page, f"_two_panel_wrapped_{name}", True)

    for signal_owner, signal_name in (
        (getattr(page, "pdf_path", None), "textChanged"),
        (getattr(page, "text_input", None), "textChanged"),
    ):
        signal = getattr(signal_owner, signal_name, None) if signal_owner is not None else None
        if signal is not None:
            signal.connect(lambda *_args: QTimer.singleShot(0, enforce))

    team_page = getattr(main_window, "team_page", None)
    if team_page is not None:
        team_page.state_changed.connect(lambda _state: QTimer.singleShot(0, enforce))
        team_page.policy_changed.connect(lambda _policy: QTimer.singleShot(0, enforce))
    QTimer.singleShot(0, enforce)


def _polish_settings(main_window) -> None:
    settings = getattr(main_window, "settings_page", None)
    if settings is None:
        return

    # Fix the three desktop-behavior rows. A broad QFrame selector previously
    # propagated borders into the detail labels because QLabel inherits QFrame.
    for key, radio in getattr(settings, "close_radios", {}).items():
        row = radio.parentWidget()
        if isinstance(row, QFrame):
            name = f"DesktopOption_{key}"
            row.setObjectName(name)
            row.setStyleSheet(
                f"QFrame#{name}{{background:#FBFDFE;border:1px solid #E7EEF2;border-radius:10px;}}"
            )

    panel = getattr(settings, "_privacygate_plan_account_panel", None)
    if panel is not None:
        panel.setMaximumHeight(285)

    # Give the main cards more breathing room and a lighter visual hierarchy.
    for card in settings.findChildren(QFrame, "SettingsPremiumCard"):
        card.setStyleSheet(
            "QFrame#SettingsPremiumCard{background:#FFFFFF;border:1px solid #E1E8ED;border-radius:14px;}"
        )


def apply_final_visual_polish(main_window) -> None:
    if getattr(main_window, "_final_visual_polish_applied", False):
        return
    main_window._final_visual_polish_applied = True
    _force_two_panel_protect(main_window)
    _polish_organization(main_window)
    _polish_settings(main_window)
