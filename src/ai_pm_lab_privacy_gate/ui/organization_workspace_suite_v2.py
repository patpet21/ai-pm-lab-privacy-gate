from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.organization_workspace_suite import (
    PROVIDERS,
    WorkspaceConsentDialog,
)
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader

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


def _title(text: str, size: int = 12) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color:{NAVY};font-size:{size}px;font-weight:900;border:none;background:transparent;"
    )
    return label


def _muted(text: str = "", size: int = 8) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        f"color:{MUTED};font-size:{size}px;border:none;background:transparent;"
    )
    return label


def _primary(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(36)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:8px;"
        "padding:8px 12px;font-size:9px;font-weight:850;}"
        "QPushButton:hover{background:#096D76;}"
        "QPushButton:disabled{background:#B8C8CF;color:#EEF3F5;}"
    )
    return button


def _secondary(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(34)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;"
        "border-radius:8px;padding:7px 11px;font-size:9px;font-weight:800;}"
        "QPushButton:hover{background:#F2FAFA;border-color:#96C9CD;color:#0B7180;}"
    )
    return button


class OrganizationAppsAdminView(QWidget):
    """Organization connector governance without duplicating the Protect workspace.

    Protect stays a single user-facing surface. Organization owns team administration:
    account permission, connector/AI policy visibility, role/device/member context and
    the privacy boundary. The Protect page receives a managed-workspace selector and
    account picker separately.
    """

    def __init__(self, main_window, team_page, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.team_page = team_page
        self.store = team_page._privacygate_workspace_store
        self.logo_loader = ProviderLogoLoader(team_page.state_store.data_dir, self)
        self.service = self._connected_apps_service()
        self._building = False
        self._changing_workspace = False
        self.ai_status_labels: dict[str, QLabel] = {}
        self.app_status_labels: dict[str, QLabel] = {}
        self._build()
        self.team_page.state_changed.connect(lambda _state: self.render())
        self.team_page.policy_changed.connect(lambda _policy: self.render())
        self.render()

    def _connected_apps_service(self):
        apps_page = getattr(self.main_window, "apps_hub_page", None)
        service = getattr(apps_page, "service", None) if apps_page is not None else None
        if service is not None:
            return service
        cloud = getattr(self.main_window, "cloud_automation_page", None)
        return (
            getattr(cloud, "_connected_apps_service", None)
            if cloud is not None
            else None
        )

    def _account_rows(self):
        self.service = self._connected_apps_service()
        rows: list[tuple[str, str, str, str]] = []
        if self.service is None:
            return rows
        for provider, provider_label in PROVIDERS:
            try:
                records = tuple(self.service.list_connected_accounts(provider))
            except Exception:
                records = ()
            for record in records:
                rows.append(
                    (
                        provider,
                        provider_label,
                        str(getattr(record, "account_id", "") or ""),
                        str(
                            getattr(record, "label", "")
                            or getattr(record, "subtitle", "")
                            or provider_label
                        ),
                    )
                )
        return rows

    def _permissions_text(self, provider: str, account_id: str, context) -> str:
        explicit = context.connector_bindings.get(provider, {}).get(account_id)
        keys = ["personal"] if explicit is None else list(explicit)
        if "personal" not in keys:
            keys.insert(0, "personal")
        names = [
            context.workspaces[key].name
            for key in keys
            if key in context.workspaces
        ]
        return ", ".join(names) if names else "Personal"

    def _policy(self):
        context = self.store.load()
        descriptor = context.workspaces.get(context.active_key)
        if descriptor is None or descriptor.personal:
            return None
        cached = self.store.cached_state(context.active_key)
        if cached is None and getattr(self.team_page.state, "organization_id", "") == descriptor.organization_id:
            cached = self.team_page.state
        return getattr(cached, "policy", None) if cached is not None else None

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        workspace = _card("OrgAdminWorkspace")
        row = QHBoxLayout(workspace)
        row.setContentsMargins(13, 10, 13, 10)
        row.setSpacing(10)
        copy = QVBoxLayout()
        copy.setSpacing(1)
        copy.addWidget(_title("Active workspace", 10))
        copy.addWidget(_muted("Organization controls apply to the selected company workspace.", 7))
        row.addLayout(copy)
        self.workspace_combo = QComboBox()
        self.workspace_combo.setMinimumWidth(330)
        self.workspace_combo.setMinimumHeight(34)
        self.workspace_combo.currentIndexChanged.connect(self._workspace_selected)
        row.addWidget(self.workspace_combo)
        self.workspace_note = _muted("", 8)
        row.addWidget(self.workspace_note, 1)
        self.open_protect = _primary("Open Protect")
        self.open_protect.clicked.connect(lambda: self.main_window._show_page(0))
        row.addWidget(self.open_protect)
        root.addWidget(workspace)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)

        accounts = _card("OrgAdminAccounts")
        accounts.setMinimumWidth(430)
        accounts_box = QVBoxLayout(accounts)
        accounts_box.setContentsMargins(12, 11, 12, 11)
        accounts_box.setSpacing(6)
        accounts_box.addWidget(_title("Connected accounts", 13))
        accounts_box.addWidget(
            _muted(
                "Accounts are connected to this user/device. Company use is explicit and can be changed without exposing document contents.",
                7,
            )
        )
        self.accounts_table = QTableWidget(0, 3)
        self.accounts_table.setHorizontalHeaderLabels(["Connector", "Account", "Use in workspaces"])
        self.accounts_table.verticalHeader().setVisible(False)
        self.accounts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.accounts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.accounts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.accounts_table.setShowGrid(False)
        self.accounts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.accounts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.accounts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.accounts_table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#17384E;border:none;}"
            "QTableWidget::item{padding:6px;border-bottom:1px solid #EEF2F4;font-size:8px;}"
            "QTableWidget::item:selected{background:#EAF7F7;color:#062B4F;}"
            "QHeaderView::section{background:#F8FBFC;color:#425D70;border:none;"
            "border-bottom:1px solid #DCE5EA;padding:7px;font-size:7px;font-weight:850;}"
        )
        self.accounts_table.doubleClicked.connect(lambda _index: self._manage_binding())
        accounts_box.addWidget(self.accounts_table, 1)
        account_actions = QHBoxLayout()
        self.manage_binding = _secondary("Manage selected account permissions")
        self.manage_binding.clicked.connect(self._manage_binding)
        self.open_apps = _secondary("Connect / manage apps")
        self.open_apps.clicked.connect(self._open_apps_page)
        account_actions.addWidget(self.manage_binding)
        account_actions.addWidget(self.open_apps)
        accounts_box.addLayout(account_actions)
        note = QFrame(objectName="OrgAdminAccountPrivacy")
        note.setStyleSheet(
            "QFrame#OrgAdminAccountPrivacy{background:#F2FAFA;border:1px solid #CDE7E9;border-radius:8px;}"
        )
        note_box = QVBoxLayout(note)
        note_box.setContentsMargins(9, 7, 9, 7)
        note_box.addWidget(_muted("Admins may know that an account is approved for a workspace. They do not receive its OAuth token, file list, email list or document contents.", 7))
        accounts_box.addWidget(note)
        body.addWidget(accounts)

        controls = QWidget()
        controls_box = QVBoxLayout(controls)
        controls_box.setContentsMargins(0, 0, 0, 0)
        controls_box.setSpacing(10)

        status_card = _card("OrgAdminStatus")
        status_box = QVBoxLayout(status_card)
        status_box.setContentsMargins(13, 11, 13, 11)
        status_box.setSpacing(8)
        status_head = QHBoxLayout()
        status_head.addWidget(_title("Workspace control center", 13))
        status_head.addStretch(1)
        self.refresh = _secondary("Refresh")
        self.refresh.clicked.connect(self.team_page.refresh_silent)
        status_head.addWidget(self.refresh)
        status_box.addLayout(status_head)
        self.status_summary = _muted("", 8)
        status_box.addWidget(self.status_summary)

        stats = QHBoxLayout()
        self.policy_stat = self._stat_card("Policy", "—")
        self.members_stat = self._stat_card("Members", "—")
        self.devices_stat = self._stat_card("Devices", "—")
        self.accounts_stat = self._stat_card("Accounts approved", "—")
        for card in (self.policy_stat, self.members_stat, self.devices_stat, self.accounts_stat):
            stats.addWidget(card, 1)
        status_box.addLayout(stats)
        controls_box.addWidget(status_card)

        destinations = _card("OrgAdminDestinations")
        dest_box = QVBoxLayout(destinations)
        dest_box.setContentsMargins(13, 11, 13, 11)
        dest_box.setSpacing(7)
        dest_box.addWidget(_title("Approved AI & apps", 13))
        dest_box.addWidget(_muted("This is what Protect will allow while the active company workspace is selected.", 7))
        dest_box.addWidget(_title("AI", 9))
        ai_grid = QGridLayout()
        for index, (key, label) in enumerate((("chatgpt", "ChatGPT"), ("claude", "Claude"), ("other", "Other AI"))):
            tile, status = self._destination_tile(label)
            self.ai_status_labels[key] = status
            ai_grid.addWidget(tile, 0, index)
        dest_box.addLayout(ai_grid)
        dest_box.addWidget(_title("Connected apps", 9))
        apps_grid = QGridLayout()
        for index, (provider, label) in enumerate(PROVIDERS):
            tile, status = self._app_tile(provider, label)
            self.app_status_labels[provider] = status
            apps_grid.addWidget(tile, index // 4, index % 4)
        dest_box.addLayout(apps_grid)
        controls_box.addWidget(destinations, 1)

        workflow = _card("OrgAdminWorkflow")
        workflow_box = QHBoxLayout(workflow)
        workflow_box.setContentsMargins(13, 10, 13, 10)
        workflow_box.setSpacing(12)
        workflow_copy = QVBoxLayout()
        workflow_copy.setSpacing(2)
        workflow_copy.addWidget(_title("Where document work happens", 11))
        workflow_copy.addWidget(_muted("Protect is the single document workspace. Team members choose the company workspace, source and connected account there; Organization remains the place for permissions, policy and team administration.", 8))
        workflow_box.addLayout(workflow_copy, 1)
        button = _primary("Go to Protect")
        button.clicked.connect(lambda: self.main_window._show_page(0))
        workflow_box.addWidget(button)
        controls_box.addWidget(workflow)

        body.addWidget(controls)
        body.setStretchFactor(0, 4)
        body.setStretchFactor(1, 7)
        body.setSizes([500, 840])
        root.addWidget(body, 1)

        boundary = QFrame(objectName="OrgAdminBoundary")
        boundary.setStyleSheet(
            "QFrame#OrgAdminBoundary{background:#EDF8F4;border:1px solid #B9DECD;border-radius:9px;}"
        )
        boundary_row = QHBoxLayout(boundary)
        boundary_row.setContentsMargins(11, 7, 11, 7)
        boundary_row.addWidget(_muted("Local-first boundary: Organization controls policy and access; source content, originals, protected copies, restore mappings and connector tokens stay on this computer.", 8), 1)
        root.addWidget(boundary)

    def _stat_card(self, title: str, value: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame{background:#F8FBFC;border:1px solid #E2E9ED;border-radius:9px;}")
        box = QVBoxLayout(card)
        box.setContentsMargins(10, 8, 10, 8)
        label = _muted(title, 7)
        number = QLabel(value)
        number.setProperty("statValue", True)
        number.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:950;border:none;background:transparent;")
        box.addWidget(label)
        box.addWidget(number)
        card._stat_value = number
        return card

    def _destination_tile(self, label: str) -> tuple[QFrame, QLabel]:
        tile = QFrame()
        tile.setStyleSheet("QFrame{background:#F8FBFC;border:1px solid #E2E9ED;border-radius:9px;}")
        box = QVBoxLayout(tile)
        box.setContentsMargins(9, 8, 9, 8)
        box.addWidget(_title(label, 9))
        status = QLabel("—")
        status.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:850;border:none;")
        box.addWidget(status)
        return tile, status

    def _app_tile(self, provider: str, label: str) -> tuple[QFrame, QLabel]:
        tile = QFrame()
        tile.setStyleSheet("QFrame{background:#FFFFFF;border:none;}")
        row = QHBoxLayout(tile)
        row.setContentsMargins(2, 3, 2, 3)
        row.setSpacing(6)
        logo = QLabel()
        logo.setFixedSize(22, 22)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name = QLabel(label)
        name.setStyleSheet(f"color:{INK};font-size:8px;font-weight:800;border:none;")
        status = QLabel("—")
        status.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:850;border:none;")
        row.addWidget(logo)
        row.addWidget(name, 1)
        row.addWidget(status)
        self.logo_loader.load(
            provider,
            lambda pixmap, target=logo: target.setPixmap(
                pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            ),
        )
        return tile, status

    def _provider_cell(self, provider: str, provider_label: str) -> QWidget:
        cell = QWidget()
        row = QHBoxLayout(cell)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(6)
        logo = QLabel()
        logo.setFixedSize(22, 22)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(provider_label)
        label.setStyleSheet(f"color:{INK};font-size:8px;font-weight:800;")
        row.addWidget(logo)
        row.addWidget(label)
        self.logo_loader.load(
            provider,
            lambda pixmap, target=logo: target.setPixmap(
                pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            ),
        )
        return cell

    def render(self) -> None:
        if self._building:
            return
        self._building = True
        try:
            context = self.store.load()
            rows = self._account_rows()
            self.workspace_combo.blockSignals(True)
            self.workspace_combo.clear()
            for key, descriptor in context.workspaces.items():
                if descriptor.personal:
                    continue
                role = descriptor.role.title() if descriptor.role else "Member"
                self.workspace_combo.addItem(f"{descriptor.name}  ·  {descriptor.plan.label}  ·  {role}", key)
            selected = self.workspace_combo.findData(context.active_key)
            if selected < 0 and self.workspace_combo.count():
                selected = 0
            self.workspace_combo.setCurrentIndex(selected)
            self.workspace_combo.blockSignals(False)

            active_key = str(self.workspace_combo.currentData() or context.active_key)
            descriptor = context.workspaces.get(active_key)
            if descriptor is not None:
                self.workspace_note.setText(f"{descriptor.name} • {descriptor.plan.label} • {descriptor.role.title() if descriptor.role else 'Member'}")
            else:
                self.workspace_note.setText("No company workspace available")

            self.accounts_table.setRowCount(len(rows))
            approved_count = 0
            for row_index, (provider, provider_label, account_id, account_label) in enumerate(rows):
                item = QTableWidgetItem(provider_label)
                item.setData(Qt.ItemDataRole.UserRole, provider)
                item.setData(int(Qt.ItemDataRole.UserRole) + 1, account_id)
                self.accounts_table.setItem(row_index, 0, item)
                self.accounts_table.setCellWidget(row_index, 0, self._provider_cell(provider, provider_label))
                self.accounts_table.setItem(row_index, 1, QTableWidgetItem(account_label))
                self.accounts_table.setItem(row_index, 2, QTableWidgetItem(self._permissions_text(provider, account_id, context)))
                self.accounts_table.setRowHeight(row_index, 38)
                if active_key and self.store.is_account_available(provider, account_id, active_key):
                    approved_count += 1

            policy = self._policy()
            role = getattr(self.team_page.state, "role", "member") or "member"
            if descriptor is None:
                self.status_summary.setText("No company workspace selected.")
            elif policy is None:
                self.status_summary.setText(f"{descriptor.name} is selected. Company policy is syncing or unavailable; managed connector use remains blocked until policy is available.")
            else:
                self.status_summary.setText(f"{policy.organization_name} policy is active locally. Required protection and approved destinations are enforced in Protect and Privacy Preflight.")

            self.policy_stat._stat_value.setText(f"v{policy.version}" if policy else "Syncing")
            self.members_stat._stat_value.setText(str(len(getattr(self.team_page, "_members", ()) or ())))
            self.devices_stat._stat_value.setText(str(len(getattr(self.team_page, "_devices", ()) or ())))
            self.accounts_stat._stat_value.setText(str(approved_count))

            for key, status in self.ai_status_labels.items():
                allowed = bool(policy and policy.allowed_ai.get(key, False)) if policy else False
                status.setText("Allowed" if allowed else "Blocked")
                status.setStyleSheet(f"color:{GREEN if allowed else RED};font-size:8px;font-weight:850;border:none;")
            for provider, status in self.app_status_labels.items():
                allowed = bool(policy and policy.allowed_connectors.get(provider, policy.allowed_connectors.get("*", False))) if policy else False
                status.setText("Allowed" if allowed else "Blocked")
                status.setStyleSheet(f"color:{GREEN if allowed else RED};font-size:8px;font-weight:850;border:none;")

            can_manage = role in {"owner", "admin", "manager"}
            self.manage_binding.setEnabled(bool(rows))
            self.refresh.setEnabled(True)
            self.open_protect.setEnabled(descriptor is not None)
            if not can_manage:
                self.refresh.setToolTip("Workspace membership is read-only for your role; policy remains enforced.")
        finally:
            self._building = False

    def _workspace_selected(self, _index: int) -> None:
        if self._building or self._changing_workspace:
            return
        key = str(self.workspace_combo.currentData() or "")
        if not key:
            return
        selector = getattr(self.team_page, "workspace_selector", None)
        if selector is None:
            return
        target = selector.findData(key)
        if target < 0:
            return
        self._changing_workspace = True
        try:
            selector.setCurrentIndex(target)
            QApplication.processEvents()
        finally:
            self._changing_workspace = False
        QTimer.singleShot(220, self.render)

    def _manage_binding(self) -> None:
        row = self.accounts_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select an account", "Select a connected account first.")
            return
        provider_item = self.accounts_table.item(row, 0)
        account_item = self.accounts_table.item(row, 1)
        if provider_item is None or account_item is None:
            return
        provider = str(provider_item.data(Qt.ItemDataRole.UserRole) or "")
        account_id = str(provider_item.data(int(Qt.ItemDataRole.UserRole) + 1) or "")
        if not provider or not account_id:
            return
        dialog = WorkspaceConsentDialog(
            provider=provider,
            account_id=account_id,
            account_label=account_item.text(),
            context_store=self.store,
            parent=self,
        )
        if dialog.exec() == WorkspaceConsentDialog.DialogCode.Accepted:
            dialog.save()
            self.render()

    def _open_apps_page(self) -> None:
        index = getattr(self.main_window, "apps_page_index", None)
        if index is not None:
            self.main_window._show_page(int(index))
            return
        apps = getattr(self.main_window, "apps_hub_page", None)
        if apps is not None:
            page_index = self.main_window.pages.indexOf(apps)
            if page_index >= 0:
                self.main_window._show_page(page_index)


def _polish_policy_explanation(dashboard) -> None:
    try:
        policy_view = dashboard.stack.widget(2)
    except Exception:
        return
    replacements = {
        "The policy is operational, not just informational. The same Protect engine runs inside the active Personal or company workspace suite.":
            "The policy is operational, not just informational. Select the company workspace in Protect and these rules are enforced locally there.",
        "Enforcement happens locally in the workspace Protect / Privacy Preflight engine. Organization controls policy without uploading document content, restore mappings or connector credentials.":
            "Enforcement happens locally in Protect / Privacy Preflight. Organization controls policy and account permissions without receiving document content, restore mappings or connector credentials.",
    }
    for label in policy_view.findChildren(QLabel):
        text = label.text().strip()
        if text in replacements:
            label.setText(replacements[text])


def apply_organization_workspace_suite_v2(main_window) -> OrganizationAppsAdminView | None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = getattr(team_page, "_privacygate_premium_dashboard", None) if team_page is not None else None
    if team_page is None or dashboard is None or dashboard.stack.count() <= 4:
        return None
    existing = getattr(dashboard, "_organization_apps_suite_v2", None)
    if existing is not None:
        return existing
    old = dashboard.stack.widget(4)
    was_current = dashboard.stack.currentIndex() == 4
    view = OrganizationAppsAdminView(main_window, team_page, dashboard)
    dashboard.stack.removeWidget(old)
    old.hide()
    dashboard.stack.insertWidget(4, view)
    dashboard._organization_apps_suite_v2 = view
    dashboard._organization_apps_suite_v2_old = old
    if was_current:
        dashboard.stack.setCurrentIndex(4)
    _polish_policy_explanation(dashboard)
    return view
