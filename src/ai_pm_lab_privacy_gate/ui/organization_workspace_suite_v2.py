from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.domain.company_policy import PolicyEngine
from ai_pm_lab_privacy_gate.ui.organization_workspace_suite import (
    DIRECT_IMPORT_PROVIDERS,
    PROVIDERS,
    WorkspaceConsentDialog,
)
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
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


class OrganizationAppsSuiteV2(QWidget):
    """Workspace-local connector + Protect suite inside Organization.

    The dedicated ProtectionPage instance intentionally reuses PrivacyGate's real
    protection engine and Library repository.  It is a separate UI surface, not a
    duplicate protection implementation.  A connected source is materialized into
    this embedded page and the user remains inside Organization throughout the
    workflow.
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

        self.protect = ProtectionPage(main_window.service, main_window.library)
        self.protect.setObjectName("OrganizationEmbeddedProtect")
        self._configure_embedded_protect()
        self._build()

        self.team_page.state_changed.connect(lambda _state: self.render())
        self.team_page.policy_changed.connect(lambda _policy: self._sync_policy_context())
        self.render()

    # ------------------------------------------------------------------ helpers
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

    def _configure_embedded_protect(self) -> None:
        # Keep the exact Protect behavior, but label this instance as the active
        # Organization workspace and fit it inside the suite rather than navigating
        # to the global Protect page.
        title = getattr(self.protect, "_redesign_title", None)
        if title is not None:
            title.setText("Workspace Protect")
        subtitle = getattr(self.protect, "_redesign_subtitle", None)
        if subtitle is not None:
            subtitle.setText(
                "Protect documents here without leaving Organization. The active workspace policy is enforced locally."
            )

        restore_button = getattr(self.protect, "_redesign_restore_page_button", None)
        if restore_button is not None:
            restore_button.hide()

        help_button = getattr(self.protect, "_redesign_help_button", None)
        if help_button is not None:
            help_button.setMaximumWidth(170)

        # The desktop Protect view uses a tall standalone canvas.  This embedded
        # instance keeps the same two-pane preview with smaller minimums so it can
        # live comfortably beside Connected accounts.
        preview_card = getattr(self.protect, "preview_card", None)
        if preview_card is not None:
            preview_card.setMinimumHeight(620)
        preview_tabs = getattr(self.protect, "preview_tabs", None)
        if preview_tabs is not None:
            preview_tabs.setMinimumHeight(540)
        splitter = getattr(self.protect, "document_preview_splitter", None)
        if splitter is not None:
            splitter.setMinimumHeight(470)
            splitter.setSizes([520, 520])

        redesign_scroll = getattr(self.protect, "_redesign_scroll", None)
        if redesign_scroll is not None:
            content = redesign_scroll.widget()
            if content is not None and content.layout() is not None:
                content.layout().setContentsMargins(4, 6, 4, 8)

        # Apply the same two-panel invariant used by the main Protect page, but only
        # to this Organization instance.  The helper wraps instance methods, not the
        # ProtectionPage class, so the two surfaces remain independent.
        try:
            from ai_pm_lab_privacy_gate.ui.final_visual_polish import _force_two_panel_protect

            original = self.main_window.protection_page
            self.main_window.protection_page = self.protect
            try:
                _force_two_panel_protect(self.main_window)
            finally:
                self.main_window.protection_page = original
        except Exception:
            self._enforce_compare()

        # Saving from the embedded suite must refresh the same local Library.
        callback = getattr(self.main_window, "_library_changed", None)
        if callable(callback):
            self.protect.library_changed.connect(callback)

    def _enforce_compare(self) -> None:
        tabs = getattr(self.protect, "preview_tabs", None)
        if tabs is not None and tabs.count() > 1:
            tabs.setTabVisible(1, True)
            tabs.setCurrentIndex(1)
        original = getattr(self.protect, "original_document_panel", None)
        protected = getattr(self.protect, "protected_document_panel", None)
        if original is not None:
            original.show()
        if protected is not None:
            protected.show()
        splitter = getattr(self.protect, "document_preview_splitter", None)
        if splitter is not None:
            splitter.setChildrenCollapsible(False)
            splitter.setSizes([520, 520])

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

    def _active_descriptor(self):
        context = self.store.load()
        return context, context.workspaces.get(context.active_key)

    def _policy_for_active(self):
        context, descriptor = self._active_descriptor()
        if descriptor is None or descriptor.personal:
            return None
        state = self.store.cached_state(context.active_key)
        if state is None and getattr(self.team_page.state, "organization_id", "") == descriptor.organization_id:
            state = self.team_page.state
        return getattr(state, "policy", None) if state is not None else None

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

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        workspace_card = _card("OrgSuiteWorkspaceContext")
        workspace_row = QHBoxLayout(workspace_card)
        workspace_row.setContentsMargins(13, 10, 13, 10)
        workspace_row.setSpacing(11)
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(_title("Active workspace", 10))
        text.addWidget(
            _muted(
                "Personal or company suite. Switching workspace changes policy context, not your PrivacyGate account.",
                7,
            )
        )
        workspace_row.addLayout(text)
        self.workspace_combo = QComboBox()
        self.workspace_combo.setMinimumWidth(330)
        self.workspace_combo.setMinimumHeight(34)
        self.workspace_combo.currentIndexChanged.connect(self._workspace_selected)
        workspace_row.addWidget(self.workspace_combo)
        self.workspace_note = _muted("", 8)
        workspace_row.addWidget(self.workspace_note, 1)
        root.addWidget(workspace_card)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)

        accounts = _card("OrgSuiteConnectedAccounts")
        accounts.setMinimumWidth(300)
        accounts.setMaximumWidth(410)
        accounts_box = QVBoxLayout(accounts)
        accounts_box.setContentsMargins(12, 11, 12, 11)
        accounts_box.setSpacing(6)
        accounts_box.addWidget(_title("Connected accounts", 13))
        accounts_box.addWidget(
            _muted(
                "Your local accounts. Approve any account you want to reuse inside a company workspace.",
                7,
            )
        )
        self.accounts_table = QTableWidget(0, 3)
        self.accounts_table.setHorizontalHeaderLabels(
            ["Connector", "Account", "Use in workspaces"]
        )
        self.accounts_table.verticalHeader().setVisible(False)
        self.accounts_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.accounts_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.accounts_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.accounts_table.setShowGrid(False)
        self.accounts_table.setAlternatingRowColors(False)
        self.accounts_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.accounts_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.accounts_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.accounts_table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#17384E;border:none;}"
            "QTableWidget::item{padding:6px;border-bottom:1px solid #EEF2F4;font-size:8px;}"
            "QTableWidget::item:selected{background:#EAF7F7;color:#062B4F;}"
            "QHeaderView::section{background:#F8FBFC;color:#425D70;border:none;"
            "border-bottom:1px solid #DCE5EA;padding:7px;font-size:7px;font-weight:850;}"
        )
        self.accounts_table.doubleClicked.connect(lambda _index: self._manage_binding())
        accounts_box.addWidget(self.accounts_table, 1)
        self.manage_binding = _secondary("Manage workspace permissions")
        self.manage_binding.clicked.connect(self._manage_binding)
        accounts_box.addWidget(self.manage_binding)

        privacy = QFrame(objectName="OrgSuiteAccountsPrivacy")
        privacy.setStyleSheet(
            "QFrame#OrgSuiteAccountsPrivacy{background:#F2FAFA;border:1px solid #CDE7E9;border-radius:8px;}"
        )
        privacy_box = QVBoxLayout(privacy)
        privacy_box.setContentsMargins(9, 7, 9, 7)
        privacy_box.addWidget(
            _muted(
                "Admins can know an account is approved for the workspace; they do not see its documents or OAuth credentials.",
                7,
            )
        )
        accounts_box.addWidget(privacy)
        body.addWidget(accounts)

        suite = _card("OrgSuiteProtectCard")
        suite.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        suite_box = QVBoxLayout(suite)
        suite_box.setContentsMargins(10, 10, 10, 10)
        suite_box.setSpacing(8)

        import_bar = QFrame(objectName="OrgSuiteImportBar")
        import_bar.setStyleSheet(
            "QFrame#OrgSuiteImportBar{background:#F8FBFC;border:1px solid #DDE6EB;border-radius:9px;}"
        )
        import_row = QHBoxLayout(import_bar)
        import_row.setContentsMargins(10, 8, 10, 8)
        import_row.setSpacing(8)

        source_box = QVBoxLayout()
        source_box.setSpacing(2)
        source_box.addWidget(_title("Connected source", 8))
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(150)
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        source_box.addWidget(self.source_combo)
        import_row.addLayout(source_box)

        account_box = QVBoxLayout()
        account_box.setSpacing(2)
        account_box.addWidget(_title("Account", 8))
        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(220)
        self.account_combo.currentIndexChanged.connect(self._selection_changed)
        account_box.addWidget(self.account_combo)
        import_row.addLayout(account_box)

        self.policy_summary = QLabel()
        self.policy_summary.setWordWrap(True)
        self.policy_summary.setMinimumWidth(190)
        self.policy_summary.setStyleSheet(
            "background:#FFFFFF;color:#17384E;border:1px solid #DDE6EB;border-radius:8px;"
            "padding:7px;font-size:7px;font-weight:750;"
        )
        import_row.addWidget(self.policy_summary, 1)

        self.browse_button = _primary("Browse connected content")
        self.browse_button.clicked.connect(self._browse_connected)
        import_row.addWidget(self.browse_button, alignment=Qt.AlignmentFlag.AlignBottom)
        suite_box.addWidget(import_bar)

        suite_heading = QHBoxLayout()
        suite_heading.addWidget(_title("Workspace document suite", 12))
        suite_heading.addWidget(
            _muted(
                "Upload, paste, scan, review and protect here. Connected imports open in this preview and never redirect to the standalone Protect page.",
                7,
            ),
            1,
        )
        suite_box.addLayout(suite_heading)
        suite_box.addWidget(self.protect, 1)
        body.addWidget(suite)
        body.setStretchFactor(0, 2)
        body.setStretchFactor(1, 7)
        body.setSizes([340, 980])
        root.addWidget(body, 1)

        boundary = QFrame(objectName="OrgSuiteLocalBoundaryV2")
        boundary.setStyleSheet(
            "QFrame#OrgSuiteLocalBoundaryV2{background:#EDF8F4;border:1px solid #B9DECD;border-radius:9px;}"
        )
        boundary_row = QHBoxLayout(boundary)
        boundary_row.setContentsMargins(11, 7, 11, 7)
        boundary_row.addWidget(
            _muted(
                "Local-first: source contents, originals, protected copies, restore mappings and connector tokens stay on this computer.",
                8,
            ),
            1,
        )
        root.addWidget(boundary)

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
                pixmap.scaled(
                    20,
                    20,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            ),
        )
        return cell

    # ------------------------------------------------------------------ render
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
                role = descriptor.role.title() if descriptor.role else "You"
                self.workspace_combo.addItem(
                    f"{descriptor.name}  ·  {descriptor.plan.label}  ·  {role}", key
                )
            selected = self.workspace_combo.findData(context.active_key)
            self.workspace_combo.setCurrentIndex(max(0, selected))
            self.workspace_combo.blockSignals(False)

            descriptor = context.workspaces.get(context.active_key)
            if descriptor is None:
                self.workspace_note.setText("")
            elif descriptor.personal:
                self.workspace_note.setText(
                    "Personal suite • your own privacy settings and local connected accounts."
                )
            else:
                self.workspace_note.setText(
                    f"{descriptor.name} suite • company policy is enforced locally inside this page."
                )

            self.accounts_table.setRowCount(len(rows))
            for row_index, (provider, provider_label, account_id, account_label) in enumerate(rows):
                provider_item = QTableWidgetItem(provider_label)
                provider_item.setData(Qt.ItemDataRole.UserRole, provider)
                provider_item.setData(int(Qt.ItemDataRole.UserRole) + 1, account_id)
                self.accounts_table.setItem(row_index, 0, provider_item)
                self.accounts_table.setCellWidget(
                    row_index, 0, self._provider_cell(provider, provider_label)
                )
                self.accounts_table.setItem(
                    row_index, 1, QTableWidgetItem(account_label)
                )
                self.accounts_table.setItem(
                    row_index,
                    2,
                    QTableWidgetItem(
                        self._permissions_text(provider, account_id, context)
                    ),
                )
                self.accounts_table.setRowHeight(row_index, 38)

            self._rebuild_import_controls(rows)
        finally:
            self._building = False

        self._sync_policy_context()
        self._selection_changed()

    def _rebuild_import_controls(self, rows) -> None:
        current_provider = str(self.source_combo.currentData() or "")
        current_account = str(self.account_combo.currentData() or "")
        providers_present = {provider for provider, _name, _id, _account in rows}

        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for provider, label in PROVIDERS:
            if provider in providers_present:
                suffix = "" if provider in DIRECT_IMPORT_PROVIDERS else " · browse only"
                self.source_combo.addItem(label + suffix, provider)
        index = self.source_combo.findData(current_provider)
        self.source_combo.setCurrentIndex(index if index >= 0 else 0)
        self.source_combo.blockSignals(False)

        provider = str(self.source_combo.currentData() or "")
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        for row_provider, _provider_label, account_id, account_label in rows:
            if row_provider == provider:
                self.account_combo.addItem(account_label, account_id)
        account_index = self.account_combo.findData(current_account)
        self.account_combo.setCurrentIndex(account_index if account_index >= 0 else 0)
        self.account_combo.blockSignals(False)

    def _sync_policy_context(self) -> None:
        context, descriptor = self._active_descriptor()
        policy = self._policy_for_active()
        if descriptor is None:
            engine = PolicyEngine()
            text = "No workspace selected"
        elif descriptor.personal:
            engine = PolicyEngine()
            text = "Personal • no company policy"
        elif policy is None:
            engine = PolicyEngine.unavailable(
                f"{descriptor.name} policy must sync before managed protection."
            )
            text = f"{descriptor.name} • policy syncing"
        else:
            engine = PolicyEngine(policy)
            text = f"{policy.organization_name} • Policy v{policy.version}"

        setter = getattr(self.protect, "_privacygate_set_policy_engine", None)
        if callable(setter):
            setter(engine)

        title = getattr(self.protect, "_redesign_title", None)
        if title is not None:
            title.setText(
                "Personal Protect" if descriptor is not None and descriptor.personal
                else f"Protect in {descriptor.name}" if descriptor is not None
                else "Workspace Protect"
            )
        subtitle = getattr(self.protect, "_redesign_subtitle", None)
        if subtitle is not None:
            subtitle.setText(
                "Same PrivacyGate protection engine, isolated workspace context. " + text
            )
        self._selection_changed()
        QTimer.singleShot(0, self._enforce_compare)

    def _source_changed(self, _index: int) -> None:
        if self._building:
            return
        rows = self._account_rows()
        provider = str(self.source_combo.currentData() or "")
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        for row_provider, _provider_label, account_id, account_label in rows:
            if row_provider == provider:
                self.account_combo.addItem(account_label, account_id)
        self.account_combo.blockSignals(False)
        self._selection_changed()

    def _selection_changed(self, *_args) -> None:
        provider = str(self.source_combo.currentData() or "")
        account_id = str(self.account_combo.currentData() or "")
        context, descriptor = self._active_descriptor()
        policy = self._policy_for_active()

        allowed = bool(provider and account_id)
        if descriptor is None:
            allowed = False
            summary = "Choose a workspace"
        elif descriptor.personal:
            summary = "Personal workspace • connector can be used locally"
        elif policy is None:
            allowed = False
            summary = f"{descriptor.name} • policy must sync before import"
        else:
            connector_allowed = bool(
                policy.allowed_connectors.get(
                    provider, policy.allowed_connectors.get("*", False)
                )
            )
            allowed = allowed and connector_allowed
            summary = (
                f"{policy.organization_name} • Policy v{policy.version} • "
                + ("connector allowed" if connector_allowed else "connector blocked")
            )

        self.policy_summary.setText(summary)
        self.browse_button.setEnabled(allowed)

        if allowed and descriptor is not None and not descriptor.personal:
            approved = self.store.is_account_available(
                provider, account_id, context.active_key
            )
            self.browse_button.setText(
                "Browse connected content" if approved else "Approve account & browse"
            )
        else:
            self.browse_button.setText("Browse connected content")

    # ------------------------------------------------------------------ actions
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
        QTimer.singleShot(250, self.render)

    def _manage_binding(self) -> None:
        row = self.accounts_table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Select an account", "Select a connected account first."
            )
            return
        provider_item = self.accounts_table.item(row, 0)
        account_item = self.accounts_table.item(row, 1)
        if provider_item is None or account_item is None:
            return
        provider = str(provider_item.data(Qt.ItemDataRole.UserRole) or "")
        account_id = str(
            provider_item.data(int(Qt.ItemDataRole.UserRole) + 1) or ""
        )
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

    def _ensure_account_permission(
        self, provider: str, account_id: str, account_label: str
    ) -> bool:
        context, descriptor = self._active_descriptor()
        if descriptor is None:
            return False
        if descriptor.personal:
            return True
        if self.store.is_account_available(provider, account_id, context.active_key):
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
        context = self.store.load()
        return self.store.is_account_available(provider, account_id, context.active_key)

    def _workspace_ready(self) -> bool:
        context, descriptor = self._active_descriptor()
        if descriptor is None:
            return False
        if descriptor.personal:
            return True
        if self._policy_for_active() is not None:
            return True
        QMessageBox.information(
            self,
            "Workspace policy is syncing",
            f"PrivacyGate is syncing {descriptor.name}. Wait for its policy to become active, then try again.",
        )
        return False

    def _browse_connected(self) -> None:
        provider = str(self.source_combo.currentData() or "")
        account_id = str(self.account_combo.currentData() or "")
        account_label = str(self.account_combo.currentText() or "")
        provider_title = dict(PROVIDERS).get(provider, provider)
        if not provider or not account_id or not self._workspace_ready():
            return

        policy = self._policy_for_active()
        context, descriptor = self._active_descriptor()
        if descriptor is not None and not descriptor.personal and policy is not None:
            connector_allowed = bool(
                policy.allowed_connectors.get(
                    provider, policy.allowed_connectors.get("*", False)
                )
            )
            if not connector_allowed:
                QMessageBox.warning(
                    self,
                    "Blocked by company policy",
                    f"{provider_title} is not approved for {descriptor.name}.",
                )
                return

        if not self._ensure_account_permission(provider, account_id, account_label):
            if descriptor is not None and not descriptor.personal:
                QMessageBox.information(
                    self,
                    "Workspace permission required",
                    f"This account was not enabled for {descriptor.name}.",
                )
            return

        self.service = self._connected_apps_service()
        if self.service is None:
            QMessageBox.warning(
                self, provider_title, "Connected Apps service is unavailable."
            )
            return
        try:
            self.service.activate_account(provider, account_id)
        except Exception as exc:
            QMessageBox.warning(self, f"{provider_title} account", str(exc))
            return

        # Reuse the mature source browser/materializers, but point them at the
        # embedded Organization ProtectionPage for the lifetime of the modal dialog.
        # Its legacy attempt to navigate to page 0 is intercepted so the user stays
        # in Organization.
        from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish

        opener = getattr(
            connected_apps_browse_polish,
            "_privacygate_raw_open_source_browser",
            connected_apps_browse_polish._open_source_browser,
        )
        original_protect = self.main_window.protection_page
        original_show_page = self.main_window._show_page

        def stay_in_organization(index: int) -> None:
            if index == 0:
                return
            original_show_page(index)

        self.main_window.protection_page = self.protect
        self.main_window._show_page = stay_in_organization
        try:
            opener(self.main_window, provider, provider_title)
        finally:
            self.main_window._show_page = original_show_page
            self.main_window.protection_page = original_protect

        QTimer.singleShot(0, self._enforce_compare)
        QTimer.singleShot(80, self._selection_changed)


def _polish_policy_explanation(dashboard) -> None:
    """Keep Policy wording consistent with the embedded workspace suite."""
    try:
        policy_view = dashboard.stack.widget(2)
    except Exception:
        return
    replacements = {
        "The policy is operational, not just informational. The active workspace travels with the document into the existing Protect workflow.":
            "The policy is operational, not just informational. The same Protect engine runs inside the active Personal or company workspace suite.",
        "Enforcement happens in the existing Protect / Privacy Preflight path. This Organization page never receives document content, restore mappings or connector credentials.":
            "Enforcement happens locally in the workspace Protect / Privacy Preflight engine. Organization controls policy without uploading document content, restore mappings or connector credentials.",
    }
    for label in policy_view.findChildren(QLabel):
        text = label.text().strip()
        if text in replacements:
            label.setText(replacements[text])


def apply_organization_workspace_suite_v2(main_window) -> OrganizationAppsSuiteV2 | None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = (
        getattr(team_page, "_privacygate_premium_dashboard", None)
        if team_page is not None
        else None
    )
    if team_page is None or dashboard is None:
        return None

    existing = getattr(dashboard, "_organization_apps_suite_v2", None)
    if existing is not None:
        return existing
    if dashboard.stack.count() <= 4:
        return None

    old = dashboard.stack.widget(4)
    was_current = dashboard.stack.currentIndex() == 4
    view = OrganizationAppsSuiteV2(main_window, team_page, dashboard)
    dashboard.stack.removeWidget(old)
    old.hide()
    dashboard.stack.insertWidget(4, view)
    dashboard._organization_apps_suite_v2 = view
    dashboard._organization_apps_suite_v2_old = old

    if was_current:
        dashboard.stack.setCurrentIndex(4)
    _polish_policy_explanation(dashboard)
    return view
