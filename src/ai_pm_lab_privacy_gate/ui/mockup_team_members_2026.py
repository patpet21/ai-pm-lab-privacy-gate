from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    AMBER,
    BLUE,
    BORDER,
    CANVAS,
    GREEN,
    INK,
    MUTED,
    PURPLE,
    RED,
    TEAL,
    TEXT,
    WHITE,
    action_button,
    card,
    chip,
    heading,
    muted,
)


class TeamMembersFinal(QWidget):
    """Modern Team/Members surface backed entirely by the existing TeamPage."""

    def __init__(self, main_window, dashboard, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.dashboard = dashboard
        self.team_page = dashboard.team_page
        self.summary_values: dict[str, QLabel] = {}
        self._build()
        self._adopt_existing_team_actions()
        self.render()

        self.team_page.state_changed.connect(lambda _state: QTimer.singleShot(0, self.render))
        self.team_page.policy_changed.connect(lambda _policy: QTimer.singleShot(0, self.render))

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea{{background:{CANVAS};border:none;}}"
            "QScrollBar:vertical{background:transparent;width:7px;margin:2px;}"
            "QScrollBar::handle:vertical{background:#D0D5DD;border-radius:3px;min-height:30px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )

        host = QWidget()
        host.setObjectName("TeamMembersFinalHost")
        host.setStyleSheet(f"QWidget#TeamMembersFinalHost{{background:{CANVAS};}}")
        body = QVBoxLayout(host)
        body.setContentsMargins(0, 4, 0, 22)
        body.setSpacing(14)

        header = QHBoxLayout()
        copy = QVBoxLayout()
        copy.setSpacing(3)
        copy.addWidget(heading("Members & access", 18))
        copy.addWidget(
            muted(
                "Manage organization membership, roles, seat usage and each member's managed endpoints.",
                9,
            )
        )
        header.addLayout(copy, 1)
        self.refresh_button = action_button("Refresh", self.team_page.refresh)
        self.invite_button = action_button("Invite member", self._invite, primary=True)
        header.addWidget(self.refresh_button, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(self.invite_button, 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(header)

        summary = QGridLayout()
        summary.setHorizontalSpacing(10)
        summary.setVerticalSpacing(10)
        specs = (
            ("active", "Active members", "contact", BLUE),
            ("leaders", "Admins / managers", "settings", PURPLE),
            ("disabled", "Disabled access", "history", AMBER),
            ("devices", "Managed devices", "document", TEAL),
        )
        for index, (key, title, icon_name, tone) in enumerate(specs):
            panel = card(f"TeamMembersSummary_{key}")
            panel.setMinimumHeight(78)
            row = QHBoxLayout(panel)
            row.setContentsMargins(13, 11, 13, 11)
            row.setSpacing(10)
            ico = QLabel()
            ico.setFixedSize(32, 32)
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setPixmap(icon(icon_name, color=tone, size=17).pixmap(17, 17))
            ico.setStyleSheet("background:#F8FAFC;border:1px solid #EAECF0;border-radius:9px;")
            row.addWidget(ico)
            text = QVBoxLayout()
            text.setSpacing(1)
            label = QLabel(title)
            label.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
            value = QLabel("0")
            value.setStyleSheet(f"color:{INK};font-size:18px;font-weight:950;border:none;")
            text.addWidget(label)
            text.addWidget(value)
            row.addLayout(text, 1)
            self.summary_values[key] = value
            summary.addWidget(panel, 0, index)
        body.addLayout(summary)

        seats = card("TeamMembersSeats")
        seat_box = QVBoxLayout(seats)
        seat_box.setContentsMargins(15, 12, 15, 12)
        seat_box.setSpacing(7)
        seat_top = QHBoxLayout()
        seat_top.addWidget(QLabel("Licensed seats"))
        seat_top.itemAt(0).widget().setStyleSheet(
            f"color:{TEXT};font-size:9px;font-weight:850;border:none;"
        )
        seat_top.addStretch(1)
        self.seat_value = QLabel("—")
        self.seat_value.setStyleSheet(f"color:{INK};font-size:10px;font-weight:900;border:none;")
        seat_top.addWidget(self.seat_value)
        seat_box.addLayout(seat_top)
        self.seat_progress = QProgressBar()
        self.seat_progress.setRange(0, 100)
        self.seat_progress.setTextVisible(False)
        self.seat_progress.setFixedHeight(8)
        self.seat_progress.setStyleSheet(
            "QProgressBar{background:#EAECF0;border:none;border-radius:4px;}"
            f"QProgressBar::chunk{{background:{BLUE};border-radius:4px;}}"
        )
        seat_box.addWidget(self.seat_progress)
        self.seat_note = muted("Active memberships consume organization seats.", 8)
        seat_box.addWidget(self.seat_note)
        body.addWidget(seats)

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._members_card(), 7)
        content.addWidget(self._detail_card(), 3)
        body.addLayout(content)

        privacy = QFrame()
        privacy.setStyleSheet(
            "QFrame{background:#F0FDF4;border:1px solid #BBE3C7;border-radius:11px;}"
        )
        privacy_row = QHBoxLayout(privacy)
        privacy_row.setContentsMargins(13, 10, 13, 10)
        privacy_row.setSpacing(9)
        privacy_icon = QLabel()
        privacy_icon.setPixmap(icon("protect", color=GREEN, size=17).pixmap(17, 17))
        privacy_row.addWidget(privacy_icon)
        privacy_text = QLabel(
            "Organization admins see identity, role, access and managed-device metadata only. "
            "Original documents, protected files, restore mappings and connector tokens remain local."
        )
        privacy_text.setWordWrap(True)
        privacy_text.setStyleSheet(f"color:{TEXT};font-size:8px;border:none;")
        privacy_row.addWidget(privacy_text, 1)
        body.addWidget(privacy)
        body.addStretch(1)

        scroll.setWidget(host)
        root.addWidget(scroll)

    def _members_card(self) -> QFrame:
        panel = card("TeamMembersRoster")
        box = QVBoxLayout(panel)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(10)

        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(heading("Organization members", 13))
        self.member_help = muted("", 8)
        titles.addWidget(self.member_help)
        top.addLayout(titles, 1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search members")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(230)
        self.search.setStyleSheet(
            "QLineEdit{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:9px;"
            "padding:8px 10px;font-size:8.5px;}QLineEdit:focus{border-color:#84ADFF;}"
        )
        self.search.textChanged.connect(self._apply_filter)
        top.addWidget(self.search)
        box.addLayout(top)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Account", "Role", "Status", "Joined"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(265)
        self.table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#344054;border:1px solid #EAECF0;border-radius:9px;gridline-color:#F2F4F7;}"
            "QTableWidget::item{padding:8px;border-bottom:1px solid #F2F4F7;font-size:8.5px;}"
            "QTableWidget::item:selected{background:#EEF4FF;color:#1D2939;}"
            "QHeaderView::section{background:#F8FAFC;color:#667085;border:none;border-bottom:1px solid #EAECF0;"
            "padding:8px;font-size:7.5px;font-weight:850;}"
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._render_selected_member)
        box.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.role_button = action_button("Change role", self.team_page._change_member_role)
        self.toggle_button = action_button("Disable / reactivate", self.team_page._toggle_member_status)
        self.revoke_button = QPushButton("Revoke member")
        self.revoke_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.revoke_button.setStyleSheet(
            f"QPushButton{{background:{WHITE};color:{RED};border:1px solid #F2B8B5;border-radius:9px;"
            "padding:8px 11px;font-size:8.5px;font-weight:800;}"
            "QPushButton:hover{background:#FFF5F5;}"
        )
        self.revoke_button.clicked.connect(self.team_page._revoke_member)
        actions.addWidget(self.role_button)
        actions.addWidget(self.toggle_button)
        actions.addWidget(self.revoke_button)
        actions.addStretch(1)
        box.addLayout(actions)
        return panel

    def _detail_card(self) -> QFrame:
        panel = card("TeamMemberDetail")
        panel.setMinimumWidth(250)
        box = QVBoxLayout(panel)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(9)
        box.addWidget(heading("Member detail", 13))

        self.detail_avatar = QLabel("—")
        self.detail_avatar.setFixedSize(44, 44)
        self.detail_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_avatar.setStyleSheet(
            "background:#EEF4FF;color:#2563EB;border:none;border-radius:22px;font-size:11px;font-weight:950;"
        )
        box.addWidget(self.detail_avatar, 0, Qt.AlignmentFlag.AlignLeft)
        self.detail_email = QLabel("Select a member")
        self.detail_email.setWordWrap(True)
        self.detail_email.setStyleSheet(f"color:{INK};font-size:10px;font-weight:900;border:none;")
        box.addWidget(self.detail_email)
        self.detail_role = chip("—", "neutral")
        box.addWidget(self.detail_role, 0, Qt.AlignmentFlag.AlignLeft)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{BORDER};border:none;")
        box.addWidget(line)
        self.detail_status = muted("Status —", 8)
        self.detail_joined = muted("Joined —", 8)
        self.detail_devices = muted("Managed devices —", 8)
        box.addWidget(self.detail_status)
        box.addWidget(self.detail_joined)
        box.addWidget(self.detail_devices)

        self.detail_device_list = QLabel("")
        self.detail_device_list.setWordWrap(True)
        self.detail_device_list.setStyleSheet(f"color:{TEXT};font-size:8px;border:none;")
        box.addWidget(self.detail_device_list)
        box.addStretch(1)
        return panel

    def _adopt_existing_team_actions(self) -> None:
        # Existing TeamPage methods remain the authority for role/access changes.
        # Re-point their widget references so permissions and actions operate on
        # this redesigned table instead of duplicating any Supabase semantics.
        self.team_page.members_table = self.table
        self.team_page.member_help = self.member_help
        self.team_page.member_role_button = self.role_button
        self.team_page.member_toggle_button = self.toggle_button
        self.team_page.member_revoke_button = self.revoke_button

    # ---------------------------------------------------------------- actions
    def _invite(self) -> None:
        if self.team_page.state.role not in {"owner", "admin"}:
            return
        self.team_page._create_invite()

    def _apply_filter(self, value: str) -> None:
        needle = str(value or "").strip().lower()
        for row in range(self.table.rowCount()):
            text = " ".join(
                str(self.table.item(row, col).text() if self.table.item(row, col) else "")
                for col in range(self.table.columnCount())
            ).lower()
            self.table.setRowHidden(row, bool(needle and needle not in text))

    def _selected_member(self) -> dict[str, object] | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        user_id = str(item.data(Qt.ItemDataRole.UserRole) or "") if item is not None else ""
        for member in self.team_page._members:
            if str(member.get("user_id") or "") == user_id:
                return member
        return None

    def _render_selected_member(self) -> None:
        member = self._selected_member()
        if member is None:
            self.detail_avatar.setText("—")
            self.detail_email.setText("Select a member")
            self.detail_role.setText("—")
            self.detail_status.setText("Status —")
            self.detail_joined.setText("Joined —")
            self.detail_devices.setText("Managed devices —")
            self.detail_device_list.setText("")
            return

        user_id = str(member.get("user_id") or "")
        email = str(member.get("email") or user_id or "Member")
        parts = email.replace("@", " ").replace(".", " ").split()
        initials = "".join(part[:1] for part in parts[:2]).upper() or "M"
        role = str(member.get("role") or "member").title()
        status = str(member.get("status") or "active").title()
        joined = str(member.get("joined_at") or "").replace("T", " ")[:16] or "—"
        devices = [row for row in self.team_page._devices if str(row.get("user_id") or "") == user_id]

        self.detail_avatar.setText(initials[:2])
        self.detail_email.setText(email)
        self.detail_role.setText(role.upper())
        self.detail_status.setText(f"Status · {status}")
        self.detail_joined.setText(f"Joined · {joined}")
        self.detail_devices.setText(f"Managed devices · {len(devices)}")
        if devices:
            lines = []
            for device in devices[:4]:
                name = str(device.get("display_name") or "Device")
                device_status = str(device.get("status") or "active").title()
                lines.append(f"• {name} · {device_status}")
            self.detail_device_list.setText("\n".join(lines))
        else:
            self.detail_device_list.setText("No managed endpoints returned for this member.")

    # ---------------------------------------------------------------- render
    def render(self) -> None:
        state = self.team_page.state
        members = list(self.team_page._members)
        devices = list(self.team_page._devices)
        active = [row for row in members if str(row.get("status") or "active").lower() == "active"]
        disabled = len(members) - len(active)
        leaders = sum(
            1
            for row in active
            if str(row.get("role") or "").lower() in {"owner", "admin", "manager"}
        )
        active_devices = [row for row in devices if str(row.get("status") or "active").lower() == "active"]

        self.summary_values["active"].setText(str(len(active)))
        self.summary_values["leaders"].setText(str(leaders))
        self.summary_values["disabled"].setText(str(disabled))
        self.summary_values["devices"].setText(str(len(active_devices)))

        limit = state.seat_limit
        self.seat_value.setText(f"{len(active)} / {limit if limit is not None else '—'}")
        if limit:
            pct = min(100, int(round(100 * len(active) / max(1, int(limit)))))
            self.seat_progress.setValue(pct)
            self.seat_note.setText(f"{max(0, int(limit) - len(active))} seat(s) available.")
        else:
            self.seat_progress.setValue(0)
            self.seat_note.setText("Seat limit unavailable for the current organization entitlement.")

        can_manage = state.role in {"owner", "admin"}
        can_view = state.role in {"owner", "admin", "manager"}
        self.invite_button.setVisible(can_manage)
        self.role_button.setVisible(can_manage)
        self.toggle_button.setVisible(can_manage)
        self.revoke_button.setVisible(can_manage)
        self.member_help.setText(
            "Owner/Admin can manage roles and access."
            if can_manage
            else "Read-only organization roster."
        )
        self.table.setVisible(can_view)

        if can_view:
            selected_id = ""
            current = self._selected_member()
            if current is not None:
                selected_id = str(current.get("user_id") or "")
            self.team_page._render_members()
            self._apply_filter(self.search.text())
            if selected_id:
                for row in range(self.table.rowCount()):
                    item = self.table.item(row, 0)
                    if item is not None and str(item.data(Qt.ItemDataRole.UserRole) or "") == selected_id:
                        self.table.selectRow(row)
                        break
            elif self.table.rowCount() > 0:
                self.table.selectRow(0)
            else:
                self._render_selected_member()
        else:
            self._render_selected_member()


def apply_mockup_team_members_2026(main_window) -> TeamMembersFinal | None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = getattr(team_page, "_privacygate_premium_dashboard", None) if team_page is not None else None
    if dashboard is None:
        return None
    existing = getattr(dashboard, "_privacygate_team_members_final_2026", None)
    if existing is not None:
        return existing

    stack = getattr(dashboard, "stack", None)
    if stack is None or stack.count() < 2:
        return None

    old = stack.widget(1)
    view = TeamMembersFinal(main_window, dashboard, dashboard)
    stack.removeWidget(old)
    old.hide()
    stack.insertWidget(1, view)
    dashboard._privacygate_team_members_final_2026 = view
    return view
