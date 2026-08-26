from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.domain.company_policy import ProtectionDirective
from ai_pm_lab_privacy_gate.infrastructure.policy.workspace_context import WorkspaceContextStore
from ai_pm_lab_privacy_gate.ui.iconography import icon


NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
RED = "#B54747"
BORDER = "#DCE5EA"
SOFT = "#F7FAFC"

PROVIDERS = (
    ("gmail", "Gmail"),
    ("google_drive", "Google Drive"),
    ("asana", "Asana"),
    ("clickup", "ClickUp"),
    ("trello", "Trello"),
    ("notion", "Notion"),
    ("monday", "monday.com"),
    ("jira", "Jira"),
)

DIRECT_IMPORT_PROVIDERS = {"gmail", "google_drive"}
_INSTALLED = False


def _card(name: str) -> QFrame:
    frame = QFrame(objectName=name)
    frame.setStyleSheet(
        f"QFrame#{name}{{background:#FFFFFF;border:1px solid {BORDER};border-radius:12px;}}"
    )
    return frame


def _title(text: str, size: int = 14) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color:{NAVY};font-size:{size}px;font-weight:900;border:none;background:transparent;"
    )
    return label


def _muted(text: str = "", size: int = 9) -> QLabel:
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


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear(child)


def install_workspace_connector_opt_in() -> None:
    """Make connected personal accounts opt-in for managed workspaces.

    Personal remains available by definition. A Business/Enterprise workspace may
    use an account only after the user explicitly binds that local account to the
    workspace. OAuth tokens and source contents stay in the existing local vault.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    def is_account_available(
        self: WorkspaceContextStore,
        provider: str,
        account_id: str,
        workspace_key: str,
    ) -> bool:
        if workspace_key == "personal":
            return True
        context = self.load()
        explicit = context.connector_bindings.get(provider, {}).get(account_id)
        return bool(explicit is not None and workspace_key in explicit)

    WorkspaceContextStore.is_account_available = is_account_available


class WorkspaceConsentDialog(QDialog):
    def __init__(
        self,
        *,
        provider: str,
        account_id: str,
        account_label: str,
        context_store: WorkspaceContextStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.provider = provider
        self.account_id = account_id
        self.context_store = context_store
        self.setWindowTitle("Workspace permissions")
        self.resize(510, 450)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)
        root.addWidget(_title("Use this account in workspaces", 21))
        root.addWidget(
            _muted(
                f"{account_label}\n"
                "Choose the company workspaces where this connected account may be used. "
                "This grants local availability only: credentials and source contents are "
                "never copied into the Organization control plane.",
                9,
            )
        )

        context = context_store.load()
        explicit = set(
            context.connector_bindings.get(provider, {}).get(account_id, ())
        )
        has_explicit = account_id in context.connector_bindings.get(provider, {})
        self.checks: dict[str, QCheckBox] = {}

        for key, descriptor in context.workspaces.items():
            text = (
                f"{descriptor.name}  ·  {descriptor.plan.label}"
                + (f"  ·  {descriptor.role.title()}" if descriptor.role else "")
            )
            check = QCheckBox(text)
            if key == "personal":
                check.setChecked(True)
                check.setEnabled(False)
                check.setToolTip("Connected accounts are always available in Personal.")
            else:
                check.setChecked(key in explicit if has_explicit else False)
            self.checks[key] = check
            root.addWidget(check)

        note = QFrame(objectName="WorkspaceConsentNote")
        note.setStyleSheet(
            "QFrame#WorkspaceConsentNote{background:#F2FAFA;border:1px solid #CDE7E9;"
            "border-radius:10px;}"
        )
        note_row = QHBoxLayout(note)
        note_row.setContentsMargins(12, 10, 12, 10)
        shield = QLabel()
        shield.setPixmap(icon("protect", color=TEAL, size=19).pixmap(19, 19))
        note_row.addWidget(shield)
        note_row.addWidget(
            _muted(
                "A company admin can manage policy, members and devices. "
                "Document names, document contents, connector tokens and source items "
                "remain private on this device.",
                8,
            ),
            1,
        )
        root.addWidget(note)
        root.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def save(self) -> None:
        selected = [
            key for key, check in self.checks.items() if check.isChecked()
        ]
        if "personal" not in selected:
            selected.insert(0, "personal")
        self.context_store.bind_account(
            self.provider, self.account_id, selected
        )


class PolicyWorkflowView(QWidget):
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
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title_box.addWidget(_title("Company privacy policy", 24))
        title_box.addWidget(
            _muted(
                "Define what employees must protect and which AI tools and connected apps "
                "they may use in this workspace. PrivacyGate enforces these rules locally "
                "whenever a document is protected or handed to AI.",
                10,
            )
        )
        header.addLayout(title_box, 1)
        self.version_chip = QLabel("NO POLICY")
        self.version_chip.setStyleSheet(
            "background:#E8F7F7;color:#0B7F89;border:1px solid #B8E1E4;"
            "border-radius:9px;padding:6px 10px;font-size:8px;font-weight:900;"
        )
        header.addWidget(self.version_chip, alignment=Qt.AlignmentFlag.AlignTop)
        self.edit_button = _primary("Edit policy")
        self.edit_button.clicked.connect(self.team_page._edit_policy)
        header.addWidget(self.edit_button, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        flow = _card("PolicyHowItWorks")
        flow_box = QVBoxLayout(flow)
        flow_box.setContentsMargins(15, 12, 15, 12)
        flow_box.setSpacing(8)
        flow_box.addWidget(_title("How this policy is used", 12))
        flow_box.addWidget(
            _muted(
                "The policy is operational, not just informational. The active workspace "
                "travels with the document into the existing Protect workflow.",
                8,
            )
        )
        steps = QHBoxLayout()
        steps.setSpacing(8)
        step_specs = (
            ("1", "Select workspace", "Personal or one of your company teams"),
            ("2", "Open or import", "Local file or an approved connected account"),
            ("3", "Protect enforces policy", "Required fields are locked and protected"),
            ("4", "Approved AI only", "A second local scan runs before handoff"),
        )
        for number, heading, detail in step_specs:
            step = QFrame()
            step.setStyleSheet(
                "QFrame{background:#F8FBFC;border:1px solid #E0E8ED;border-radius:9px;}"
            )
            box = QHBoxLayout(step)
            box.setContentsMargins(10, 9, 10, 9)
            bubble = QLabel(number)
            bubble.setFixedSize(26, 26)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setStyleSheet(
                "background:#E8F7F7;color:#0B7F89;border-radius:13px;"
                "font-size:10px;font-weight:950;"
            )
            text = QVBoxLayout()
            text.setSpacing(1)
            head = QLabel(heading)
            head.setStyleSheet(
                f"color:{NAVY};font-size:8px;font-weight:900;border:none;"
            )
            sub = _muted(detail, 7)
            text.addWidget(head)
            text.addWidget(sub)
            box.addWidget(bubble)
            box.addLayout(text, 1)
            steps.addWidget(step, 1)
        flow_box.addLayout(steps)
        root.addWidget(flow)

        columns = QHBoxLayout()
        columns.setSpacing(12)

        rules_card = _card("PolicyWorkflowRules")
        rules_box = QVBoxLayout(rules_card)
        rules_box.setContentsMargins(14, 12, 14, 12)
        rules_box.setSpacing(4)
        rules_box.addWidget(_title("Sensitive data rules", 13))
        rules_box.addWidget(
            _muted(
                "Required rules cannot be bypassed. Default and employee-choice rules "
                "remain visible so users understand exactly what Protect will do.",
                8,
            )
        )
        rules_box.addLayout(self.rules_layout)
        rules_box.addStretch(1)
        columns.addWidget(rules_card, 5)

        destination_card = _card("PolicyWorkflowDestinations")
        destination_box = QVBoxLayout(destination_card)
        destination_box.setContentsMargins(14, 12, 14, 12)
        destination_box.setSpacing(7)
        destination_box.addWidget(_title("AI & Apps", 13))
        destination_box.addWidget(
            _muted(
                "Only approved destinations can be used while this workspace is active.",
                8,
            )
        )
        destination_box.addWidget(_title("AI", 9))
        destination_box.addLayout(self.ai_layout)
        destination_box.addSpacing(3)
        destination_box.addWidget(_title("Connected apps", 9))
        destination_box.addLayout(self.apps_layout)
        destination_box.addStretch(1)
        columns.addWidget(destination_card, 4)
        root.addLayout(columns, 1)

        boundary = QFrame(objectName="PolicyEnforcementBoundary")
        boundary.setStyleSheet(
            "QFrame#PolicyEnforcementBoundary{background:#EDF8F4;border:1px solid #B9DECD;"
            "border-radius:9px;}"
        )
        row = QHBoxLayout(boundary)
        row.setContentsMargins(12, 9, 12, 9)
        shield = QLabel()
        shield.setPixmap(icon("protect", color=GREEN, size=18).pixmap(18, 18))
        row.addWidget(shield)
        row.addWidget(
            _muted(
                "Enforcement happens in the existing Protect / Privacy Preflight path. "
                "This Organization page never receives document content, restore mappings "
                "or connector credentials.",
                8,
            ),
            1,
        )
        root.addWidget(boundary)

    def _rule_row(self, name: str, value: str, locked: bool) -> QWidget:
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 5, 0, 5)
        label = QLabel(name)
        label.setStyleSheet(
            f"color:{INK};font-size:8px;font-weight:750;border:none;"
        )
        status = QLabel(value)
        status.setStyleSheet(
            (
                "background:#EDF8F4;color:#23824B;border:none;border-radius:7px;"
                "padding:3px 7px;font-size:7px;font-weight:850;"
                if locked
                else
                "background:#F1F5F7;color:#50697A;border:none;border-radius:7px;"
                "padding:3px 7px;font-size:7px;font-weight:800;"
            )
        )
        mark = QLabel("🔒" if locked else "✓")
        mark.setStyleSheet(f"color:{GREEN};font-size:9px;border:none;")
        box.addWidget(label, 1)
        box.addWidget(status)
        box.addWidget(mark)
        return row

    def _destination_row(self, name: str, allowed: bool) -> QWidget:
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 2, 0, 2)
        label = QLabel(name)
        label.setStyleSheet(
            f"color:{INK};font-size:8px;font-weight:750;border:none;"
        )
        status = QLabel("Allowed" if allowed else "Blocked")
        status.setStyleSheet(
            f"color:{GREEN if allowed else RED};font-size:8px;font-weight:850;border:none;"
        )
        box.addWidget(label, 1)
        box.addWidget(status)
        return row

    def render(self) -> None:
        policy = self.team_page.state.policy
        can_admin = self.team_page.state.role in {"owner", "admin"}
        self.edit_button.setVisible(can_admin and policy is not None)
        self.version_chip.setText(
            f"ACTIVE • v{policy.version}" if policy else "NO POLICY"
        )
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
            directive = policy.protection_rules.get(
                entity, ProtectionDirective.USER_CHOICE
            )
            self.rules_layout.addWidget(
                self._rule_row(
                    name,
                    directive_labels[directive],
                    directive is ProtectionDirective.REQUIRED_PROTECT,
                )
            )

        for key, name in (
            ("chatgpt", "ChatGPT"),
            ("claude", "Claude"),
            ("other", "Other AI"),
        ):
            self.ai_layout.addWidget(
                self._destination_row(
                    name, bool(policy.allowed_ai.get(key, False))
                )
            )

        for index, (key, name) in enumerate(PROVIDERS):
            allowed = bool(
                policy.allowed_connectors.get(
                    key, policy.allowed_connectors.get("*", False)
                )
            )
            self.apps_layout.addWidget(
                self._destination_row(name, allowed),
                index // 2,
                index % 2,
            )


class AppsWorkspaceView(QWidget):
    def __init__(self, main_window, team_page, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.team_page = team_page
        self.store = getattr(
            team_page,
            "_privacygate_workspace_store",
            WorkspaceContextStore(
                team_page.state_store.data_dir, team_page.identity_store.secrets
            ),
        )
        self.service = self._service()
        self._building = False
        self._consent_selection: tuple[str, str, str] | None = None
        self._build()
        self.render()
        team_page.state_changed.connect(lambda _state: self.render())
        QTimer.singleShot(700, self.render)

    def _service(self):
        apps = getattr(self.main_window, "apps_hub_page", None)
        service = getattr(apps, "service", None) if apps is not None else None
        if service is not None:
            return service
        cloud = getattr(self.main_window, "cloud_automation_page", None)
        return (
            getattr(cloud, "_connected_apps_service", None)
            if cloud is not None
            else None
        )

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        header = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(3)
        text.addWidget(_title("Apps & AI", 24))
        text.addWidget(
            _muted(
                "Connect accounts once on this device, then explicitly allow each account "
                "in the Personal or company workspaces where you want to use it.",
                10,
            )
        )
        header.addLayout(text, 1)
        root.addLayout(header)

        workspace_card = _card("SuiteWorkspaceContext")
        workspace_row = QHBoxLayout(workspace_card)
        workspace_row.setContentsMargins(13, 10, 13, 10)
        workspace_row.setSpacing(10)
        label_box = QVBoxLayout()
        label_box.setSpacing(1)
        label_box.addWidget(_title("Active workspace", 10))
        label_box.addWidget(
            _muted(
                "Changing workspace changes policy context, not your PrivacyGate account.",
                7,
            )
        )
        workspace_row.addLayout(label_box)
        self.workspace_combo = QComboBox()
        self.workspace_combo.setMinimumWidth(315)
        self.workspace_combo.setMinimumHeight(34)
        self.workspace_combo.currentIndexChanged.connect(
            self._workspace_selected
        )
        workspace_row.addWidget(self.workspace_combo)
        self.workspace_note = _muted("", 8)
        workspace_row.addWidget(self.workspace_note, 1)
        root.addWidget(workspace_card)

        banner = QFrame(objectName="SuiteConnectOnce")
        banner.setStyleSheet(
            "QFrame#SuiteConnectOnce{background:#F2FAFA;border:1px solid #CDE7E9;"
            "border-radius:10px;}"
        )
        banner_row = QHBoxLayout(banner)
        banner_row.setContentsMargins(12, 9, 12, 9)
        info_icon = QLabel()
        info_icon.setPixmap(icon("cloud", color=TEAL, size=18).pixmap(18, 18))
        banner_row.addWidget(info_icon)
        banner_text = QVBoxLayout()
        banner_text.setSpacing(1)
        banner_text.addWidget(_title("Connect once. Use across workspaces.", 10))
        banner_text.addWidget(
            _muted(
                "OAuth credentials stay local. A managed workspace gets access only after "
                "you approve the binding on this device.",
                8,
            )
        )
        banner_row.addLayout(banner_text, 1)
        root.addWidget(banner)

        columns = QHBoxLayout()
        columns.setSpacing(10)

        accounts = _card("SuiteConnectedAccounts")
        accounts_box = QVBoxLayout(accounts)
        accounts_box.setContentsMargins(12, 11, 12, 11)
        accounts_box.setSpacing(6)
        accounts_box.addWidget(_title("Connected accounts", 12))
        accounts_box.addWidget(
            _muted(
                "The same local account can be approved for several workspaces.",
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
        self.accounts_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.accounts_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.accounts_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        accounts_box.addWidget(self.accounts_table, 1)
        self.manage_binding = _secondary("Manage workspace permissions")
        self.manage_binding.clicked.connect(self._manage_binding)
        accounts_box.addWidget(self.manage_binding)
        columns.addWidget(accounts, 4)

        bindings = _card("SuiteWorkspaceBindings")
        bindings_box = QVBoxLayout(bindings)
        bindings_box.setContentsMargins(12, 11, 12, 11)
        bindings_box.setSpacing(6)
        bindings_box.addWidget(_title("Workspace bindings", 12))
        bindings_box.addWidget(
            _muted(
                "Availability is explicit. Personal stays private and company access is opt-in.",
                7,
            )
        )
        self.bindings_table = QTableWidget(0, 3)
        self.bindings_table.setHorizontalHeaderLabels(
            ["Account", "Approved workspaces", "Current"]
        )
        self.bindings_table.verticalHeader().setVisible(False)
        self.bindings_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.bindings_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.bindings_table.setShowGrid(False)
        for column in range(3):
            self.bindings_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.Stretch
            )
        bindings_box.addWidget(self.bindings_table, 1)
        binding_note = QFrame(objectName="SuiteBindingBoundary")
        binding_note.setStyleSheet(
            "QFrame#SuiteBindingBoundary{background:#F8FBFC;border:1px solid #E3EAEE;"
            "border-radius:8px;}"
        )
        note_row = QHBoxLayout(binding_note)
        note_row.setContentsMargins(9, 7, 9, 7)
        note_row.addWidget(
            _muted(
                "Bindings decide where an account may be used; they never expose its documents to an admin.",
                7,
            )
        )
        bindings_box.addWidget(binding_note)
        columns.addWidget(bindings, 4)

        importer = _card("SuiteImportProtect")
        import_box = QVBoxLayout(importer)
        import_box.setContentsMargins(12, 11, 12, 11)
        import_box.setSpacing(7)
        import_box.addWidget(_title("Import into Protect", 12))
        import_box.addWidget(
            _muted(
                "Choose source, account and workspace. Then browse connected content and "
                "send the selected item into the existing Protect workflow.",
                7,
            )
        )

        import_box.addWidget(_title("Source", 8))
        self.source_combo = QComboBox()
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        import_box.addWidget(self.source_combo)

        import_box.addWidget(_title("Account", 8))
        self.account_combo = QComboBox()
        self.account_combo.currentIndexChanged.connect(
            self._import_selection_changed
        )
        import_box.addWidget(self.account_combo)

        import_box.addWidget(_title("Import to workspace", 8))
        self.target_combo = QComboBox()
        self.target_combo.currentIndexChanged.connect(
            self._import_selection_changed
        )
        import_box.addWidget(self.target_combo)

        self.consent = QCheckBox()
        self.consent.stateChanged.connect(self._import_selection_changed)
        import_box.addWidget(self.consent)

        self.policy_summary = QLabel()
        self.policy_summary.setWordWrap(True)
        self.policy_summary.setStyleSheet(
            "background:#F2FAFA;color:#17384E;border:1px solid #CDE7E9;"
            "border-radius:8px;padding:8px;font-size:8px;font-weight:750;"
        )
        import_box.addWidget(self.policy_summary)

        self.browse_button = _primary("Browse connected content")
        self.browse_button.clicked.connect(self._browse)
        import_box.addWidget(self.browse_button)

        self.import_note = _muted(
            "The secure source picker opens next. Select a file/email there and choose "
            "Use in Protect. Nothing leaves this device during import.",
            7,
        )
        import_box.addWidget(self.import_note)
        import_box.addStretch(1)
        columns.addWidget(importer, 3)

        root.addLayout(columns, 1)

        boundary = QFrame(objectName="SuiteLocalBoundary")
        boundary.setStyleSheet(
            "QFrame#SuiteLocalBoundary{background:#EDF8F4;border:1px solid #B9DECD;"
            "border-radius:9px;}"
        )
        row = QHBoxLayout(boundary)
        row.setContentsMargins(12, 8, 12, 8)
        shield = QLabel()
        shield.setPixmap(icon("protect", color=GREEN, size=18).pixmap(18, 18))
        row.addWidget(shield)
        row.addWidget(
            _muted(
                "Local-first boundary: source contents, original/protected documents, "
                "restore mappings and connector tokens remain on this computer.",
                8,
            ),
            1,
        )
        root.addWidget(boundary)

    def _account_rows(self):
        self.service = self._service()
        rows = []
        if self.service is None:
            return rows
        for provider, provider_label in PROVIDERS:
            try:
                records = tuple(
                    self.service.list_connected_accounts(provider)
                )
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
        if state is None and context.active_key == workspace_key:
            state = self.team_page.state
        return getattr(state, "policy", None) if state is not None else None

    def _allowed_for(self, workspace_key: str, provider: str) -> tuple[bool, str]:
        context = self.store.load()
        descriptor = context.workspaces.get(workspace_key)
        if descriptor is None:
            return False, "Unknown workspace"
        if descriptor.personal:
            return True, "Personal workspace • no company policy"
        policy = self._policy_for(workspace_key)
        if policy is None:
            return False, "Company policy must sync before this workspace can import"
        allowed = bool(
            policy.allowed_connectors.get(
                provider, policy.allowed_connectors.get("*", False)
            )
        )
        return (
            allowed,
            f"{policy.organization_name} • Policy v{policy.version} • "
            + ("connector allowed" if allowed else "connector blocked"),
        )

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
                    f"{descriptor.name}  ·  {descriptor.plan.label}  ·  {role}",
                    key,
                )
            index = self.workspace_combo.findData(context.active_key)
            self.workspace_combo.setCurrentIndex(max(0, index))
            self.workspace_combo.blockSignals(False)

            active = context.workspaces.get(context.active_key)
            if active is not None and active.personal:
                self.workspace_note.setText(
                    "Personal workspace • your own Protect settings and connected accounts."
                )
            elif active is not None:
                self.workspace_note.setText(
                    f"Managed by {active.name} • company policy is enforced locally."
                )
            else:
                self.workspace_note.setText("")

            self.accounts_table.setRowCount(len(rows))
            self.bindings_table.setRowCount(len(rows))
            for row_index, (
                provider,
                provider_label,
                account_id,
                account_label,
            ) in enumerate(rows):
                provider_item = QTableWidgetItem(provider_label)
                provider_item.setData(Qt.ItemDataRole.UserRole, provider)
                provider_item.setData(
                    int(Qt.ItemDataRole.UserRole) + 1, account_id
                )
                self.accounts_table.setItem(row_index, 0, provider_item)
                self.accounts_table.setItem(
                    row_index, 1, QTableWidgetItem(account_label)
                )

                explicit = context.connector_bindings.get(provider, {}).get(
                    account_id
                )
                keys = ["personal"] if explicit is None else list(explicit)
                if "personal" not in keys:
                    keys.insert(0, "personal")
                names = [
                    context.workspaces[key].name
                    for key in keys
                    if key in context.workspaces
                ]
                use_text = ", ".join(names) if names else "Personal"
                self.accounts_table.setItem(
                    row_index, 2, QTableWidgetItem(use_text)
                )

                self.bindings_table.setItem(
                    row_index,
                    0,
                    QTableWidgetItem(
                        f"{provider_label}\n{account_label}"
                    ),
                )
                self.bindings_table.setItem(
                    row_index, 1, QTableWidgetItem(use_text)
                )
                current = self.store.is_account_available(
                    provider, account_id, context.active_key
                )
                self.bindings_table.setItem(
                    row_index,
                    2,
                    QTableWidgetItem("Available" if current else "Not approved"),
                )

            self._rebuild_import_controls(rows, context)
        finally:
            self._building = False
        self._import_selection_changed()

    def _rebuild_import_controls(self, rows, context) -> None:
        current_provider = str(self.source_combo.currentData() or "")
        current_account = str(self.account_combo.currentData() or "")
        current_target = str(self.target_combo.currentData() or "")

        providers_present = {
            provider for provider, _label, _id, _account in rows
        }
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for provider, label in PROVIDERS:
            if provider in providers_present:
                suffix = "" if provider in DIRECT_IMPORT_PROVIDERS else " · browse only"
                self.source_combo.addItem(label + suffix, provider)
        provider_index = self.source_combo.findData(current_provider)
        self.source_combo.setCurrentIndex(
            provider_index if provider_index >= 0 else 0
        )
        self.source_combo.blockSignals(False)

        provider = str(self.source_combo.currentData() or "")
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        for row_provider, _provider_label, account_id, account_label in rows:
            if row_provider == provider:
                self.account_combo.addItem(account_label, account_id)
        account_index = self.account_combo.findData(current_account)
        self.account_combo.setCurrentIndex(
            account_index if account_index >= 0 else 0
        )
        self.account_combo.blockSignals(False)

        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        for key, descriptor in context.workspaces.items():
            role = descriptor.role.title() if descriptor.role else "You"
            self.target_combo.addItem(
                f"{descriptor.name}  ·  {descriptor.plan.label}  ·  {role}",
                key,
            )
        target = (
            current_target
            if current_target in context.workspaces
            else context.active_key
        )
        target_index = self.target_combo.findData(target)
        self.target_combo.setCurrentIndex(max(0, target_index))
        self.target_combo.blockSignals(False)

    def _workspace_selected(self, _index: int) -> None:
        if self._building:
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
        selector.setCurrentIndex(target)
        QTimer.singleShot(80, self.render)

    def _source_changed(self, _index: int) -> None:
        if self._building:
            return
        self.render()

    def _import_selection_changed(self, *_args) -> None:
        if self._building:
            return
        provider = str(self.source_combo.currentData() or "")
        account_id = str(self.account_combo.currentData() or "")
        workspace_key = str(self.target_combo.currentData() or "")
        context = self.store.load()
        descriptor = context.workspaces.get(workspace_key)

        if not provider or not account_id or descriptor is None:
            self.consent.hide()
            self.policy_summary.setText(
                "Connect an account to start importing."
            )
            self.browse_button.setEnabled(False)
            return

        allowed, policy_text = self._allowed_for(
            workspace_key, provider
        )
        available = self.store.is_account_available(
            provider, account_id, workspace_key
        )

        selection = (provider, account_id, workspace_key)
        if descriptor.personal:
            self.consent.hide()
            self._consent_selection = selection
        else:
            self.consent.show()
            self.consent.setText(
                f"Allow this connected account in {descriptor.name}"
            )
            if self._consent_selection != selection or available:
                self.consent.blockSignals(True)
                self.consent.setChecked(available)
                self.consent.blockSignals(False)
            self._consent_selection = selection

        direct = provider in DIRECT_IMPORT_PROVIDERS
        mode_text = (
            "Direct import into Protect is available."
            if direct
            else "Browsing is available; direct Protect import for this connector is not yet implemented."
        )
        self.policy_summary.setText(
            f"{policy_text}\n{mode_text}"
        )

        has_consent = (
            True
            if descriptor.personal
            else (available or self.consent.isChecked())
        )
        self.browse_button.setEnabled(
            bool(allowed and has_consent and provider and account_id)
        )
        self.browse_button.setText(
            "Browse connected content"
            if direct
            else "Browse connected app"
        )

    def _manage_binding(self) -> None:
        row = self.accounts_table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "Select an account",
                "Select a connected account first.",
            )
            return
        provider_item = self.accounts_table.item(row, 0)
        account_item = self.accounts_table.item(row, 1)
        if provider_item is None or account_item is None:
            return
        provider = str(
            provider_item.data(Qt.ItemDataRole.UserRole) or ""
        )
        account_id = str(
            provider_item.data(
                int(Qt.ItemDataRole.UserRole) + 1
            )
            or ""
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
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.save()
            self.render()

    def _ensure_target_workspace(self, workspace_key: str) -> bool:
        context = self.store.load()
        if context.active_key == workspace_key:
            return True
        selector = getattr(self.team_page, "workspace_selector", None)
        if selector is None:
            return False
        index = selector.findData(workspace_key)
        if index < 0:
            return False
        selector.setCurrentIndex(index)
        QApplication.processEvents()
        context = self.store.load()
        if context.active_key == workspace_key:
            return True
        descriptor = context.workspaces.get(workspace_key)
        name = descriptor.name if descriptor is not None else "workspace"
        QMessageBox.information(
            self,
            "Workspace is syncing",
            f"PrivacyGate is syncing {name} before activation. "
            "Wait for the workspace to become active, then choose Browse again.",
        )
        return False

    def _browse(self) -> None:
        provider = str(self.source_combo.currentData() or "")
        title = dict(PROVIDERS).get(provider, provider)
        account_id = str(self.account_combo.currentData() or "")
        workspace_key = str(self.target_combo.currentData() or "")
        if not provider or not account_id or not workspace_key:
            return

        context = self.store.load()
        descriptor = context.workspaces.get(workspace_key)
        if descriptor is None:
            return

        allowed, _summary = self._allowed_for(
            workspace_key, provider
        )
        if not allowed:
            QMessageBox.warning(
                self,
                "Blocked by company policy",
                f"{title} is not approved for {descriptor.name}.",
            )
            return

        if not descriptor.personal:
            available = self.store.is_account_available(
                provider, account_id, workspace_key
            )
            if not available:
                if not self.consent.isChecked():
                    QMessageBox.information(
                        self,
                        "Permission required",
                        f"Approve this account for {descriptor.name} before using it there.",
                    )
                    return
                explicit = list(
                    context.connector_bindings.get(provider, {}).get(
                        account_id, ()
                    )
                )
                if "personal" not in explicit:
                    explicit.insert(0, "personal")
                if workspace_key not in explicit:
                    explicit.append(workspace_key)
                self.store.bind_account(
                    provider, account_id, explicit
                )

        if self.service is None:
            QMessageBox.warning(
                self,
                title,
                "Connected Apps service is unavailable.",
            )
            return

        try:
            self.service.activate_account(provider, account_id)
        except Exception as exc:
            QMessageBox.warning(
                self, f"{title} account", str(exc)
            )
            return

        if not self._ensure_target_workspace(workspace_key):
            return

        from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish

        opener = getattr(
            connected_apps_browse_polish,
            "_privacygate_raw_open_source_browser",
            connected_apps_browse_polish._open_source_browser,
        )
        opener(self.main_window, provider, title)
        QTimer.singleShot(120, self.render)


def _replace_stack_page(dashboard, index: int, view: QWidget, marker: str) -> None:
    stack = dashboard.stack
    existing = getattr(dashboard, marker, None)
    if existing is not None:
        return
    old = stack.widget(index)
    stack.removeWidget(old)
    old.hide()
    stack.insertWidget(index, view)
    setattr(dashboard, marker, view)
    setattr(dashboard, f"{marker}_old", old)


def apply_organization_workspace_suite(main_window) -> None:
    """Upgrade Organization without changing ProtectionPage or its core logic."""
    team_page = getattr(main_window, "team_page", None)
    dashboard = (
        getattr(team_page, "_privacygate_premium_dashboard", None)
        if team_page is not None
        else None
    )
    if team_page is None or dashboard is None:
        return
    if getattr(main_window, "_organization_workspace_suite_applied", False):
        return
    main_window._organization_workspace_suite_applied = True

    _replace_stack_page(
        dashboard,
        2,
        PolicyWorkflowView(team_page, dashboard),
        "_workspace_suite_policy",
    )

    if dashboard.stack.count() > 4:
        _replace_stack_page(
            dashboard,
            4,
            AppsWorkspaceView(main_window, team_page, dashboard),
            "_workspace_suite_apps",
        )

    current = dashboard.stack.currentIndex()
    visual = {0: 0, 1: 1, 2: 2, 4: 3, 3: 4}.get(current, 0)
    style_tabs = getattr(dashboard, "_style_tabs", None)
    if callable(style_tabs):
        style_tabs(visual)
