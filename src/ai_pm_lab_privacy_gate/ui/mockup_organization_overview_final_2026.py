from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.application.feature_suite import LocalActivityStore
from ai_pm_lab_privacy_gate.domain.company_policy import ProtectionDirective
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    AdaptiveGrid,
    AMBER,
    AMBER_SOFT,
    BLUE,
    BLUE_SOFT,
    BORDER,
    CANVAS,
    CoveragePlot,
    GREEN,
    GREEN_SOFT,
    INK,
    MUTED,
    PURPLE,
    PURPLE_SOFT,
    RED,
    RED_SOFT,
    StatusRing,
    TEAL,
    TEXT,
    WHITE,
    action_button,
    card,
    chip,
    clear_layout,
    heading,
    link_button,
    muted,
)
from ai_pm_lab_privacy_gate.ui.team_page import _CONNECTORS, _RULE_LABELS


SUCCESS_STATUSES = {"", "ok", "success", "protected", "ready", "allowed"}


def _format_when(raw: object) -> str:
    text = str(raw or "")
    if not text:
        return "—"
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return moment.strftime("%b %d · %H:%M")
    except ValueError:
        return text[:16]


def _friendly_event(value: str) -> str:
    key = str(value or "").strip().lower()
    mapping = {
        "document_scanned": "Document scanned",
        "library_saved": "Protected document saved",
        "batch_protected": "Batch protection completed",
        "ocr_completed": "Local OCR completed",
        "preflight_completed": "AI privacy preflight completed",
        "ai_handoff": "Protected AI handoff",
        "handoff_completed": "Protected AI handoff completed",
        "file_renamed": "Library item renamed",
        "file_moved": "Library item moved",
        "file_safe_deleted": "Library item moved to trash",
        "encrypted_backup_created": "Encrypted backup created",
    }
    return mapping.get(key, key.replace("_", " ").strip().title() or "PrivacyGate activity")


class _ResponsivePair(QWidget):
    def __init__(self, left: QWidget, right: QWidget, *, left_stretch: int = 1, right_stretch: int = 1, parent=None) -> None:
        super().__init__(parent)
        self.left = left
        self.right = right
        self.left_stretch = left_stretch
        self.right_stretch = right_stretch
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        self._stacked = False
        self._reflow(force=True)

    def _reflow(self, *, force: bool = False) -> None:
        stacked = self.width() < 850
        if stacked == self._stacked and not force:
            return
        self._stacked = stacked
        self.grid.removeWidget(self.left)
        self.grid.removeWidget(self.right)
        if stacked:
            self.grid.addWidget(self.left, 0, 0)
            self.grid.addWidget(self.right, 1, 0)
            self.grid.setColumnStretch(0, 1)
            self.grid.setColumnStretch(1, 0)
        else:
            self.grid.addWidget(self.left, 0, 0)
            self.grid.addWidget(self.right, 0, 1)
            self.grid.setColumnStretch(0, self.left_stretch)
            self.grid.setColumnStretch(1, self.right_stretch)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._reflow()


