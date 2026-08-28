from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.domain.plans import Capability, supports
from ai_pm_lab_privacy_gate.ui.dialog_visual_system import (
    BORDER,
    BORDER_SOFT,
    CANVAS,
    FIELD,
    GREEN,
    INK,
    MUTED,
    NAVY,
    SURFACE,
    TEAL,
    TEAL_DARK,
    TEAL_SOFT,
    _button_qss,
)
from ai_pm_lab_privacy_gate.ui.feature_suite_2026 import WatchedFoldersDialog
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    BLUE,
    BLUE_SOFT,
    action_button,
    card,
    chip,
    clear_layout,
    heading,
    muted,
)
from ai_pm_lab_privacy_gate.ui.mockup_organization_overview_final_2026 import (
    OrganizationOverviewFinal,
)
from ai_pm_lab_privacy_gate.ui.mockup_team_members_2026 import TeamMembersFinal
from ai_pm_lab_privacy_gate.ui.team_page import TeamPage


# ---------------------------------------------------------------------------
# Shared product-dialog foundation
# ---------------------------------------------------------------------------
class PrivacyGateProductDialog(QDialog):
    """Reusable shell for product-grade PrivacyGate forms.

    The global dialog visual system continues to style every legacy QDialog,
    QMessageBox and QInputDialog automatically. New, richer workflows can use
    this shell so headers, fields, privacy notes and actions remain identical
    without rebuilding dialog chrome in every feature module.
    """

    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str,
        subtitle: str,
        icon_name: str = "settings",
        width: int = 620,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(width)
        self.setStyleSheet(
            f"QDialog{{background:{CANVAS};color:{INK};}}"
            f"QFrame#PGProductDialogCard{{background:{SURFACE};border:1px solid {BORDER};border-radius:16px;}}"
            f"QLabel#PGDialogTitle{{color:{NAVY};font-size:20px;font-weight:950;border:none;}}"
            f"QLabel#PGDialogSubtitle{{color:{MUTED};font-size:9px;border:none;}}"
            f"QLabel#PGDialogFieldLabel{{color:{INK};font-size:9px;font-weight:850;border:none;}}"
            f"QComboBox,QSpinBox,QLineEdit{{background:{FIELD};color:{INK};border:1px solid #D4E0E6;"
            "border-radius:10px;padding:8px 10px;min-height:28px;font-size:10px;}"
            f"QComboBox:focus,QSpinBox:focus,QLineEdit:focus{{background:#FFFFFF;border:1px solid {TEAL};}}"
            "QComboBox::drop-down{border:none;width:28px;}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(0)

        self.card = QFrame(objectName="PGProductDialogCard")
        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(13)
        outer.addWidget(self.card)

        header = QHBoxLayout()
        header.setSpacing(12)
        bubble = QLabel()
        bubble.setFixedSize(44, 44)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setPixmap(icon(icon_name, color=BLUE, size=23).pixmap(23, 23))
        bubble.setStyleSheet(f"background:{BLUE_SOFT};border:none;border-radius:13px;")
        header.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(3)
        title_label = QLabel(title, objectName="PGDialogTitle")
        subtitle_label = QLabel(subtitle, objectName="PGDialogSubtitle")
        subtitle_label.setWordWrap(True)
        copy.addWidget(title_label)
        copy.addWidget(subtitle_label)
        header.addLayout(copy, 1)
        self.body.addLayout(header)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background:{BORDER_SOFT};border:none;")
        self.body.addWidget(divider)

    def add_field(self, label: str, widget: QWidget, help_text: str = "") -> None:
        caption = QLabel(label, objectName="PGDialogFieldLabel")
        self.body.addWidget(caption)
        self.body.addWidget(widget)
        if help_text:
            note = QLabel(help_text)
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
            self.body.addWidget(note)

    def add_notice(self, text: str, *, privacy: bool = False) -> None:
        panel = QFrame()
        tone_bg = "#F0FDF4" if privacy else TEAL_SOFT
        tone_border = "#BBE3C7" if privacy else "#CDE7E9"
        tone_text = GREEN if privacy else TEAL_DARK
        panel.setStyleSheet(
            f"QFrame{{background:{tone_bg};border:1px solid {tone_border};border-radius:10px;}}"
        )
        row = QHBoxLayout(panel)
        row.setContentsMargins(11, 9, 11, 9)
        row.setSpacing(8)
        mark = QLabel()
        mark.setPixmap(icon("protect" if privacy else "check", color=tone_text, size=17).pixmap(17, 17))
        row.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{INK};font-size:8px;border:none;")
        row.addWidget(label, 1)
        self.body.addWidget(panel)

    def add_actions(
        self,
        *,
        primary_text: str,
        primary_callback,
        secondary_text: str = "Cancel",
        secondary_callback=None,
        primary_enabled: bool = True,
    ) -> tuple[QPushButton, QPushButton]:
        row = QHBoxLayout()
        row.addStretch(1)
        secondary = QPushButton(secondary_text)
        secondary.setMinimumHeight(42)
        secondary.setMinimumWidth(104)
        secondary.setCursor(Qt.CursorShape.PointingHandCursor)
        secondary.setStyleSheet(_button_qss("secondary"))
        secondary.clicked.connect(secondary_callback or self.reject)
        primary = QPushButton(primary_text)
        primary.setMinimumHeight(42)
        primary.setMinimumWidth(128)
        primary.setCursor(Qt.CursorShape.PointingHandCursor)
        primary.setStyleSheet(_button_qss("primary"))
        primary.setEnabled(primary_enabled)
        primary.clicked.connect(primary_callback)
        row.addWidget(secondary)
        row.addWidget(primary)
        self.body.addLayout(row)
        return primary, secondary


class InviteMemberDialog(PrivacyGateProductDialog):
    """Collect only values required by the existing invitation RPC."""

    def __init__(self, parent: QWidget | None) -> None:
        super().__init__(
            parent,
            title="Invite member",
            subtitle="Create a one-time organization invite without collecting a recipient email or other unnecessary personal data.",
            icon_name="contact",
            width=620,
        )
        self.role = QComboBox()
        for label, value in (("Member", "member"), ("Manager", "manager"), ("Admin", "admin")):
            self.role.addItem(label, value)
        self.add_field(
            "Role",
            self.role,
            "The role controls organization access after the invitation is accepted.",
        )

        self.expiry = QComboBox()
        for label, hours in (("24 hours", 24), ("72 hours", 72), ("7 days", 168)):
            self.expiry.addItem(label, hours)
        self.expiry.setCurrentIndex(1)
        self.add_field(
            "Invitation expires",
            self.expiry,
            "Short-lived invitation codes reduce the amount of persistent access metadata.",
        )

        self.add_notice(
            "Privacy by design: PrivacyGate sends only organization ID, selected role and expiry to the existing invitation service. No recipient email, name, document data or connector data is required.",
            privacy=True,
        )
        self.add_notice(
            "A licensed seat is consumed only when a person accepts the invitation and becomes an active organization member."
        )
        self.add_actions(primary_text="Create invite", primary_callback=self.accept)

    @property
    def selected_role(self) -> str:
        return str(self.role.currentData() or "member")

    @property
    def expires_hours(self) -> int:
        return int(self.expiry.currentData() or 72)


class InvitationReadyDialog(PrivacyGateProductDialog):
    def __init__(self, parent: QWidget | None, *, code: str, role: str, expires_hours: int) -> None:
        super().__init__(
            parent,
            title="Invitation ready",
            subtitle="Share this one-time code directly with the person you want to add.",
            icon_name="check",
            width=640,
        )
        self.code = QLineEdit(code)
        self.code.setReadOnly(True)
        self.code.setCursorPosition(0)
        self.add_field("One-time invite code", self.code)
        expiry_label = "7 days" if expires_hours == 168 else f"{expires_hours} hours"
        self.add_notice(f"Role: {role.title()}  ·  Expires in: {expiry_label}")
        self.add_notice(
            "PrivacyGate does not need to know who you send this code to. The recipient identity is associated only when they authenticate and accept the invitation.",
            privacy=True,
        )
        actions = QHBoxLayout()
        actions.addStretch(1)
        close = QPushButton("Done")
        close.setMinimumHeight(42)
        close.setMinimumWidth(104)
        close.setStyleSheet(_button_qss("secondary"))
        close.clicked.connect(self.accept)
        copy = QPushButton("Copy invite code")
        copy.setMinimumHeight(42)
        copy.setMinimumWidth(144)
        copy.setStyleSheet(_button_qss("primary"))
        copy.clicked.connect(self._copy)
        actions.addWidget(close)
        actions.addWidget(copy)
        self.body.addLayout(actions)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.code.text())
        self.code.selectAll()


