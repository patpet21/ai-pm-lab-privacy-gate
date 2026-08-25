from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QThreadPool, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.domain.company_policy import (
    CompanyPolicy,
    ProtectionDirective,
)
from ai_pm_lab_privacy_gate.domain.plans import PlanCode, all_plans
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
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


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


class PolicyEditorDialog(QDialog):
    def __init__(self, policy: CompanyPolicy, parent=None) -> None:
        super().__init__(parent)
        self.policy = policy
        self.setWindowTitle("Company privacy policy")
        self.resize(760, 680)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel(f"{policy.organization_name} — Company Policy")
        title.setStyleSheet("font-size:20px;font-weight:900;color:#062B4F;")
        note = QLabel(
            "These rules are distributed to managed devices. Documents, restore mappings "
            "and connector tokens stay on each employee's computer."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#61798A;")
        root.addWidget(title)
        root.addWidget(note)

        ai_box = QFrame()
        ai_box.setObjectName("Card")
        ai_layout = QHBoxLayout(ai_box)
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

        apps_box = QFrame()
        apps_box.setObjectName("Card")
        apps_layout = QGridLayout(apps_box)
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
        self.rules_table.horizontalHeader().setStretchLastSection(True)
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
                key: check.isChecked() for key, check in self.ai_checks.items()
            },
            allowed_connectors={
                key: check.isChecked()
                for key, check in self.connector_checks.items()
            },
            protection_rules={
                key: ProtectionDirective(str(combo.currentData()))
                for key, combo in self.rule_combos.items()
            },
        )