class OrganizationOverviewFinal(QWidget):
    """Organization dashboard using real TeamState and local metadata only.

    This is a reusable presentation layer. TeamPage/Supabase remains authoritative
    for membership, roles, invitations, policy and device actions; this view only
    summarizes those objects and delegates mutations to the existing controllers.
    """

    def __init__(self, main_window, dashboard, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.dashboard = dashboard
        self.team_page = dashboard.team_page
        self.activity = LocalActivityStore(main_window.library.data_dir)
        self.metric_cards: dict[str, dict[str, object]] = {}
        self.coverage_rows: dict[str, tuple[QLabel, QProgressBar, QLabel]] = {}
        self.team_values: dict[str, QLabel] = {}
        self._build()
        self.render()

        self.team_page.state_changed.connect(lambda _state: QTimer.singleShot(0, self.render))
        self.team_page.policy_changed.connect(lambda _policy: QTimer.singleShot(0, self.render))
        self.main_window.protection_page.library_changed.connect(lambda _doc: QTimer.singleShot(0, self.render))

    # -------------------------------------------------------------- navigation
    def _open_activity(self) -> None:
        controller = getattr(self.main_window, "_privacygate_redesign_sidebar_controller", None)
        callback = getattr(controller, "_open_activity", None) if controller is not None else None
        if callable(callback):
            callback()

    def _open_dashboard_tab(self, visual_index: int) -> None:
        selector = getattr(self.dashboard, "_select_tab", None)
        if callable(selector):
            selector(visual_index)

    def _refresh_org(self) -> None:
        refresh = getattr(self.team_page, "refresh", None)
        if callable(refresh):
            refresh()

    def _invite_member(self) -> None:
        button = getattr(self.team_page, "invite_button", None)
        if button is not None and button.isVisible() and button.isEnabled():
            button.click()

    # -------------------------------------------------------------------- build
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
        host.setObjectName("OrganizationOverviewFinalHost")
        host.setStyleSheet(f"QWidget#OrganizationOverviewFinalHost{{background:{CANVAS};}}")
        body = QVBoxLayout(host)
        body.setContentsMargins(28, 23, 28, 28)
        body.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        self.title = QLabel("Organization")
        self.title.setStyleSheet(
            f"color:{INK};font-size:30px;font-weight:950;background:transparent;border:none;"
        )
        self.subtitle = muted("Organization overview. Policy, people, endpoints and AI controls at a glance.", 10)
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)
        self.role_chip = chip("MEMBER", "neutral")
        self.plan_chip = chip("BUSINESS", "blue")
        header.addWidget(self.role_chip, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(self.plan_chip, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(link_button("Refresh", self._refresh_org), 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(header)

        metric_widgets = [
            self._policy_metric(),
            self._number_metric("protected", "Protected documents", "document", BLUE, BLUE_SOFT),
            self._number_metric("blocked", "Blocked actions", "protect", RED, RED_SOFT),
            self._device_metric(),
            self._number_metric("ai", "Recent AI use", "workflow", PURPLE, PURPLE_SOFT),
        ]
        body.addWidget(AdaptiveGrid(metric_widgets, max_columns=5))

        coverage = self._coverage_card()
        activity = self._activity_card()
        body.addWidget(_ResponsivePair(coverage, activity, left_stretch=6, right_stretch=5))

        risks = self._risks_card()
        team = self._team_card()
        body.addWidget(_ResponsivePair(risks, team, left_stretch=7, right_stretch=4))

        body.addStretch(1)
        scroll.setWidget(host)
        root.addWidget(scroll)

    def _metric_shell(self, key: str, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = card(f"OrgFinalMetric_{key}")
        frame.setMinimumHeight(172)
        box = QVBoxLayout(frame)
        box.setContentsMargins(15, 14, 15, 13)
        box.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(heading(title, 10))
        top.addStretch(1)
        box.addLayout(top)
        self.metric_cards[key] = {"frame": frame, "layout": box}
        return frame, box

    def _policy_metric(self) -> QFrame:
        frame, box = self._metric_shell("policy", "Policy status")
        content = QHBoxLayout()
        content.setSpacing(11)
        ring = StatusRing(color=GREEN, diameter=98)
        self.metric_cards["policy"]["ring"] = ring
        content.addWidget(ring)
        details = QVBoxLayout()
        details.setSpacing(5)
        version = QLabel("—")
        version.setStyleSheet(f"color:{INK};font-size:18px;font-weight:900;border:none;")
        required = muted("No company policy", 8)
        ai = muted("AI controls unavailable", 8)
        details.addWidget(version)
        details.addWidget(required)
        details.addWidget(ai)
        details.addStretch(1)
        content.addLayout(details, 1)
        box.addLayout(content)
        box.addStretch(1)
        self.metric_cards["policy"].update({"value": version, "detail1": required, "detail2": ai})
        footer = link_button("View policy center", lambda: self._open_dashboard_tab(2))
        box.addWidget(footer, 0, Qt.AlignmentFlag.AlignLeft)
        return frame

    def _number_metric(self, key: str, title: str, icon_name: str, color: str, soft: str) -> QFrame:
        frame, box = self._metric_shell(key, title)
        row = QHBoxLayout()
        row.setSpacing(11)
        bubble = QLabel()
        bubble.setFixedSize(42, 42)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setPixmap(icon(icon_name, color=color, size=22).pixmap(22, 22))
        bubble.setStyleSheet(f"background:{soft};border:none;border-radius:12px;")
        row.addWidget(bubble)
        value = QLabel("0")
        value.setStyleSheet(f"color:{INK};font-size:25px;font-weight:950;border:none;")
        row.addWidget(value)
        row.addStretch(1)
        box.addLayout(row)
        detail1 = muted("No local organization activity yet", 8)
        detail2 = muted("", 8)
        box.addWidget(detail1)
        box.addWidget(detail2)
        box.addStretch(1)
        self.metric_cards[key].update({"value": value, "detail1": detail1, "detail2": detail2})
        if key == "protected":
            box.addWidget(link_button("View activity", self._open_activity), 0, Qt.AlignmentFlag.AlignLeft)
        elif key == "blocked":
            box.addWidget(link_button("Review activity", self._open_activity), 0, Qt.AlignmentFlag.AlignLeft)
        elif key == "ai":
            box.addWidget(link_button("View AI use activity", self._open_activity), 0, Qt.AlignmentFlag.AlignLeft)
        return frame

    def _device_metric(self) -> QFrame:
        frame, box = self._metric_shell("devices", "Device compliance")
        content = QHBoxLayout()
        content.setSpacing(11)
        ring = StatusRing(color=GREEN, diameter=98)
        self.metric_cards["devices"]["ring"] = ring
        content.addWidget(ring)
        details = QVBoxLayout()
        details.setSpacing(5)
        compliant = QLabel("—")
        compliant.setStyleSheet(f"color:{INK};font-size:18px;font-weight:900;border:none;")
        active = muted("No managed devices", 8)
        review = muted("", 8)
        details.addWidget(compliant)
        details.addWidget(active)
        details.addWidget(review)
        details.addStretch(1)
        content.addLayout(details, 1)
        box.addLayout(content)
        box.addStretch(1)
        self.metric_cards["devices"].update({"value": compliant, "detail1": active, "detail2": review})
        box.addWidget(link_button("View devices", lambda: self._open_dashboard_tab(4)), 0, Qt.AlignmentFlag.AlignLeft)
        return frame

    def _coverage_card(self) -> QFrame:
        frame = card("OrgFinalCoverage")
        frame.setMinimumHeight(320)
        box = QVBoxLayout(frame)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(11)
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.addWidget(heading("Protection coverage", 13))
        title_box.addWidget(muted("Current organization control coverage. The graph uses real policy/device categories, not invented history.", 8.5))
        top.addLayout(title_box, 1)
        self.coverage_chip = chip("NO POLICY", "neutral")
        top.addWidget(self.coverage_chip, 0, Qt.AlignmentFlag.AlignTop)
        box.addLayout(top)

        content = QHBoxLayout()
        content.setSpacing(18)
        left = QVBoxLayout()
        overall_row = QHBoxLayout()
        overall_caption = muted("Overall coverage", 8.5)
        self.coverage_overall = QLabel("—")
        self.coverage_overall.setStyleSheet(f"color:{INK};font-size:28px;font-weight:950;border:none;")
        self.coverage_grade = QLabel("")
        self.coverage_grade.setStyleSheet(f"color:{GREEN};font-size:9px;font-weight:850;border:none;")
        overall_row.addWidget(overall_caption)
        overall_row.addStretch(1)
        overall_row.addWidget(self.coverage_overall)
        overall_row.addWidget(self.coverage_grade)
        left.addLayout(overall_row)
        self.coverage_plot = CoveragePlot()
        left.addWidget(self.coverage_plot, 1)
        content.addLayout(left, 6)

        right = QVBoxLayout()
        right.setSpacing(8)
        for key, title in (
            ("data", "Sensitive-data rules"),
            ("ai", "AI controls"),
            ("apps", "Connected-app controls"),
            ("devices", "Managed-device compliance"),
        ):
            title_row = QHBoxLayout()
            label = QLabel(title)
            label.setStyleSheet(f"color:{TEXT};font-size:8.5px;font-weight:800;border:none;")
            value = QLabel("—")
            value.setStyleSheet(f"color:{INK};font-size:9px;font-weight:850;border:none;")
            title_row.addWidget(label, 1)
            title_row.addWidget(value)
            right.addLayout(title_row)
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(0)
            progress.setTextVisible(False)
            progress.setFixedHeight(8)
            progress.setStyleSheet(
                "QProgressBar{background:#EAECF0;border:none;border-radius:4px;}"
                f"QProgressBar::chunk{{background:{GREEN};border-radius:4px;}}"
            )
            right.addWidget(progress)
            detail = muted("", 7.5)
            right.addWidget(detail)
            self.coverage_rows[key] = (value, progress, detail)
        right.addStretch(1)
        content.addLayout(right, 4)
        box.addLayout(content, 1)
        return frame

    def _activity_card(self) -> QFrame:
        frame = card("OrgFinalActivity")
        frame.setMinimumHeight(320)
        box = QVBoxLayout(frame)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(heading("Recent activity", 13))
        top.addStretch(1)
        top.addWidget(link_button("View all", self._open_activity))
        box.addLayout(top)
        self.activity_rows = QVBoxLayout()
        self.activity_rows.setSpacing(0)
        box.addLayout(self.activity_rows, 1)
        return frame

    def _risks_card(self) -> QFrame:
        frame = card("OrgFinalRisks")
        frame.setMinimumHeight(310)
        box = QVBoxLayout(frame)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(8)
        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(heading("Top risks to monitor", 13))
        titles.addWidget(muted("Derived from policy scope, seat usage, access state, endpoint sync and local metadata events.", 8.5))
        top.addLayout(titles, 1)
        top.addWidget(link_button("Policy center", lambda: self._open_dashboard_tab(2)), 0, Qt.AlignmentFlag.AlignTop)
        box.addLayout(top)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Risk", "Category", "Impact", "Status", "Observed"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setShowGrid(False)
        table.setMinimumHeight(190)
        table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#344054;border:none;}"
            "QTableWidget::item{padding:8px;border-bottom:1px solid #F2F4F7;font-size:8.5px;}"
            "QHeaderView::section{background:#FFFFFF;color:#667085;border:none;border-bottom:1px solid #EAECF0;"
            "padding:8px;font-size:7.5px;font-weight:850;}"
        )
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.risks_table = table
        box.addWidget(table, 1)
        return frame

    def _team_card(self) -> QFrame:
        frame = card("OrgFinalTeam")
        frame.setMinimumHeight(310)
        box = QVBoxLayout(frame)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(10)
        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(heading("Team at a glance", 13))
        titles.addWidget(muted("Roles, access, seats and managed endpoints.", 8.5))
        top.addLayout(titles, 1)
        top.addWidget(link_button("Manage", lambda: self._open_dashboard_tab(1)), 0, Qt.AlignmentFlag.AlignTop)
        box.addLayout(top)

        seat_row = QHBoxLayout()
        self.seat_label = QLabel("Seats")
        self.seat_label.setStyleSheet(f"color:{TEXT};font-size:8.5px;font-weight:800;border:none;")
        self.seat_value = QLabel("—")
        self.seat_value.setStyleSheet(f"color:{INK};font-size:9px;font-weight:900;border:none;")
        seat_row.addWidget(self.seat_label)
        seat_row.addStretch(1)
        seat_row.addWidget(self.seat_value)
        box.addLayout(seat_row)
        self.seat_progress = QProgressBar()
        self.seat_progress.setRange(0, 100)
        self.seat_progress.setTextVisible(False)
        self.seat_progress.setFixedHeight(8)
        self.seat_progress.setStyleSheet(
            "QProgressBar{background:#EAECF0;border:none;border-radius:4px;}"
            f"QProgressBar::chunk{{background:{BLUE};border-radius:4px;}}"
        )
        box.addWidget(self.seat_progress)

        summary = QGridLayout()
        summary.setHorizontalSpacing(10)
        summary.setVerticalSpacing(8)
        for index, (key, title, icon_name, tone) in enumerate(
            (
                ("members", "Active members", "contact", BLUE),
                ("leaders", "Admins / managers", "settings", PURPLE),
                ("disabled", "Disabled access", "history", AMBER),
                ("devices", "Managed devices", "document", TEAL),
            )
        ):
            mini = QFrame()
            mini.setStyleSheet("QFrame{background:#F8FAFC;border:1px solid #EAECF0;border-radius:10px;}")
            mini_box = QHBoxLayout(mini)
            mini_box.setContentsMargins(9, 8, 9, 8)
            ico = QLabel()
            ico.setPixmap(icon(icon_name, color=tone, size=16).pixmap(16, 16))
            mini_box.addWidget(ico)
            copy = QVBoxLayout()
            copy.setSpacing(1)
            name = QLabel(title)
            name.setStyleSheet(f"color:{MUTED};font-size:7px;border:none;")
            value = QLabel("0")
            value.setStyleSheet(f"color:{INK};font-size:12px;font-weight:900;border:none;")
            copy.addWidget(name)
            copy.addWidget(value)
            mini_box.addLayout(copy, 1)
            summary.addWidget(mini, index // 2, index % 2)
            self.team_values[key] = value
        box.addLayout(summary)

        roster_title = QHBoxLayout()
        roster_title.addWidget(QLabel("Member preview"))
        roster_title.itemAt(0).widget().setStyleSheet(f"color:{TEXT};font-size:8px;font-weight:850;border:none;")
        roster_title.addStretch(1)
        box.addLayout(roster_title)
        self.roster_layout = QVBoxLayout()
        self.roster_layout.setSpacing(0)
        box.addLayout(self.roster_layout, 1)

        actions = QHBoxLayout()
        manage = action_button("Manage team", lambda: self._open_dashboard_tab(1))
        self.invite_action = action_button("Invite member", self._invite_member, primary=True)
        actions.addWidget(manage)
        actions.addWidget(self.invite_action)
        actions.addStretch(1)
        box.addLayout(actions)
        return frame

    # ------------------------------------------------------------------- data
    def _activity_items(self) -> list[dict[str, object]]:
        try:
            rows = list(self.activity.recent(300))
        except Exception:
            return []
        store = getattr(self.team_page, "_privacygate_workspace_store", None)
        active_key = ""
        if store is not None:
            try:
                active_key = str(store.load().active_key or "")
            except Exception:
                active_key = ""
        if not active_key:
            organization_id = str(self.team_page.state.organization_id or "")
            active_key = f"org:{organization_id}" if organization_id else "personal"
        return [row for row in rows if str(row.get("workspace_key") or "") == active_key]

    @staticmethod
    def _event_counts(rows: list[dict[str, object]]) -> tuple[int, int, int, int]:
        protected = blocked = ai_use = scans = 0
        for row in rows:
            event = str(row.get("event_type") or "").lower()
            status = str(row.get("status") or "").lower()
            detail = str(row.get("detail") or "").lower()
            if any(token in event for token in ("protect", "library_saved", "batch_protected")):
                protected += 1
            if "scan" in event or "preflight" in event:
                scans += 1
            if status not in SUCCESS_STATUSES or "block" in event or "blocked" in detail:
                blocked += 1
            if any(token in event for token in ("ai", "preflight", "handoff")):
                ai_use += 1
        return protected, blocked, ai_use, scans

    def _coverage_values(self, policy, devices: list[dict[str, object]]) -> tuple[dict[str, int | None], dict[str, str], int | None]:
        if policy is None:
            values = {"data": 0, "ai": 0, "apps": 0, "devices": None if not devices else 0}
            details = {
                "data": "Company policy unavailable",
                "ai": "Company policy unavailable",
                "apps": "Company policy unavailable",
                "devices": "No managed devices" if not devices else "No active policy to verify",
            }
            return values, details, 0

        expected_rules = max(1, len(_RULE_LABELS))
        configured_rules = sum(1 for key in _RULE_LABELS if key in policy.protection_rules)
        data_pct = int(round(100 * configured_rules / expected_rules))

        expected_ai = ("chatgpt", "claude", "other")
        configured_ai = sum(1 for key in expected_ai if key in policy.allowed_ai)
        ai_pct = int(round(100 * configured_ai / len(expected_ai)))

        connector_keys = {key for key, _label in _CONNECTORS}
        if "*" in policy.allowed_connectors:
            apps_pct = 100
            apps_detail = "Wildcard/default connector control configured"
        else:
            configured_apps = sum(1 for key in connector_keys if key in policy.allowed_connectors)
            apps_pct = int(round(100 * configured_apps / max(1, len(connector_keys))))
            apps_detail = f"{configured_apps} of {len(connector_keys)} catalog controls configured"

        active_devices = [row for row in devices if str(row.get("status") or "active").lower() == "active"]
        if not active_devices:
            device_pct: int | None = None
            device_detail = "No active managed devices"
        else:
            compliant = sum(1 for row in active_devices if int(row.get("last_policy_version") or 0) == int(policy.version))
            device_pct = int(round(100 * compliant / len(active_devices)))
            device_detail = f"{compliant} of {len(active_devices)} active devices on policy v{policy.version}"

        values = {"data": data_pct, "ai": ai_pct, "apps": apps_pct, "devices": device_pct}
        details = {
            "data": f"{configured_rules} of {expected_rules} sensitive-data controls configured",
            "ai": f"{configured_ai} of {len(expected_ai)} AI destination controls configured",
            "apps": apps_detail,
            "devices": device_detail,
        }
        applicable = [value for value in values.values() if value is not None]
        overall = int(round(sum(applicable) / len(applicable))) if applicable else None
        return values, details, overall

    # ------------------------------------------------------------------ render
    def _render_activity(self, rows: list[dict[str, object]]) -> None:
        clear_layout(self.activity_rows)
        if not rows:
            empty = muted("No organization activity has been recorded on this device yet.", 9)
            empty.setMinimumHeight(190)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.activity_rows.addWidget(empty)
            return

        colors = (GREEN, BLUE, PURPLE, AMBER, TEAL)
        for index, row in enumerate(rows[:6]):
            line = QFrame()
            line.setMinimumHeight(43)
            line.setStyleSheet("QFrame{background:transparent;border:none;border-bottom:1px solid #F2F4F7;}")
            layout = QHBoxLayout(line)
            layout.setContentsMargins(1, 8, 1, 8)
            layout.setSpacing(9)
            status = str(row.get("status") or "").lower()
            tone = RED if status not in SUCCESS_STATUSES else colors[index % len(colors)]
            ico = QLabel()
            ico.setPixmap(icon("history", color=tone, size=16).pixmap(16, 16))
            layout.addWidget(ico)
            label = QLabel(_friendly_event(str(row.get("event_type") or "")))
            label.setStyleSheet(f"color:{TEXT};font-size:8.5px;font-weight:700;border:none;")
            layout.addWidget(label, 1)
            when = QLabel(_format_when(row.get("created_at")))
            when.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;")
            layout.addWidget(when)
            self.activity_rows.addWidget(line)
        self.activity_rows.addStretch(1)

    def _set_coverage(self, key: str, value: int | None, detail: str) -> None:
        label, progress, detail_label = self.coverage_rows[key]
        if value is None:
            label.setText("N/A")
            progress.setValue(0)
            detail_label.setText(detail)
            return
        label.setText(f"{value}%")
        progress.setValue(value)
        detail_label.setText(detail)

    def _render_risks(
        self,
        *,
        policy,
        coverage: dict[str, int | None],
        active_members: list[dict[str, object]],
        inactive_members: int,
        devices: list[dict[str, object]],
        blocked: int,
        activity_rows: list[dict[str, object]],
    ) -> None:
        risks: list[tuple[str, str, str, str, str]] = []
        observed = _format_when(activity_rows[0].get("created_at")) if activity_rows else "Current"

        if policy is None:
            risks.append(("Company policy unavailable", "Policy", "High", "Action required", "Current"))
        else:
            if int(coverage.get("data") or 0) < 100:
                risks.append(("Sensitive-data policy scope incomplete", "Data", "Medium", "Review", "Current"))
            if int(coverage.get("ai") or 0) < 100:
                risks.append(("AI control scope incomplete", "AI", "Medium", "Review", "Current"))
            device_pct = coverage.get("devices")
            if device_pct is not None and device_pct < 100:
                risks.append(("Managed devices not fully synced", "Endpoint", "High" if device_pct < 70 else "Medium", "Active", "Current"))

        if inactive_members:
            risks.append((f"{inactive_members} disabled/revoked membership(s)", "Access", "Medium", "Review", "Current"))

        limit = self.team_page.state.seat_limit
        if limit:
            usage = len(active_members) / max(1, int(limit))
            if usage >= 0.9:
                risks.append(("Organization seats nearly full", "Capacity", "Medium", "Monitor", "Current"))

        inactive_devices = sum(1 for row in devices if str(row.get("status") or "active").lower() != "active")
        if inactive_devices:
            risks.append((f"{inactive_devices} managed device(s) inactive", "Endpoint", "Medium", "Review", "Current"))
        if blocked:
            risks.append((f"{blocked} blocked/failed local event(s)", "Activity", "Medium", "Monitor", observed))
        if not risks:
            risks.append(("No elevated risk derived from current metadata", "Workspace", "Low", "Normal", "Current"))

        self.risks_table.setRowCount(min(5, len(risks)))
        for row_index, values in enumerate(risks[:5]):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 2:
                    if value == "High":
                        item.setForeground(Qt.GlobalColor.red)
                    elif value == "Medium":
                        item.setForeground(Qt.GlobalColor.darkYellow)
                self.risks_table.setItem(row_index, column, item)

    def _render_roster(self, members: list[dict[str, object]], can_view_roster: bool) -> None:
        clear_layout(self.roster_layout)
        if not can_view_roster:
            note = muted("Member roster is private unless your role is Manager, Admin or Owner.", 8)
            note.setMinimumHeight(48)
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.roster_layout.addWidget(note)
            return
        if not members:
            note = muted("No organization members returned by the current sync.", 8)
            note.setMinimumHeight(48)
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.roster_layout.addWidget(note)
            return

        for member in members[:4]:
            row = QFrame()
            row.setStyleSheet("QFrame{background:transparent;border:none;border-bottom:1px solid #F2F4F7;}")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 7, 0, 7)
            layout.setSpacing(9)
            email = str(member.get("email") or member.get("user_id") or "Member")
            initials_text = "".join(part[:1] for part in email.replace("@", " ").replace(".", " ").split()[:2]).upper() or "M"
            avatar = QLabel(initials_text[:2])
            avatar.setFixedSize(28, 28)
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar.setStyleSheet("background:#EEF4FF;color:#2563EB;border:none;border-radius:14px;font-size:8px;font-weight:900;")
            layout.addWidget(avatar)
            copy = QVBoxLayout()
            copy.setSpacing(1)
            name = QLabel(email)
            name.setStyleSheet(f"color:{INK};font-size:8px;font-weight:800;border:none;")
            role = str(member.get("role") or "member").title()
            status = str(member.get("status") or "active").title()
            meta = QLabel(f"{role} · {status}")
            meta.setStyleSheet(f"color:{MUTED};font-size:7px;border:none;")
            copy.addWidget(name)
            copy.addWidget(meta)
            layout.addLayout(copy, 1)
            tone = GREEN if status.lower() == "active" else AMBER
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{tone};font-size:8px;border:none;")
            layout.addWidget(dot)
            self.roster_layout.addWidget(row)

    def render(self) -> None:
        state = self.team_page.state
        if not state.organization_id:
            return

        policy = state.policy
        members = list(self.team_page._members)
        devices = list(self.team_page._devices)
        active_members = [row for row in members if str(row.get("status") or "active").lower() == "active"]
        inactive_members = max(0, len(members) - len(active_members))
        admins = sum(1 for row in active_members if str(row.get("role") or "").lower() in {"owner", "admin"})
        managers = sum(1 for row in active_members if str(row.get("role") or "").lower() == "manager")
        leaders = admins + managers
        active_devices = [row for row in devices if str(row.get("status") or "active").lower() == "active"]

        organization_name = state.organization_name or (policy.organization_name if policy else "Organization")
        self.title.setText(organization_name)
        self.subtitle.setText("Organization overview. Policy, people, endpoints and AI controls at a glance.")
        self.role_chip.setText((state.role or "member").upper())
        self.plan_chip.setText(state.plan.label.upper())

        activity_rows = self._activity_items()
        protected, blocked, ai_use, scans = self._event_counts(activity_rows)

        # Policy metric
        policy_ring = self.metric_cards["policy"]["ring"]
        if policy is not None and state.membership_status == "active":
            policy_ring.set_status(100, caption="ACTIVE", color=GREEN)
            self.metric_cards["policy"]["value"].setText(f"Policy v{policy.version}")
            required = sum(1 for directive in policy.protection_rules.values() if directive is ProtectionDirective.REQUIRED_PROTECT)
            enabled_ai = sum(1 for allowed in policy.allowed_ai.values() if allowed)
            self.metric_cards["policy"]["detail1"].setText(f"{required} mandatory protection rule(s)")
            self.metric_cards["policy"]["detail2"].setText(f"{enabled_ai} approved AI destination(s)")
        else:
            policy_ring.set_status(0, caption="REVIEW", color=RED)
            self.metric_cards["policy"]["value"].setText("No active policy")
            self.metric_cards["policy"]["detail1"].setText("Policy sync required")
            self.metric_cards["policy"]["detail2"].setText("")

        # Local organization event metrics
        self.metric_cards["protected"]["value"].setText(str(protected))
        self.metric_cards["protected"]["detail1"].setText("Protected activity recorded for this organization on this device")
        self.metric_cards["protected"]["detail2"].setText(f"{scans} scan/preflight event(s)")

        self.metric_cards["blocked"]["value"].setText(str(blocked))
        self.metric_cards["blocked"]["detail1"].setText("Blocked or failed local metadata events")
        self.metric_cards["blocked"]["detail2"].setText("No document content is included")

        self.metric_cards["ai"]["value"].setText(str(ai_use))
        enabled_ai = sum(1 for allowed in policy.allowed_ai.values() if allowed) if policy else 0
        restricted_ai = sum(1 for allowed in policy.allowed_ai.values() if not allowed) if policy else 0
        self.metric_cards["ai"]["detail1"].setText("AI/preflight/handoff metadata events")
        self.metric_cards["ai"]["detail2"].setText(f"{enabled_ai} approved · {restricted_ai} restricted by policy" if policy else "Policy unavailable")

        # Coverage and device compliance
        coverage, coverage_details, overall = self._coverage_values(policy, devices)
        if policy:
            self.coverage_chip.setText(f"POLICY v{policy.version}")
            self.coverage_chip.setStyleSheet(
                f"background:{GREEN_SOFT};color:{GREEN};border:1px solid #BBF7D0;border-radius:8px;"
                "padding:4px 8px;font-size:7.5px;font-weight:850;"
            )
        else:
            self.coverage_chip.setText("NO POLICY")
        self.coverage_overall.setText("N/A" if overall is None else f"{overall}%")
        if overall is None:
            self.coverage_grade.setText("")
        elif overall >= 90:
            self.coverage_grade.setText("Excellent")
            self.coverage_grade.setStyleSheet(f"color:{GREEN};font-size:9px;font-weight:850;border:none;")
        elif overall >= 70:
            self.coverage_grade.setText("Review")
            self.coverage_grade.setStyleSheet(f"color:{AMBER};font-size:9px;font-weight:850;border:none;")
        else:
            self.coverage_grade.setText("Needs attention")
            self.coverage_grade.setStyleSheet(f"color:{RED};font-size:9px;font-weight:850;border:none;")

        plot_values = [("Data", coverage["data"] or 0), ("AI", coverage["ai"] or 0), ("Apps", coverage["apps"] or 0)]
        if coverage["devices"] is not None:
            plot_values.append(("Devices", int(coverage["devices"] or 0)))
        self.coverage_plot.set_values(plot_values)
        for key in ("data", "ai", "apps", "devices"):
            self._set_coverage(key, coverage[key], coverage_details[key])

        device_ring = self.metric_cards["devices"]["ring"]
        if not active_devices:
            device_ring.set_status(None, center="—", caption="NO DEVICES", color=TEAL)
            self.metric_cards["devices"]["value"].setText("No devices")
            self.metric_cards["devices"]["detail1"].setText("No active managed endpoints")
            self.metric_cards["devices"]["detail2"].setText("")
        else:
            device_pct = int(coverage["devices"] or 0)
            compliant = sum(1 for row in active_devices if policy is not None and int(row.get("last_policy_version") or 0) == int(policy.version)) if policy else 0
            review_count = max(0, len(active_devices) - compliant)
            device_ring.set_status(device_pct, caption="COMPLIANT" if device_pct == 100 else "REVIEW", color=GREEN if device_pct == 100 else AMBER)
            self.metric_cards["devices"]["value"].setText(f"{compliant} compliant")
            self.metric_cards["devices"]["detail1"].setText(f"{len(active_devices)} active managed device(s)")
            self.metric_cards["devices"]["detail2"].setText(f"{review_count} need review" if review_count else "All active devices on current policy")

        self._render_activity(activity_rows)
        self._render_risks(
            policy=policy,
            coverage=coverage,
            active_members=active_members,
            inactive_members=inactive_members,
            devices=devices,
            blocked=blocked,
            activity_rows=activity_rows,
        )

        # Team / access system
        can_view_roster = state.role in {"owner", "admin", "manager"}
        self.team_values["members"].setText(str(len(active_members)) if can_view_roster else "Private")
        self.team_values["leaders"].setText(str(leaders) if can_view_roster else "—")
        self.team_values["disabled"].setText(str(inactive_members) if can_view_roster else "—")
        self.team_values["devices"].setText(str(len(devices)) if can_view_roster else "This device")

        seat_limit = state.seat_limit
        if can_view_roster and seat_limit:
            used = len(active_members)
            percent = int(round(100 * used / max(1, int(seat_limit))))
            self.seat_value.setText(f"{used} / {seat_limit}")
            self.seat_progress.setValue(min(100, percent))
        elif can_view_roster:
            self.seat_value.setText(f"{len(active_members)} / —")
            self.seat_progress.setValue(0)
        else:
            self.seat_value.setText("Managed by organization")
            self.seat_progress.setValue(0)

        self._render_roster(members, can_view_roster)
        self.invite_action.setVisible(state.role in {"owner", "admin"})
        self.invite_action.setEnabled(state.role in {"owner", "admin"})


def apply_mockup_organization_overview_final_2026(main_window) -> OrganizationOverviewFinal | None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = getattr(team_page, "_privacygate_premium_dashboard", None) if team_page is not None else None
    if team_page is None or dashboard is None:
        return None

    existing = getattr(dashboard, "_privacygate_organization_overview_final_2026", None)
    if existing is not None:
        return existing

    stack = getattr(dashboard, "stack", None)
    if stack is None or stack.count() == 0:
        return None

    old = stack.widget(0)
    view = OrganizationOverviewFinal(main_window, dashboard, dashboard)
    stack.removeWidget(old)
    old.hide()
    stack.insertWidget(0, view)
    dashboard.overview = view
    dashboard._privacygate_organization_overview_final_2026 = view
    if stack.currentIndex() == 0:
        stack.setCurrentIndex(0)
    dashboard._style_tabs(0)
    return view
