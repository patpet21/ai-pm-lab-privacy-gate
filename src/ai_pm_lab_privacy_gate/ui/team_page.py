from __future__ import annotations

from dataclasses import replace
import hashlib

from PySide6.QtCore import QThreadPool, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.domain.company_policy import (
    CompanyPolicy,
    ProtectionDirective,
)
from ai_pm_lab_privacy_gate.domain.plans import PlanCode
from ai_pm_lab_privacy_gate.infrastructure.auth.supabase_account import (
    AccountSession,
    SupabaseAccountClient,
)
from ai_pm_lab_privacy_gate.infrastructure.mcp.identity import ConnectionIdentityStore
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import (
    PolicyCacheError,
    SecureTeamStateStore,
    TeamState,
)
from ai_pm_lab_privacy_gate.infrastructure.policy.supabase_team import (
    SupabaseTeamClient,
    TeamServiceError,
)
from ai_pm_lab_privacy_gate.ui.organization_admin import (
    set_device_status,
    set_member_role,
    set_member_status,
)
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


NAVY = "#062B4F"
TEAL = "#0B7180"
GREEN = "#23824B"
RED = "#A23A3A"
MUTED = "#61798A"
BORDER = "#DCE5EA"
SOFT = "#F7FAFC"

_RULE_LABELS = {
    "US_SSN": "Social Security Number",
    "US_BANK_NUMBER": "Bank account",
    "US_ROUTING_NUMBER": "Routing number",
    "CREDIT_CARD": "Credit card",
    "EMAIL_ADDRESS": "Email address",
    "PHONE_NUMBER": "Phone number",
    "PERSON": "Person name",
    "STREET_ADDRESS": "Street address",
    "LOCATION": "Location",
    "MONEY_AMOUNT": "Money amount",
    "CUSTOMER_ID": "Customer ID",
    "EMPLOYEE_ID": "Employee ID",
}

_CONNECTORS = (
    ("gmail", "Gmail"),
    ("google_drive", "Google Drive"),
    ("clickup", "ClickUp"),
    ("asana", "Asana"),
    ("trello", "Trello"),
    ("notion", "Notion"),
    ("monday", "monday.com"),
    ("jira", "Jira"),
)

_OWNER_ENTERPRISE_EMAILS = {"peter@propertydex.xyz"}


def _account_entitlement(state: TeamState, email: str) -> TeamState:
    """Apply the product-owner entitlement without changing customer plans."""
    if email.strip().lower() in _OWNER_ENTERPRISE_EMAILS:
        return replace(state, plan=PlanCode.ENTERPRISE, entitlement_status="active")
    return state


def _card() -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame{{background:#FFFFFF;border:1px solid {BORDER};border-radius:12px;}}"
    )
    return frame


def _status_chip(text: str, *, tone: str = "teal") -> QLabel:
    palette = {
        "teal": ("#E8F6F6", TEAL, "#B8E1E4"),
        "green": ("#EDF8F4", GREEN, "#B9DECD"),
        "red": ("#FDECEC", RED, "#F1C1C1"),
        "neutral": ("#F1F5F7", MUTED, BORDER),
    }
    bg, fg, border = palette.get(tone, palette["neutral"])
    label = QLabel(text)
    label.setStyleSheet(
        f"background:{bg};color:{fg};border:1px solid {border};"
        "border-radius:9px;padding:5px 9px;font-size:9px;font-weight:900;"
    )
    return label


def _metric_card(title: str) -> tuple[QFrame, QLabel, QLabel]:
    card = _card()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 11, 14, 11)
    layout.setSpacing(3)
    label = QLabel(title.upper())
    label.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:900;")
    value = QLabel("—")
    value.setStyleSheet(f"color:{NAVY};font-size:20px;font-weight:950;")
    detail = QLabel("")
    detail.setStyleSheet(f"color:{MUTED};font-size:8px;")
    detail.setWordWrap(True)
    layout.addWidget(label)
    layout.addWidget(value)
    layout.addWidget(detail)
    return card, value, detail


def _directive_label(directive: ProtectionDirective) -> str:
    return {
        ProtectionDirective.REQUIRED_PROTECT: "Required protect",
        ProtectionDirective.DEFAULT_PROTECT: "Protect by default",
        ProtectionDirective.USER_CHOICE: "Employee choice",
        ProtectionDirective.ALLOW: "Allowed visible",
    }[directive]