class SeatManagementDialog(PrivacyGateProductDialog):
    """Billing-ready seat UX that deliberately does not mutate entitlement data."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        plan_label: str,
        licensed_seats: int,
        active_members: int,
    ) -> None:
        super().__init__(
            parent,
            title="Add organization seats",
            subtitle="Plan the seat increase now. The licensed limit changes only after a real billing checkout confirms payment.",
            icon_name="contact",
            width=660,
        )
        self.licensed_seats = max(0, int(licensed_seats))
        self.active_members = max(0, int(active_members))

        summary = QFrame()
        summary.setStyleSheet(f"QFrame{{background:#F8FAFC;border:1px solid {BORDER};border-radius:11px;}}")
        summary_box = QHBoxLayout(summary)
        summary_box.setContentsMargins(12, 10, 12, 10)
        for title, value in (
            ("Plan", plan_label),
            ("Licensed seats", str(self.licensed_seats)),
            ("Active members", str(self.active_members)),
        ):
            cell = QVBoxLayout()
            caption = QLabel(title)
            caption.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;")
            number = QLabel(value)
            number.setStyleSheet(f"color:{INK};font-size:12px;font-weight:900;border:none;")
            cell.addWidget(caption)
            cell.addWidget(number)
            summary_box.addLayout(cell, 1)
        self.body.addWidget(summary)

        self.quantity = QSpinBox()
        self.quantity.setRange(1, max(1, 100 - self.licensed_seats))
        self.quantity.setValue(1)
        self.add_field(
            "Additional seats",
            self.quantity,
            "Seat quantity is calculated locally in this dialog and is not written to Supabase.",
        )

        self.new_total = QLabel()
        self.new_total.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:900;border:none;")
        self.pricing = QLabel("Per-seat price · Defined by the billing checkout")
        self.pricing.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
        self.body.addWidget(self.new_total)
        self.body.addWidget(self.pricing)
        self.quantity.valueChanged.connect(self._update_total)
        self._update_total()

        self.add_notice(
            "Billing boundary: payment-card data should be collected by the billing provider, not PrivacyGate. The PrivacyGate control plane should receive only the minimum entitlement result needed to enforce the paid seat limit.",
            privacy=True,
        )
        self.add_notice(
            "Billing is not connected in this test build. Continuing will not change the current 7-seat entitlement and no payment will be attempted."
            if self.licensed_seats == 7
            else "Billing is not connected in this test build. Continuing will not change the current seat entitlement and no payment will be attempted."
        )
        self.add_actions(primary_text="Continue to billing", primary_callback=self._billing_unavailable)

    def _update_total(self) -> None:
        self.new_total.setText(
            f"New licensed total after successful checkout · {self.licensed_seats + int(self.quantity.value())} seats"
        )

    def _billing_unavailable(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Billing integration required")
        box.setText("No seat entitlement was changed.")
        box.setInformativeText(
            "This branch now has the seat-management UX and privacy boundary, but no payment provider is connected yet. A future hosted checkout can use the selected quantity and update the organization entitlement only after confirmed payment."
        )
        box.exec()


# ---------------------------------------------------------------------------
# Team actions / seat UX
# ---------------------------------------------------------------------------
def _install_invitation_dialog() -> None:
    if bool(getattr(TeamPage, "_privacygate_product_invite_2026", False)):
        return

    def create_invite(self: TeamPage) -> None:
        if self.state.role not in {"owner", "admin"}:
            return
        dialog = InviteMemberDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        role = dialog.selected_role
        expires_hours = dialog.expires_hours
        organization_id = self.state.organization_id

        def show_code(value: object) -> None:
            code = str(value or "").strip()
            if not code:
                QMessageBox.warning(self, "Invitation unavailable", "The invitation service did not return a code.")
                return
            ready = InvitationReadyDialog(
                self,
                code=code,
                role=role,
                expires_hours=expires_hours,
            )
            ready.exec()

        self._run_team_action(
            lambda session: self.team_client.create_invitation(
                session,
                organization_id,
                role=role,
                expires_hours=expires_hours,
            ),
            result_handler=show_code,
        )

    TeamPage._create_invite = create_invite
    TeamPage._privacygate_product_invite_2026 = True


def _open_seat_dialog(view: TeamMembersFinal) -> None:
    state = view.team_page.state
    limit = state.seat_limit
    if limit is None or state.role not in {"owner", "admin"}:
        return
    active_members = sum(
        1
        for row in view.team_page._members
        if str(row.get("status") or "active").lower() == "active"
    )
    dialog = SeatManagementDialog(
        view,
        plan_label=state.plan.label,
        licensed_seats=int(limit),
        active_members=active_members,
    )
    dialog.exec()


def _install_team_seat_action() -> None:
    if bool(getattr(TeamMembersFinal, "_privacygate_seat_action_2026", False)):
        return

    original_build = TeamMembersFinal._build
    original_render = TeamMembersFinal.render

    def build(self: TeamMembersFinal) -> None:
        original_build(self)
        seats = self.findChild(QFrame, "TeamMembersSeats")
        if seats is None or seats.layout() is None:
            return
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.add_seats_button = action_button(
            "Add seats",
            lambda: _open_seat_dialog(self),
            primary=False,
        )
        self.add_seats_button.setToolTip(
            "Plan a paid seat increase. The entitlement is not changed until real billing is connected."
        )
        actions.addWidget(self.add_seats_button)
        seats.layout().addLayout(actions)

    def render(self: TeamMembersFinal) -> None:
        original_render(self)
        button = getattr(self, "add_seats_button", None)
        if button is not None:
            button.setVisible(
                self.team_page.state.role in {"owner", "admin"}
                and self.team_page.state.seat_limit is not None
            )

    TeamMembersFinal._build = build
    TeamMembersFinal.render = render
    TeamMembersFinal._privacygate_seat_action_2026 = True


# ---------------------------------------------------------------------------
# Organization Overview: real local workflows only
# ---------------------------------------------------------------------------
class ActiveWorkflowsCard(QFrame):
    def __init__(self, overview: OrganizationOverviewFinal) -> None:
        super().__init__()
        self.overview = overview
        self.main_window = overview.main_window
        self.team_page = overview.team_page
        self.setObjectName("OrgFinalActiveWorkflows")
        self.setStyleSheet(
            f"QFrame#OrgFinalActiveWorkflows{{background:#FFFFFF;border:1px solid {BORDER};border-radius:14px;}}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 15, 18, 15)
        root.setSpacing(10)

        top = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(2)
        title.addWidget(heading("Active workflows", 13))
        title.addWidget(
            muted(
                "Live local automations for this workspace. Only workflow type/status is summarized here; folder paths and document details stay local and are not sent to the Organization control plane.",
                8,
            )
        )
        top.addLayout(title, 1)
        self.count_chip = chip("0 ACTIVE", "neutral")
        top.addWidget(self.count_chip, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(top)

        self.rows = QVBoxLayout()
        self.rows.setSpacing(0)
        root.addLayout(self.rows)

        footer = QHBoxLayout()
        self.status = muted("", 8)
        footer.addWidget(self.status, 1)
        manage = action_button("Manage workflows", self._manage)
        open_studio = action_button("Open Automation", self._open_automation, primary=True)
        footer.addWidget(manage)
        footer.addWidget(open_studio)
        root.addLayout(footer)
        self.render()

    def _workspace_key(self) -> str:
        store = getattr(self.team_page, "_privacygate_workspace_store", None)
        if store is not None:
            try:
                return str(store.load().active_key or "")
            except Exception:
                pass
        organization_id = str(self.team_page.state.organization_id or "")
        return f"org:{organization_id}" if organization_id else "personal"

    def _configs(self):
        controller = getattr(self.main_window, "privacygate_feature_suite", None)
        watch_store = getattr(controller, "watch_store", None) if controller is not None else None
        if watch_store is None:
            return ()
        try:
            workspace_key = self._workspace_key()
            return tuple(
                item
                for item in watch_store.list()
                if item.enabled and str(item.workspace_key or "") == workspace_key
            )
        except Exception:
            return ()

    def render(self) -> None:
        clear_layout(self.rows)
        configs = self._configs()
        self.count_chip.setText(f"{len(configs)} ACTIVE")
        self.count_chip.setProperty("workflowActive", bool(configs))

        if not configs:
            empty = QLabel("No active local workflows in this workspace.")
            empty.setMinimumHeight(48)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
            self.rows.addWidget(empty)
            self.status.setText("Create a real Watched Folder workflow to see it here.")
            return

        for config in configs[:4]:
            row = QFrame()
            row.setStyleSheet("QFrame{background:transparent;border:none;border-bottom:1px solid #F2F4F7;}")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(1, 7, 1, 7)
            layout.setSpacing(10)
            bubble = QLabel()
            bubble.setFixedSize(30, 30)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setPixmap(icon("workflow", color=TEAL_DARK, size=16).pixmap(16, 16))
            bubble.setStyleSheet(f"background:{TEAL_SOFT};border:none;border-radius:9px;")
            layout.addWidget(bubble)
            copy = QVBoxLayout()
            copy.setSpacing(1)
            name = QLabel("Watched folder · Inbox → Protected")
            name.setStyleSheet(f"color:{INK};font-size:8.5px;font-weight:800;border:none;")
            meta = QLabel(f"Profile · {str(config.profile_key or 'default').replace('_', ' ').title()}  ·  Local monitoring")
            meta.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;")
            copy.addWidget(name)
            copy.addWidget(meta)
            layout.addLayout(copy, 1)
            active = QLabel("ACTIVE")
            active.setStyleSheet(
                "background:#F0FDF4;color:#15803D;border:1px solid #BBE3C7;border-radius:7px;"
                "padding:3px 6px;font-size:7px;font-weight:900;"
            )
            layout.addWidget(active)
            self.rows.addWidget(row)
        self.status.setText(
            f"{len(configs)} local workflow(s) active for the selected workspace."
        )

    def _manage(self) -> None:
        controller = getattr(self.main_window, "privacygate_feature_suite", None)
        if controller is None:
            self._open_automation()
            return
        plan = controller.plan_for_workspace(self._workspace_key())
        if not supports(plan, Capability.WATCHED_FOLDERS):
            controller.show_locked(Capability.WATCHED_FOLDERS, "Watched Folders")
            return
        dialog = WatchedFoldersDialog(controller)
        dialog.exec()
        self.render()

    def _open_automation(self) -> None:
        controller = getattr(self.main_window, "_privacygate_redesign_sidebar_controller", None)
        opener = getattr(controller, "_open_page", None) if controller is not None else None
        if callable(opener):
            opener("local_automation_page")
            return
        page = getattr(self.main_window, "local_automation_page", None)
        pages = getattr(self.main_window, "pages", None)
        if page is not None and pages is not None:
            pages.setCurrentWidget(page)


def _install_workflow_overview() -> None:
    if bool(getattr(OrganizationOverviewFinal, "_privacygate_active_workflows_2026", False)):
        return

    original_build = OrganizationOverviewFinal._build
    original_render = OrganizationOverviewFinal.render

    def build(self: OrganizationOverviewFinal) -> None:
        original_build(self)
        host = self.findChild(QWidget, "OrganizationOverviewFinalHost")
        layout = host.layout() if host is not None else None
        if not isinstance(layout, QVBoxLayout):
            return
        self.active_workflows_card = ActiveWorkflowsCard(self)
        insert_at = max(0, layout.count() - 1)
        layout.insertWidget(insert_at, self.active_workflows_card)

    def render(self: OrganizationOverviewFinal) -> None:
        original_render(self)
        workflow = getattr(self, "active_workflows_card", None)
        if workflow is not None:
            workflow.render()

    OrganizationOverviewFinal._build = build
    OrganizationOverviewFinal.render = render
    OrganizationOverviewFinal._privacygate_active_workflows_2026 = True


def install_organization_product_experience_2026() -> None:
    """Install privacy-minimal organization UX before Team/Overview construction."""
    _install_invitation_dialog()
    _install_team_seat_action()
    _install_workflow_overview()
