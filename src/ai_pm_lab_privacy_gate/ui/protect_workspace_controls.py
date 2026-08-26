from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.organization_workspace_suite import (
    DIRECT_IMPORT_PROVIDERS,
    PROVIDERS,
    WorkspaceConsentDialog,
)

NAVY = "#062B4F"
TEAL = "#0B7F89"
MUTED = "#61798A"


def _label(text: str, size: int = 8, bold: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setStyleSheet(
        f"color:{NAVY if bold else MUTED};font-size:{size}px;"
        f"font-weight:{900 if bold else 500};border:none;background:transparent;"
    )
    return widget


def _secondary(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(34)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;"
        "border-radius:8px;padding:7px 10px;font-size:9px;font-weight:800;}"
        "QPushButton:hover{background:#F2FAFA;border-color:#96C9CD;color:#0B7180;}"
    )
    return button


def _primary(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(34)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:8px;"
        "padding:7px 11px;font-size:9px;font-weight:850;}"
        "QPushButton:hover{background:#096D76;}"
        "QPushButton:disabled{background:#B8C8CF;color:#EEF3F5;}"
    )
    return button


class ManagedProtectContextBar(QFrame):
    """Workspace/source/account controls layered onto the existing Protect UI.

    The bar exists only for users who belong to at least one Business/Enterprise
    workspace. Personal remains selectable so the visual context always matches the
    policy context that the existing ProtectionPage is actually using.
    """

    def __init__(self, main_window, team_page, parent=None) -> None:
        super().__init__(parent, objectName="ManagedProtectContextBar")
        self.main_window = main_window
        self.team_page = team_page
        self.store = team_page._privacygate_workspace_store
        self.service = self._connected_apps_service()
        self._building = False
        self._changing_workspace = False
        self.setStyleSheet(
            "QFrame#ManagedProtectContextBar{background:#F2FAFA;border:1px solid #CDE7E9;"
            "border-radius:10px;}"
        )
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
        return getattr(cloud, "_connected_apps_service", None) if cloud is not None else None

    @staticmethod
    def _managed_workspaces(context):
        return [
            (key, descriptor)
            for key, descriptor in context.workspaces.items()
            if not descriptor.personal
            and str(descriptor.plan.label).strip().lower() in {"business", "enterprise"}
        ]

    def _eligible_workspaces(self, context):
        managed_keys = {key for key, _descriptor in self._managed_workspaces(context)}
        return [
            (key, descriptor)
            for key, descriptor in context.workspaces.items()
            if descriptor.personal or key in managed_keys
        ]

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

    def _policy_for(self, workspace_key: str):
        context = self.store.load()
        descriptor = context.workspaces.get(workspace_key)
        if descriptor is None or descriptor.personal:
            return None
        state = self.store.cached_state(workspace_key)
        if state is None and getattr(self.team_page.state, "organization_id", "") == descriptor.organization_id:
            state = self.team_page.state
        return getattr(state, "policy", None) if state is not None else None

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(11, 8, 11, 8)
        root.setSpacing(5)

        head = QHBoxLayout()
        head.addWidget(_label("WORKSPACE CONTEXT", 8, True))
        head.addWidget(
            _label(
                "Personal or company context + connected account. Detection, preview and Protect behavior below stay the same.",
                7,
            ),
            1,
        )
        self.manage = _secondary("Manage team access in Organization")
        self.manage.clicked.connect(self._open_organization)
        head.addWidget(self.manage)
        root.addLayout(head)

        row = QHBoxLayout()
        row.setSpacing(7)

        workspace_box = QVBoxLayout()
        workspace_box.setSpacing(2)
        workspace_box.addWidget(_label("Workspace", 7, True))
        self.workspace_combo = QComboBox()
        self.workspace_combo.setMinimumWidth(235)
        self.workspace_combo.currentIndexChanged.connect(self._workspace_changed)
        workspace_box.addWidget(self.workspace_combo)
        row.addLayout(workspace_box)

        source_box = QVBoxLayout()
        source_box.setSpacing(2)
        source_box.addWidget(_label("Connected source", 7, True))
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(145)
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        source_box.addWidget(self.source_combo)
        row.addLayout(source_box)

        account_box = QVBoxLayout()
        account_box.setSpacing(2)
        account_box.addWidget(_label("Account", 7, True))
        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(220)
        self.account_combo.currentIndexChanged.connect(self._selection_changed)
        account_box.addWidget(self.account_combo)
        row.addLayout(account_box)

        self.policy = QLabel()
        self.policy.setWordWrap(True)
        self.policy.setMinimumWidth(190)
        self.policy.setStyleSheet(
            "background:#FFFFFF;color:#17384E;border:1px solid #DDE6EB;border-radius:8px;"
            "padding:7px;font-size:7px;font-weight:750;"
        )
        row.addWidget(self.policy, 1)

        self.browse = _primary("Browse connected content")
        self.browse.clicked.connect(self._browse_connected)
        row.addWidget(self.browse, alignment=Qt.AlignmentFlag.AlignBottom)
        root.addLayout(row)

    def render(self) -> None:
        if self._building:
            return
        self._building = True
        try:
            context = self.store.load()
            managed = self._managed_workspaces(context)
            self.setVisible(bool(managed))
            if not managed:
                return

            eligible = self._eligible_workspaces(context)
            rows = self._account_rows()
            current_workspace = str(self.workspace_combo.currentData() or context.active_key)
            eligible_keys = {key for key, _descriptor in eligible}
            if current_workspace not in eligible_keys:
                current_workspace = context.active_key if context.active_key in eligible_keys else eligible[0][0]

            self.workspace_combo.blockSignals(True)
            self.workspace_combo.clear()
            for key, descriptor in eligible:
                role = descriptor.role.title() if descriptor.role else "You"
                self.workspace_combo.addItem(
                    f"{descriptor.name}  ·  {descriptor.plan.label}  ·  {role}", key
                )
            index = self.workspace_combo.findData(current_workspace)
            self.workspace_combo.setCurrentIndex(index if index >= 0 else 0)
            self.workspace_combo.blockSignals(False)

            current_provider = str(self.source_combo.currentData() or "")
            providers_present = {provider for provider, _label, _id, _account in rows}
            self.source_combo.blockSignals(True)
            self.source_combo.clear()
            for provider, label in PROVIDERS:
                if provider in providers_present:
                    suffix = "" if provider in DIRECT_IMPORT_PROVIDERS else " · browse only"
                    self.source_combo.addItem(label + suffix, provider)
            source_index = self.source_combo.findData(current_provider)
            self.source_combo.setCurrentIndex(source_index if source_index >= 0 else 0)
            self.source_combo.blockSignals(False)
            self._rebuild_accounts(rows)
        finally:
            self._building = False
        self._selection_changed()

    def _rebuild_accounts(self, rows=None) -> None:
        rows = self._account_rows() if rows is None else rows
        provider = str(self.source_combo.currentData() or "")
        current = str(self.account_combo.currentData() or "")
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        for row_provider, _provider_label, account_id, account_label in rows:
            if row_provider == provider:
                self.account_combo.addItem(account_label, account_id)
        account_index = self.account_combo.findData(current)
        self.account_combo.setCurrentIndex(account_index if account_index >= 0 else 0)
        self.account_combo.blockSignals(False)

    def _workspace_changed(self, _index: int) -> None:
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

    def _source_changed(self, _index: int) -> None:
        if self._building:
            return
        self._rebuild_accounts()
        self._selection_changed()

    def _selection_changed(self, *_args) -> None:
        workspace_key = str(self.workspace_combo.currentData() or "")
        provider = str(self.source_combo.currentData() or "")
        account_id = str(self.account_combo.currentData() or "")
        context = self.store.load()
        descriptor = context.workspaces.get(workspace_key)
        allowed = bool(workspace_key and provider and account_id and descriptor is not None)

        if descriptor is None:
            summary = "Choose a workspace"
            allowed = False
        elif descriptor.personal:
            summary = "Personal • no company policy • local connected account"
        else:
            policy = self._policy_for(workspace_key)
            if policy is None:
                summary = f"{descriptor.name} • policy syncing"
                allowed = False
            else:
                connector_allowed = bool(
                    policy.allowed_connectors.get(provider, policy.allowed_connectors.get("*", False))
                )
                allowed = allowed and connector_allowed
                summary = (
                    f"{policy.organization_name} • Policy v{policy.version} • "
                    + ("connector allowed" if connector_allowed else "connector blocked")
                )

        self.policy.setText(summary)
        if allowed and descriptor is not None and not descriptor.personal:
            approved = self.store.is_account_available(provider, account_id, workspace_key)
            self.browse.setText("Browse connected content" if approved else "Approve account & browse")
        else:
            self.browse.setText("Browse connected content")
        self.browse.setEnabled(allowed)

    def _ensure_permission(self, provider: str, account_id: str, account_label: str, workspace_key: str) -> bool:
        context = self.store.load()
        descriptor = context.workspaces.get(workspace_key)
        if descriptor is None:
            return False
        if descriptor.personal:
            return True
        if self.store.is_account_available(provider, account_id, workspace_key):
            return True
        dialog = WorkspaceConsentDialog(
            provider=provider,
            account_id=account_id,
            account_label=account_label,
            context_store=self.store,
            parent=self,
        )
        if dialog.exec() != WorkspaceConsentDialog.DialogCode.Accepted:
            return False
        dialog.save()
        self.render()
        return self.store.is_account_available(provider, account_id, workspace_key)

    def _browse_connected(self) -> None:
        workspace_key = str(self.workspace_combo.currentData() or "")
        provider = str(self.source_combo.currentData() or "")
        account_id = str(self.account_combo.currentData() or "")
        account_label = str(self.account_combo.currentText() or "")
        if not workspace_key or not provider or not account_id:
            return
        context = self.store.load()
        descriptor = context.workspaces.get(workspace_key)
        if descriptor is None:
            return
        if not descriptor.personal:
            policy = self._policy_for(workspace_key)
            if policy is None:
                return
            connector_allowed = bool(
                policy.allowed_connectors.get(provider, policy.allowed_connectors.get("*", False))
            )
            if not connector_allowed:
                QMessageBox.warning(
                    self,
                    "Blocked by company policy",
                    f"{dict(PROVIDERS).get(provider, provider)} is not approved for {descriptor.name}.",
                )
                return
        if not self._ensure_permission(provider, account_id, account_label, workspace_key):
            return
        self.service = self._connected_apps_service()
        if self.service is None:
            QMessageBox.warning(self, "Connected Apps", "Connected Apps service is unavailable.")
            return
        try:
            self.service.activate_account(provider, account_id)
        except Exception as exc:
            QMessageBox.warning(self, "Connected account", str(exc))
            return

        from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish

        opener = getattr(
            connected_apps_browse_polish,
            "_privacygate_raw_open_source_browser",
            connected_apps_browse_polish._open_source_browser,
        )
        opener(self.main_window, provider, dict(PROVIDERS).get(provider, provider))
        QTimer.singleShot(100, self.render)

    def _open_organization(self) -> None:
        team_index = getattr(self.main_window, "team_page_index", None)
        if team_index is None:
            return
        self.main_window._show_page(int(team_index))
        dashboard = getattr(self.team_page, "_privacygate_premium_dashboard", None)
        if dashboard is not None and dashboard.stack.count() > 4:
            dashboard.stack.setCurrentIndex(4)
            style = getattr(dashboard, "_style_tabs", None)
            if callable(style):
                style(3)


def apply_managed_protect_context(main_window) -> ManagedProtectContextBar | None:
    page = getattr(main_window, "protection_page", None)
    team_page = getattr(main_window, "team_page", None)
    if page is None or team_page is None or not hasattr(team_page, "_privacygate_workspace_store"):
        return None
    existing = getattr(page, "_managed_workspace_context_bar", None)
    if existing is not None:
        return existing
    preview = getattr(page, "preview_card", None)
    preview_layout = preview.layout() if preview is not None else None
    if preview_layout is None:
        return None
    bar = ManagedProtectContextBar(main_window, team_page, preview)
    quick = getattr(page, "_protect_source_quick_bar", None)
    index = preview_layout.indexOf(quick) if quick is not None else 0
    preview_layout.insertWidget(max(0, index), bar)
    page._managed_workspace_context_bar = bar
    return bar