class PolicyEditorDialog(QDialog):
    def __init__(self, policy: CompanyPolicy, parent=None) -> None:
        super().__init__(parent)
        self.policy = policy
        self.setWindowTitle("Company privacy policy")
        self.resize(800, 700)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel(f"{policy.organization_name} — Company Policy")
        title.setStyleSheet(f"font-size:20px;font-weight:900;color:{NAVY};")
        note = QLabel(
            "These rules are distributed to managed devices. Documents, restore mappings "
            "and connector tokens remain on each employee's computer."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};")
        root.addWidget(title)
        root.addWidget(note)

        ai_box = _card()
        ai_layout = QHBoxLayout(ai_box)
        ai_layout.setContentsMargins(14, 11, 14, 11)
        ai_layout.addWidget(QLabel("Allowed AI"))
        self.ai_checks: dict[str, QCheckBox] = {}
        for key, label in (
            ("chatgpt", "ChatGPT"),
            ("claude", "Claude"),
            ("other", "Other AI"),
        ):
            check = QCheckBox(label)
            check.setChecked(bool(policy.allowed_ai.get(key, False)))
            self.ai_checks[key] = check
            ai_layout.addWidget(check)
        ai_layout.addStretch(1)
        root.addWidget(ai_box)

        apps_box = _card()
        apps_layout = QGridLayout(apps_box)
        apps_layout.setContentsMargins(14, 11, 14, 11)
        apps_layout.addWidget(QLabel("Allowed Apps"), 0, 0, 1, 4)
        self.connector_checks: dict[str, QCheckBox] = {}
        for index, (key, label) in enumerate(_CONNECTORS):
            check = QCheckBox(label)
            check.setChecked(bool(policy.allowed_connectors.get(key, False)))
            self.connector_checks[key] = check
            apps_layout.addWidget(check, 1 + index // 4, index % 4)
        root.addWidget(apps_box)

        root.addWidget(QLabel("Protection rules"))
        self.rules_table = QTableWidget(len(_RULE_LABELS), 2)
        self.rules_table.setHorizontalHeaderLabels(["Sensitive data", "Company rule"])
        self.rules_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.rules_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.rule_combos: dict[str, QComboBox] = {}
        for row, (entity_type, label) in enumerate(_RULE_LABELS.items()):
            item = QTableWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entity_type)
            item.setToolTip(entity_type)
            self.rules_table.setItem(row, 0, item)
            combo = QComboBox()
            for directive, directive_label in (
                (ProtectionDirective.REQUIRED_PROTECT, "Required protect 🔒"),
                (ProtectionDirective.DEFAULT_PROTECT, "Protect by default"),
                (ProtectionDirective.USER_CHOICE, "Employee choice"),
                (ProtectionDirective.ALLOW, "Allow visible"),
            ):
                combo.addItem(directive_label, directive.value)
            current = policy.protection_rules.get(
                entity_type, ProtectionDirective.USER_CHOICE
            )
            combo.setCurrentIndex(max(0, combo.findData(current.value)))
            self.rule_combos[entity_type] = combo
            self.rules_table.setCellWidget(row, 1, combo)
        root.addWidget(self.rules_table, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def updated_policy(self) -> CompanyPolicy:
        return replace(
            self.policy,
            allowed_ai={
                **self.policy.allowed_ai,
                **{key: check.isChecked() for key, check in self.ai_checks.items()},
            },
            allowed_connectors={
                **self.policy.allowed_connectors,
                **{
                    key: check.isChecked()
                    for key, check in self.connector_checks.items()
                },
            },
            protection_rules={
                key: ProtectionDirective(str(combo.currentData()))
                for key, combo in self.rule_combos.items()
            },
        )


class TeamPage(QWidget):
    """Role-aware Organization workspace.

    The historic class name is retained for compatibility with existing runtime
    wiring. Business/Enterprise users see an operational organization dashboard;
    Basic/Pro users see only enrollment controls. No document metadata is shown.
    """

    policy_changed = Signal(object)
    state_changed = Signal(object)
    open_account = Signal()

    def __init__(
        self,
        data_dir,
        identity_store: ConnectionIdentityStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.identity_store = identity_store
        self.account_client = SupabaseAccountClient(identity_store)
        self.team_client = SupabaseTeamClient(identity_store)
        self.state_store = SecureTeamStateStore(data_dir, identity_store.secrets)
        self.thread_pool = QThreadPool.globalInstance()
        self._active_worker: FunctionWorker | None = None
        self._members: list[dict[str, object]] = []
        self._devices: list[dict[str, object]] = []
        self._cache_error = ""

        try:
            self.state = self.state_store.load()
        except PolicyCacheError as error:
            self.state = TeamState()
            self._cache_error = str(error)
        self.state = _account_entitlement(
            self.state, self.account_client.current_email or ""
        )

        self._build_ui()
        self._render()
        QTimer.singleShot(900, self.refresh_silent)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Organization")
        title.setStyleSheet(f"color:{NAVY};font-size:27px;font-weight:950;")
        subtitle = QLabel(
            "Manage company privacy policy, members and managed devices. "
            "Employee documents remain local and are never listed here."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        self.plan_badge = _status_chip("BASIC")
        self.role_badge = _status_chip("INDIVIDUAL", tone="neutral")
        header.addWidget(self.role_badge, alignment=Qt.AlignmentFlag.AlignTop)
        header.addWidget(self.plan_badge, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.alert = QLabel()
        self.alert.setWordWrap(True)
        self.alert.setVisible(False)
        root.addWidget(self.alert)

        self.individual_card = self._build_individual_card()
        root.addWidget(self.individual_card)

        self.organization_shell = QWidget()
        shell_layout = QVBoxLayout(self.organization_shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(10)

        shell_layout.addWidget(self._build_org_header())

        nav = QHBoxLayout()
        nav.setSpacing(6)
        self.section_buttons: list[QPushButton] = []
        self.sections = QStackedWidget()
        for index, (label, page) in enumerate(
            (
                ("Overview", self._build_overview()),
                ("Members", self._build_members()),
                ("Policy", self._build_policy()),
                ("Devices", self._build_devices()),
            )
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(
                lambda _checked=False, page_index=index: self._show_section(page_index)
            )
            self.section_buttons.append(button)
            nav.addWidget(button)
            self.sections.addWidget(page)
        nav.addStretch(1)
        shell_layout.addLayout(nav)
        shell_layout.addWidget(self.sections, 1)
        root.addWidget(self.organization_shell, 1)

        self.section_buttons[0].setChecked(True)
        self._show_section(0)

    def _build_individual_card(self) -> QFrame:
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(9)

        top = QHBoxLayout()
        title = QLabel("Individual PrivacyGate")
        title.setStyleSheet(f"color:{NAVY};font-size:18px;font-weight:900;")
        self.individual_sync = QLabel("Local-first")
        self.individual_sync.setStyleSheet(f"color:{MUTED};")
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.individual_sync)
        layout.addLayout(top)

        note = QLabel(
            "Basic and Pro are individual plans. Join a company to receive its privacy "
            "policy, or create a Business workspace if you administer an organization."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};")
        layout.addWidget(note)

        actions = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh", objectName="Secondary")
        self.join_button = QPushButton("Join company", objectName="Secondary")
        self.create_button = QPushButton(
            "Create Business workspace", objectName="Primary"
        )
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.join_button)
        actions.addWidget(self.create_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        privacy = QLabel(
            "No company policy is active. Existing PrivacyGate behavior remains unchanged."
        )
        privacy.setStyleSheet(
            f"background:{SOFT};border:1px solid {BORDER};border-radius:9px;"
            f"padding:10px;color:{NAVY};"
        )
        layout.addWidget(privacy)

        self.refresh_button.clicked.connect(self.refresh)
        self.join_button.clicked.connect(self._join_company)
        self.create_button.clicked.connect(self._create_workspace)
        return card

    def _build_org_header(self) -> QFrame:
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self.org_title = QLabel()
        self.org_title.setStyleSheet(f"color:{NAVY};font-size:20px;font-weight:950;")
        self.sync_label = QLabel()
        self.sync_label.setStyleSheet(f"color:{MUTED};")
        top.addWidget(self.org_title)
        top.addStretch(1)
        top.addWidget(self.sync_label)
        layout.addLayout(top)

        self.org_summary = QLabel(
            "Company controls privacy rules and approved destinations. "
            "Employees keep separate local Libraries, restore mappings and connector tokens."
        )
        self.org_summary.setWordWrap(True)
        self.org_summary.setStyleSheet(f"color:{MUTED};")
        layout.addWidget(self.org_summary)

        actions = QHBoxLayout()
        self.org_refresh_button = QPushButton("Refresh", objectName="Secondary")
        self.invite_button = QPushButton("Invite member", objectName="Primary")
        self.edit_policy_button = QPushButton(
            "Edit privacy policy", objectName="Secondary"
        )
        actions.addWidget(self.org_refresh_button)
        actions.addWidget(self.invite_button)
        actions.addWidget(self.edit_policy_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.org_refresh_button.clicked.connect(self.refresh)
        self.invite_button.clicked.connect(self._create_invite)
        self.edit_policy_button.clicked.connect(self._edit_policy)
        return card

    def _build_overview(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        metrics = QGridLayout()
        metrics.setSpacing(10)
        self.seats_card, self.seats_value, self.seats_detail = _metric_card("Seats")
        self.members_card, self.members_value, self.members_detail = _metric_card("Members")
        self.devices_card, self.devices_value, self.devices_detail = _metric_card("Managed devices")
        self.policy_card, self.policy_value, self.policy_detail = _metric_card("Policy")
        for column, card in enumerate(
            (self.seats_card, self.members_card, self.devices_card, self.policy_card)
        ):
            metrics.addWidget(card, 0, column)
        layout.addLayout(metrics)

        columns = QHBoxLayout()
        columns.setSpacing(10)

        policy_card = _card()
        policy_layout = QVBoxLayout(policy_card)
        policy_layout.setContentsMargins(16, 13, 16, 13)
        policy_title = QLabel("Company privacy policy")
        policy_title.setStyleSheet(f"color:{NAVY};font-size:14px;font-weight:900;")
        self.overview_policy = QLabel()
        self.overview_policy.setWordWrap(True)
        self.overview_policy.setStyleSheet(f"color:{MUTED};")
        policy_layout.addWidget(policy_title)
        policy_layout.addWidget(self.overview_policy)
        policy_layout.addStretch(1)
        columns.addWidget(policy_card, 1)

        destinations_card = _card()
        dest_layout = QVBoxLayout(destinations_card)
        dest_layout.setContentsMargins(16, 13, 16, 13)
        dest_title = QLabel("Approved destinations")
        dest_title.setStyleSheet(f"color:{NAVY};font-size:14px;font-weight:900;")
        self.overview_destinations = QLabel()
        self.overview_destinations.setWordWrap(True)
        self.overview_destinations.setStyleSheet(f"color:{MUTED};")
        dest_layout.addWidget(dest_title)
        dest_layout.addWidget(self.overview_destinations)
        dest_layout.addStretch(1)
        columns.addWidget(destinations_card, 1)

        layout.addLayout(columns)

        boundary = _card()
        boundary_layout = QVBoxLayout(boundary)
        boundary_layout.setContentsMargins(16, 12, 16, 12)
        title = QLabel("Privacy boundary")
        title.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:900;")
        self.boundary_text = QLabel(
            "Admin sees organization identity, roles, device status and policy sync only. "
            "Original/protected documents, Library contents, restore mappings and connector "
            "OAuth tokens stay on each employee device."
        )
        self.boundary_text.setWordWrap(True)
        self.boundary_text.setStyleSheet(f"color:{MUTED};")
        boundary_layout.addWidget(title)
        boundary_layout.addWidget(self.boundary_text)
        layout.addWidget(boundary)
        layout.addStretch(1)
        return page

    def _build_members(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("Members")
        title.setStyleSheet(f"color:{NAVY};font-size:16px;font-weight:900;")
        self.member_help = QLabel()
        self.member_help.setStyleSheet(f"color:{MUTED};")
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.member_help)
        layout.addLayout(top)

        self.members_table = QTableWidget(0, 4)
        self.members_table.setHorizontalHeaderLabels(
            ["Account", "Role", "Status", "Joined"]
        )
        self.members_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.members_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.members_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.members_table.verticalHeader().setVisible(False)
        self.members_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for column in (1, 2, 3):
            self.members_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        layout.addWidget(self.members_table, 1)

        actions = QHBoxLayout()
        self.member_role_button = QPushButton("Change role", objectName="Secondary")
        self.member_toggle_button = QPushButton("Disable / reactivate", objectName="Secondary")
        self.member_revoke_button = QPushButton("Revoke member", objectName="Secondary")
        actions.addWidget(self.member_role_button)
        actions.addWidget(self.member_toggle_button)
        actions.addWidget(self.member_revoke_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.member_role_button.clicked.connect(self._change_member_role)
        self.member_toggle_button.clicked.connect(self._toggle_member_status)
        self.member_revoke_button.clicked.connect(self._revoke_member)
        return page

    def _build_policy(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("Company privacy policy")
        title.setStyleSheet(f"color:{NAVY};font-size:16px;font-weight:900;")
        self.policy_version_chip = _status_chip("NO POLICY", tone="neutral")
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.policy_version_chip)
        layout.addLayout(top)

        grids = QHBoxLayout()
        grids.setSpacing(10)

        rules = _card()
        rules_layout = QVBoxLayout(rules)
        rules_layout.setContentsMargins(16, 13, 16, 13)
        rules_layout.addWidget(QLabel("Sensitive data rules"))
        self.policy_rules = QLabel()
        self.policy_rules.setWordWrap(True)
        self.policy_rules.setStyleSheet(f"color:{MUTED};")
        rules_layout.addWidget(self.policy_rules)
        rules_layout.addStretch(1)
        grids.addWidget(rules, 1)

        destinations = _card()
        dest_layout = QVBoxLayout(destinations)
        dest_layout.setContentsMargins(16, 13, 16, 13)
        dest_layout.addWidget(QLabel("AI & Apps"))
        self.policy_destinations = QLabel()
        self.policy_destinations.setWordWrap(True)
        self.policy_destinations.setStyleSheet(f"color:{MUTED};")
        dest_layout.addWidget(self.policy_destinations)
        dest_layout.addStretch(1)
        grids.addWidget(destinations, 1)
        layout.addLayout(grids)

        note = QLabel(
            "Required rules are enforced again immediately before protection and AI handoff; "
            "the UI checkbox is not the security boundary."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"background:#EDF8F4;border:1px solid #B9DECD;border-radius:9px;"
            f"padding:10px;color:{GREEN};"
        )
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _build_devices(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("Managed devices")
        title.setStyleSheet(f"color:{NAVY};font-size:16px;font-weight:900;")
        self.device_help = QLabel()
        self.device_help.setStyleSheet(f"color:{MUTED};")
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.device_help)
        layout.addLayout(top)

        self.devices_table = QTableWidget(0, 7)
        self.devices_table.setHorizontalHeaderLabels(
            ["User", "Device", "Platform", "App", "Status", "Policy", "Last sync"]
        )
        self.devices_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.devices_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.devices_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.devices_table.verticalHeader().setVisible(False)
        self.devices_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.devices_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        for column in range(2, 7):
            self.devices_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        layout.addWidget(self.devices_table, 1)

        actions = QHBoxLayout()
        self.device_toggle_button = QPushButton("Disable / reactivate", objectName="Secondary")
        self.device_revoke_button = QPushButton("Revoke device", objectName="Secondary")
        actions.addWidget(self.device_toggle_button)
        actions.addWidget(self.device_revoke_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.device_toggle_button.clicked.connect(self._toggle_device_status)
        self.device_revoke_button.clicked.connect(self._revoke_device)
        return page

    def _show_section(self, index: int) -> None:
        self.sections.setCurrentIndex(index)
        for button_index, button in enumerate(self.section_buttons):
            selected = button_index == index
            button.setChecked(selected)
            button.setStyleSheet(
                (
                    f"background:{TEAL};color:#FFFFFF;border:none;border-radius:9px;"
                    "padding:8px 14px;font-weight:900;"
                )
                if selected
                else (
                    f"background:#FFFFFF;color:{NAVY};border:1px solid {BORDER};"
                    "border-radius:9px;padding:8px 14px;font-weight:800;"
                )
            )

    # ------------------------------------------------------------- sync/state
    def current_policy(self) -> CompanyPolicy | None:
        return self.state.policy

    def refresh_silent(self) -> None:
        self._refresh(show_errors=False)

    def refresh(self) -> None:
        self._refresh(show_errors=True)

    def _refresh(self, *, show_errors: bool) -> None:
        if self._active_worker is not None:
            return

        def task():
            session = self.account_client.restore_session()
            if session is None:
                return None
            state = self.team_client.fetch_team_state(session)
            state = _account_entitlement(state, session.email)
            members: list[dict[str, object]] = []
            devices: list[dict[str, object]] = []
            if state.organization_id and state.role in {"owner", "admin", "manager"}:
                members = self.team_client.list_members(session, state.organization_id)
                devices = self.team_client.list_devices(session, state.organization_id)
            return state, members, devices

        worker = FunctionWorker(task)
        self._active_worker = worker
        self._set_busy(True)
        worker.signals.result.connect(self._refresh_ready)
        if show_errors:
            worker.signals.error.connect(
                lambda message: QMessageBox.warning(
                    self, "Organization sync unavailable", message
                )
            )
        worker.signals.finished.connect(self._worker_finished)
        self.thread_pool.start(worker)

    def _refresh_ready(self, payload: object) -> None:
        if payload is None:
            self._render()
            return
        state, members, devices = payload
        self._apply_state(state, members, devices)

    def _worker_finished(self) -> None:
        self._active_worker = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        for button in (
            self.refresh_button,
            self.join_button,
            self.create_button,
            self.org_refresh_button,
            self.edit_policy_button,
            self.invite_button,
            self.member_role_button,
            self.member_toggle_button,
            self.member_revoke_button,
            self.device_toggle_button,
            self.device_revoke_button,
        ):
            button.setEnabled(not busy)
        label = "Syncing…" if busy else "Refresh"
        self.refresh_button.setText(label)
        self.org_refresh_button.setText(label)

    def _apply_state(
        self,
        state: TeamState,
        members: list[dict[str, object]] | None = None,
        devices: list[dict[str, object]] | None = None,
    ) -> None:
        self.state_store.save(state)
        self.state = state
        self._cache_error = ""
        if members is not None:
            self._members = members
        if devices is not None:
            self._devices = devices
        self._render()
        self.policy_changed.emit(state.policy)
        self.state_changed.emit(state)

    # ---------------------------------------------------------------- render
    def _render(self) -> None:
        self.plan_badge.setText(self.state.plan.label.upper())
        self.role_badge.setText(
            self.state.role.upper() if self.state.organization_id else "INDIVIDUAL"
        )

        if self._cache_error:
            self.alert.setVisible(True)
            self.alert.setText(f"⚠ {self._cache_error}")
            self.alert.setStyleSheet(
                "background:#FFF2E2;color:#8A5600;border:1px solid #EDCD9B;"
                "border-radius:9px;padding:9px;"
            )
        else:
            self.alert.setVisible(False)

        has_org = bool(self.state.organization_id)
        self.individual_card.setVisible(not has_org)
        self.organization_shell.setVisible(has_org)

        if not has_org:
            signed_in = bool(self.account_client.current_user_id)
            self.individual_sync.setText(
                "Synced individual account" if signed_in else "Sign in required for cloud entitlement"
            )
            return

        self.org_title.setText(self.state.organization_name or "Organization")
        sync = (
            self.state.synced_at.replace("T", " ")[:16]
            if self.state.synced_at
            else "cached"
        )
        self.sync_label.setText(
            f"{self.state.role.title()} • {self.state.plan.label} • synced {sync}"
        )

        can_admin = self.state.role in {"owner", "admin"}
        can_manage = self.state.role in {"owner", "admin"}
        is_manager = self.state.role in {"owner", "admin", "manager"}

        self.invite_button.setVisible(can_admin)
        self.edit_policy_button.setVisible(can_admin and self.state.policy is not None)
        self.member_role_button.setVisible(can_manage)
        self.member_toggle_button.setVisible(can_manage)
        self.member_revoke_button.setVisible(can_manage)
        self.device_toggle_button.setVisible(can_manage)
        self.device_revoke_button.setVisible(can_manage)

        self.section_buttons[1].setVisible(is_manager)
        self.section_buttons[3].setVisible(is_manager)
        if not is_manager and self.sections.currentIndex() in {1, 3}:
            self._show_section(0)

        self._render_overview()
        self._render_members()
        self._render_policy()
        self._render_devices()

    def _render_overview(self) -> None:
        active_members = [
            row for row in self._members if str(row.get("status") or "") == "active"
        ]
        active_devices = [
            row for row in self._devices if str(row.get("status") or "") == "active"
        ]
        synced_devices = [
            row
            for row in active_devices
            if self.state.policy
            and int(row.get("last_policy_version") or 0) == self.state.policy.version
        ]

        if self.state.role in {"owner", "admin", "manager"}:
            used = len(active_members)
            limit = self.state.seat_limit
            self.seats_value.setText(f"{used} / {limit if limit is not None else '—'}")
            self.seats_detail.setText("Active memberships / licensed seats")
            self.members_value.setText(str(len(self._members)))
            self.members_detail.setText(f"{used} active")
            self.devices_value.setText(str(len(self._devices)))
            self.devices_detail.setText(
                f"{len(synced_devices)} on current policy"
                if self.state.policy
                else "No active company policy"
            )
        else:
            self.seats_value.setText("Managed")
            self.seats_detail.setText("Seat is controlled by your organization")
            self.members_value.setText("Private")
            self.members_detail.setText("Other members are not shown")
            self.devices_value.setText("This device")
            self.devices_detail.setText(
                self.identity_store.load_or_create().display_name
            )

        policy = self.state.policy
        if policy:
            self.policy_value.setText(f"v{policy.version}")
            self.policy_detail.setText("Active company policy")
            required = [
                _RULE_LABELS.get(entity, entity.replace("_", " ").title())
                for entity, directive in policy.protection_rules.items()
                if directive is ProtectionDirective.REQUIRED_PROTECT
            ]
            self.overview_policy.setText(
                "Required protection\n"
                + ("\n".join(f"🔒 {item}" for item in required) or "No mandatory categories")
            )
            allowed_ai = [
                key.title()
                for key, enabled in policy.allowed_ai.items()
                if enabled
            ]
            allowed_apps = [
                ("All approved connectors" if key == "*" else key.replace("_", " ").title())
                for key, enabled in policy.allowed_connectors.items()
                if enabled
            ]
            self.overview_destinations.setText(
                "AI\n"
                + (", ".join(allowed_ai) or "None")
                + "\n\nApps\n"
                + (", ".join(allowed_apps) or "None")
            )
        else:
            self.policy_value.setText("—")
            self.policy_detail.setText("Policy unavailable")
            self.overview_policy.setText("Company policy unavailable.")
            self.overview_destinations.setText("Approved destinations unavailable.")

    def _render_members(self) -> None:
        self.members_table.setRowCount(len(self._members))
        for row, member in enumerate(self._members):
            email = str(member.get("email") or member.get("user_id") or "Member")
            role = str(member.get("role") or "member").title()
            status = str(member.get("status") or "active").title()
            joined = str(member.get("joined_at") or "").replace("T", " ")[:16]
            values = (email, role, status, joined)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, str(member.get("user_id") or ""))
                    item.setData(int(Qt.ItemDataRole.UserRole) + 1, str(member.get("role") or "member"))
                    item.setData(int(Qt.ItemDataRole.UserRole) + 2, str(member.get("status") or "active"))
                self.members_table.setItem(row, column, item)
        self.member_help.setText(
            "Owner/Admin can manage roles and access."
            if self.state.role in {"owner", "admin"}
            else "Read-only organization view."
        )

    def _render_policy(self) -> None:
        policy = self.state.policy
        if not policy:
            self.policy_version_chip.setText("UNAVAILABLE")
            self.policy_rules.setText("Company policy unavailable.")
            self.policy_destinations.setText("Approved destinations unavailable.")
            return

        self.policy_version_chip.setText(f"ACTIVE • v{policy.version}")
        rules: list[str] = []
        for entity, directive in policy.protection_rules.items():
            label = _RULE_LABELS.get(entity, entity.replace("_", " ").title())
            lock = " 🔒" if directive is ProtectionDirective.REQUIRED_PROTECT else ""
            rules.append(f"{label}: {_directive_label(directive)}{lock}")
        self.policy_rules.setText("\n".join(rules))

        ai_lines = [
            f"{'✓' if enabled else '✕'} {key.title()}"
            for key, enabled in policy.allowed_ai.items()
        ]
        app_lines = [
            f"{'✓' if enabled else '✕'} "
            + ("All other connectors" if key == "*" else key.replace("_", " ").title())
            for key, enabled in policy.allowed_connectors.items()
        ]
        self.policy_destinations.setText(
            "AI\n" + "\n".join(ai_lines) + "\n\nApps\n" + "\n".join(app_lines)
        )

    def _render_devices(self) -> None:
        self.devices_table.setRowCount(len(self._devices))
        for row, device in enumerate(self._devices):
            policy_version = device.get("last_policy_version")
            last_sync = str(device.get("last_policy_sync_at") or "").replace("T", " ")[:16]
            values = (
                str(device.get("email") or device.get("user_id") or "Member"),
                str(device.get("display_name") or "Device"),
                str(device.get("platform") or "—"),
                str(device.get("app_version") or "—"),
                str(device.get("status") or "active").title(),
                f"v{policy_version}" if policy_version is not None else "—",
                last_sync or "—",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        str(device.get("installation_hash") or ""),
                    )
                    item.setData(
                        int(Qt.ItemDataRole.UserRole) + 1,
                        str(device.get("status") or "active"),
                    )
                self.devices_table.setItem(row, column, item)
        self.device_help.setText(
            "Owner/Admin can disable or revoke a managed endpoint."
            if self.state.role in {"owner", "admin"}
            else "Read-only organization view."
        )

    # -------------------------------------------------------------- enrollment
    def _require_signed_in(self) -> bool:
        if self.account_client.current_user_id:
            return True
        response = QMessageBox.question(
            self,
            "Sign in required",
            "Organization policy sync is attached to your PrivacyGate account. "
            "Open the account/connection page now?",
        )
        if response == QMessageBox.StandardButton.Yes:
            self.open_account.emit()
        return False

    def _join_company(self) -> None:
        if not self._require_signed_in():
            return
        code, ok = QInputDialog.getText(
            self,
            "Join a company",
            "Enter the one-time PrivacyGate company invitation code:",
        )
        if not ok or not code.strip():
            return
        self._run_team_action(
            lambda session: self.team_client.accept_invitation(session, code),
            success_message="Company policy activated on this device.",
        )

    def _create_workspace(self) -> None:
        if not self._require_signed_in():
            return
        name, ok = QInputDialog.getText(
            self,
            "Create Business workspace",
            "Company / organization name:",
        )
        if not ok or not name.strip():
            return
        seats, ok = QInputDialog.getInt(
            self,
            "Business seats",
            "Initial seat limit:",
            5,
            2,
            100,
            1,
        )
        if not ok:
            return

        def operation(session: AccountSession):
            try:
                return self.team_client.create_business_workspace(
                    session, name, seat_limit=seats
                )
            except TeamServiceError as error:
                if "already belongs to an active PrivacyGate organization" in str(error):
                    return self.team_client.fetch_team_state(session)
                raise

        self._run_team_action(
            operation,
            success_message="Business workspace is active on this device.",
        )

    # ------------------------------------------------------------ admin actions
    def _create_invite(self) -> None:
        if not self.state.organization_id or self.state.role not in {"owner", "admin"}:
            return
        role_label, ok = QInputDialog.getItem(
            self,
            "Invite member",
            "Role:",
            ["Member", "Manager", "Admin"],
            0,
            False,
        )
        if not ok:
            return
        role = role_label.lower()

        def task(session: AccountSession):
            return self.team_client.create_invitation(
                session,
                self.state.organization_id,
                role=role,
            )

        def success(code: str) -> None:
            QApplication.clipboard().setText(code)
            QMessageBox.information(
                self,
                "Invitation created",
                f"One-time invitation code:\n\n{code}\n\n"
                "The code has been copied to the clipboard and expires automatically.",
            )

        self._run_team_action(task, result_handler=success, refresh_after=True)

    def _edit_policy(self) -> None:
        if not self.state.policy or self.state.role not in {"owner", "admin"}:
            return
        dialog = PolicyEditorDialog(self.state.policy, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.updated_policy()
        self._run_team_action(
            lambda session: self.team_client.publish_policy(session, updated),
            success_message="Company policy published and cached on this device.",
        )

    def _selected_member(self) -> tuple[str, str, str] | None:
        row = self.members_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select a member", "Select a member first.")
            return None
        item = self.members_table.item(row, 0)
        if item is None:
            return None
        return (
            str(item.data(Qt.ItemDataRole.UserRole) or ""),
            str(item.data(int(Qt.ItemDataRole.UserRole) + 1) or "member"),
            str(item.data(int(Qt.ItemDataRole.UserRole) + 2) or "active"),
        )

    def _change_member_role(self) -> None:
        selected = self._selected_member()
        if not selected or not self.state.organization_id:
            return
        user_id, current_role, _status = selected
        if current_role == "owner":
            QMessageBox.information(
                self, "Owner role", "The organization owner role cannot be changed here."
            )
            return
        role_label, ok = QInputDialog.getItem(
            self,
            "Change member role",
            "New role:",
            ["Member", "Manager", "Admin"],
            ["member", "manager", "admin"].index(current_role)
            if current_role in {"member", "manager", "admin"}
            else 0,
            False,
        )
        if not ok:
            return
        self._run_team_action(
            lambda session: set_member_role(
                self.team_client, session, self.state.organization_id, user_id, role_label.lower()
            ),
            success_message="Member role updated.",
            refresh_after=True,
        )

    def _toggle_member_status(self) -> None:
        selected = self._selected_member()
        if not selected or not self.state.organization_id:
            return
        user_id, role, status = selected
        if role == "owner":
            QMessageBox.information(
                self, "Owner access", "The organization owner cannot be disabled."
            )
            return
        target = "active" if status != "active" else "disabled"
        self._run_team_action(
            lambda session: set_member_status(
                self.team_client, session, self.state.organization_id, user_id, target
            ),
            success_message=f"Member {target}.",
            refresh_after=True,
        )

    def _revoke_member(self) -> None:
        selected = self._selected_member()
        if not selected or not self.state.organization_id:
            return
        user_id, role, _status = selected
        if role == "owner":
            QMessageBox.information(
                self, "Owner access", "The organization owner cannot be revoked."
            )
            return
        if (
            QMessageBox.question(
                self,
                "Revoke member",
                "Revoke this member and disable their organization devices?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._run_team_action(
            lambda session: set_member_status(
                self.team_client, session, self.state.organization_id, user_id, "revoked"
            ),
            success_message="Member revoked.",
            refresh_after=True,
        )

    def _selected_device(self) -> tuple[str, str] | None:
        row = self.devices_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select a device", "Select a device first.")
            return None
        item = self.devices_table.item(row, 0)
        if item is None:
            return None
        installation_hash = str(item.data(Qt.ItemDataRole.UserRole) or "")
        status = str(item.data(int(Qt.ItemDataRole.UserRole) + 1) or "active")
        if not installation_hash:
            QMessageBox.warning(
                self,
                "Device unavailable",
                "This device record does not expose a management identifier yet. Refresh and try again.",
            )
            return None
        return installation_hash, status

    def _is_current_device(self, installation_hash: str) -> bool:
        identity = self.identity_store.load_or_create()
        current_hash = hashlib.sha256(
            identity.installation_id.encode("ascii")
        ).hexdigest()
        return installation_hash == current_hash

    def _toggle_device_status(self) -> None:
        selected = self._selected_device()
        if not selected or not self.state.organization_id:
            return
        installation_hash, status = selected
        if self._is_current_device(installation_hash):
            QMessageBox.information(
                self,
                "Current device",
                "For safety, manage this device from another Owner/Admin endpoint.",
            )
            return
        target = "active" if status != "active" else "disabled"
        self._run_team_action(
            lambda session: set_device_status(
                self.team_client, session, self.state.organization_id, installation_hash, target
            ),
            success_message=f"Device {target}.",
            refresh_after=True,
        )

    def _revoke_device(self) -> None:
        selected = self._selected_device()
        if not selected or not self.state.organization_id:
            return
        installation_hash, _status = selected
        if self._is_current_device(installation_hash):
            QMessageBox.information(
                self,
                "Current device",
                "For safety, revoke this device from another Owner/Admin endpoint.",
            )
            return
        if (
            QMessageBox.question(
                self,
                "Revoke device",
                "Revoke this endpoint from the organization? The device can no longer "
                "sync managed policy until it is explicitly reactivated.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._run_team_action(
            lambda session: set_device_status(
                self.team_client, session, self.state.organization_id, installation_hash, "revoked"
            ),
            success_message="Device revoked.",
            refresh_after=True,
        )

    # ------------------------------------------------------------ worker helper
    def _run_team_action(
        self,
        operation,
        *,
        success_message: str = "",
        result_handler=None,
        refresh_after: bool = False,
    ) -> None:
        if self._active_worker is not None:
            return

        def task():
            session = self.account_client.restore_session()
            if session is None:
                raise TeamServiceError("Sign in to your PrivacyGate account first.")
            return operation(session)

        worker = FunctionWorker(task)
        self._active_worker = worker
        self._set_busy(True)

        def ready(result: object) -> None:
            if isinstance(result, TeamState):
                self._apply_state(result)
                self.refresh_silent()
            elif result_handler is not None:
                result_handler(result)
            if success_message:
                QMessageBox.information(self, "PrivacyGate Organization", success_message)
            if refresh_after:
                QTimer.singleShot(0, self.refresh_silent)

        worker.signals.result.connect(ready)
        worker.signals.error.connect(
            lambda message: QMessageBox.warning(
                self, "Organization action failed", message
            )
        )
        worker.signals.finished.connect(self._worker_finished)
        self.thread_pool.start(worker)