class TeamPage(QWidget):
    policy_changed = Signal(object)
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

        self._build_ui()
        self._render()
        QTimer.singleShot(1200, self.refresh_silent)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("Team & Plans")
        title.setStyleSheet("color:#062B4F;font-size:27px;font-weight:900;")
        subtitle = QLabel(
            "Basic, Pro, Business and Enterprise share one product foundation. "
            "Business/Enterprise add company policy, members and managed devices — not shared documents."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#61798A;font-size:11px;")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        self.plan_badge = QLabel()
        self.plan_badge.setStyleSheet(
            "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
            "border-radius:10px;padding:7px 11px;font-size:10px;font-weight:900;"
        )
        header.addWidget(self.plan_badge, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.alert = QLabel()
        self.alert.setWordWrap(True)
        self.alert.setVisible(False)
        root.addWidget(self.alert)

        plans = QGridLayout()
        plans.setSpacing(10)
        self.plan_cards: dict[PlanCode, QFrame] = {}
        self.plan_markers: dict[PlanCode, QLabel] = {}
        for column, definition in enumerate(all_plans()):
            card = QFrame()
            card.setObjectName("Card")
            layout = QVBoxLayout(card)
            heading = QLabel(definition.label)
            heading.setStyleSheet("color:#062B4F;font-size:16px;font-weight:900;")
            description = QLabel(definition.description)
            description.setWordWrap(True)
            description.setStyleSheet("color:#61798A;font-size:9px;")
            marker = QLabel()
            marker.setObjectName("Muted")
            layout.addWidget(heading)
            layout.addWidget(description)
            layout.addStretch(1)
            layout.addWidget(marker)
            plans.addWidget(card, 0, column)
            self.plan_cards[definition.code] = card
            self.plan_markers[definition.code] = marker
        root.addLayout(plans)

        self.workspace = QFrame()
        self.workspace.setObjectName("Card")
        workspace_layout = QVBoxLayout(self.workspace)
        workspace_layout.setContentsMargins(18, 16, 18, 16)

        top = QHBoxLayout()
        self.org_title = QLabel()
        self.org_title.setStyleSheet("color:#062B4F;font-size:18px;font-weight:900;")
        self.sync_label = QLabel()
        self.sync_label.setStyleSheet("color:#61798A;")
        top.addWidget(self.org_title)
        top.addStretch(1)
        top.addWidget(self.sync_label)
        workspace_layout.addLayout(top)

        self.org_summary = QLabel()
        self.org_summary.setWordWrap(True)
        workspace_layout.addWidget(self.org_summary)

        actions = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh", objectName="Secondary")
        self.join_button = QPushButton("Join company", objectName="Secondary")
        self.create_button = QPushButton(
            "Create Business workspace", objectName="Primary"
        )
        self.edit_policy_button = QPushButton("Edit company policy", objectName="Primary")
        self.invite_button = QPushButton("Create invite", objectName="Secondary")
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.join_button)
        actions.addWidget(self.create_button)
        actions.addWidget(self.edit_policy_button)
        actions.addWidget(self.invite_button)
        actions.addStretch(1)
        workspace_layout.addLayout(actions)

        self.policy_summary = QLabel()
        self.policy_summary.setWordWrap(True)
        self.policy_summary.setStyleSheet(
            "background:#F7FAFC;border:1px solid #DCE5EA;border-radius:9px;"
            "padding:10px;color:#17384E;"
        )
        workspace_layout.addWidget(self.policy_summary)

        details = QHBoxLayout()
        self.members_label = QLabel()
        self.members_label.setWordWrap(True)
        self.devices_label = QLabel()
        self.devices_label.setWordWrap(True)
        details.addWidget(self.members_label, 1)
        details.addWidget(self.devices_label, 1)
        workspace_layout.addLayout(details)

        root.addWidget(self.workspace)
        root.addStretch(1)

        self.refresh_button.clicked.connect(self.refresh)
        self.join_button.clicked.connect(self._join_company)
        self.create_button.clicked.connect(self._create_workspace)
        self.edit_policy_button.clicked.connect(self._edit_policy)
        self.invite_button.clicked.connect(self._create_invite)

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
                    self, "Team sync unavailable", message
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
            self.edit_policy_button,
            self.invite_button,
        ):
            button.setEnabled(not busy)
        self.refresh_button.setText("Syncing…" if busy else "Refresh")

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

    def _render(self) -> None:
        self.plan_badge.setText(self.state.plan.label.upper())
        for code, marker in self.plan_markers.items():
            if code == self.state.plan:
                marker.setText("CURRENT PLAN")
                marker.setStyleSheet("color:#0B7180;font-size:8px;font-weight:900;")
            elif code is PlanCode.BASIC:
                marker.setText("FREE")
                marker.setStyleSheet("color:#61798A;font-size:8px;font-weight:800;")
            elif code is PlanCode.BUSINESS:
                marker.setText("TEAM POLICY + SEATS")
                marker.setStyleSheet("color:#61798A;font-size:8px;font-weight:800;")
            elif code is PlanCode.ENTERPRISE:
                marker.setText("ADVANCED ORGANIZATION")
                marker.setStyleSheet("color:#61798A;font-size:8px;font-weight:800;")
            else:
                marker.setText("INDIVIDUAL")
                marker.setStyleSheet("color:#61798A;font-size:8px;font-weight:800;")

        if self._cache_error:
            self.alert.setVisible(True)
            self.alert.setText(f"⚠ {self._cache_error}")
            self.alert.setStyleSheet(
                "background:#FFF2E2;color:#8A5600;border:1px solid #EDCD9B;"
                "border-radius:9px;padding:9px;"
            )
        else:
            self.alert.setVisible(False)

        signed_in = bool(self.account_client.current_user_id)
        if not self.state.organization_id:
            self.org_title.setText("Individual workspace")
            self.sync_label.setText("Local-first")
            self.org_summary.setText(
                "Your current PrivacyGate data remains local. Sign in to sync an entitlement, "
                "join a company with an invitation code, or create a Business workspace. "
                "Enterprise is provisioned centrally rather than by a reusable local key."
            )
            self.policy_summary.setText(
                "No company policy is active. Existing PrivacyGate behavior remains unchanged."
            )
            self.members_label.setText("Members\n—")
            identity = self.identity_store.load_or_create()
            self.devices_label.setText(f"This device\n{identity.display_name} • local")
            self.join_button.setVisible(True)
            self.create_button.setVisible(True)
            self.edit_policy_button.setVisible(False)
            self.invite_button.setVisible(False)
            if not signed_in:
                self.sync_label.setText("Sign in required for cloud policy sync")
            return

        policy = self.state.policy
        self.org_title.setText(self.state.organization_name or "Company workspace")
        sync = self.state.synced_at.replace("T", " ")[:16] if self.state.synced_at else "cached"
        self.sync_label.setText(
            f"{self.state.role.title()} • {self.state.plan.label} • synced {sync}"
        )
        self.org_summary.setText(
            "Company controls privacy rules and approved destinations. "
            "Each employee keeps a separate local Library, restore mappings and connector tokens."
        )
        if policy:
            required = [
                entity.replace("_", " ").title()
                for entity, directive in policy.protection_rules.items()
                if directive is ProtectionDirective.REQUIRED_PROTECT
            ]
            allowed_ai = [
                key.title()
                for key, allowed in policy.allowed_ai.items()
                if allowed
            ]
            allowed_apps = [
                key.replace("_", " ").title()
                for key, allowed in policy.allowed_connectors.items()
                if allowed
            ]
            self.policy_summary.setText(
                f"{policy.policy_name} • v{policy.version} • ACTIVE\n"
                f"Required protection: {', '.join(required) or 'None'}\n"
                f"Allowed AI: {', '.join(allowed_ai) or 'None'}\n"
                f"Allowed Apps: {', '.join(allowed_apps) or 'None'}"
            )
        else:
            self.policy_summary.setText("Company policy unavailable.")

        member_lines = ["Members"]
        if self._members:
            for member in self._members[:8]:
                identity = str(member.get("email") or member.get("user_id") or "Member")
                member_lines.append(
                    f"• {identity} — {str(member.get('role') or 'member').title()}"
                )
        else:
            member_lines.append("• Synced member details available to managers/admins")
        self.members_label.setText("\n".join(member_lines))

        device_lines = ["Devices"]
        if self._devices:
            for device in self._devices[:8]:
                name = str(device.get("display_name") or "Device")
                version = device.get("last_policy_version")
                device_lines.append(
                    f"• {name} — policy v{version if version is not None else '—'}"
                )
        else:
            identity = self.identity_store.load_or_create()
            device_lines.append(f"• {identity.display_name} — protected locally")
        self.devices_label.setText("\n".join(device_lines))

        can_admin = self.state.role in {"owner", "admin"}
        self.join_button.setVisible(False)
        self.create_button.setVisible(False)
        self.edit_policy_button.setVisible(can_admin and policy is not None)
        self.invite_button.setVisible(can_admin)

    def _require_signed_in(self) -> bool:
        if self.account_client.current_user_id:
            return True
        response = QMessageBox.question(
            self,
            "Sign in required",
            "Team policy sync is attached to your PrivacyGate account. "
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
        self._run_team_action(
            lambda session: self.team_client.create_business_workspace(
                session, name, seat_limit=seats
            ),
            success_message=(
                "Business workspace created. A starter company policy is active and cached locally."
            ),
        )

    def _create_invite(self) -> None:
        if not self.state.organization_id or self.state.role not in {"owner", "admin"}:
            return
        role_label, ok = QInputDialog.getItem(
            self,
            "Create company invite",
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
                "The code has been copied to the clipboard. It expires automatically.",
            )

        self._run_team_action(task, result_handler=success)

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

    def _run_team_action(
        self,
        operation,
        *,
        success_message: str = "",
        result_handler=None,
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
                QMessageBox.information(self, "PrivacyGate Team", success_message)

        worker.signals.result.connect(ready)
        worker.signals.error.connect(
            lambda message: QMessageBox.warning(self, "Team action failed", message)
        )
        worker.signals.finished.connect(self._worker_finished)
        self.thread_pool.start(worker)
