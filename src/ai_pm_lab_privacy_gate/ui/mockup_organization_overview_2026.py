from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
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
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.application.feature_suite import LocalActivityStore
from ai_pm_lab_privacy_gate.domain.company_policy import ProtectionDirective
from ai_pm_lab_privacy_gate.ui.iconography import icon


BLUE = "#2563EB"
BLUE_SOFT = "#EEF4FF"
INK = "#101828"
TEXT = "#344054"
MUTED = "#667085"
BORDER = "#E4E7EC"
BG = "#F7F9FC"
WHITE = "#FFFFFF"
GREEN = "#16A34A"
GREEN_SOFT = "#ECFDF3"
AMBER = "#D97706"
AMBER_SOFT = "#FFF7ED"
RED = "#DC2626"
RED_SOFT = "#FEF2F2"
PURPLE = "#7C3AED"
PURPLE_SOFT = "#F5F3FF"


class _Ring(QWidget):
    def __init__(self, *, color: str = GREEN, parent=None) -> None:
        super().__init__(parent)
        self._value = 0
        self._label = ""
        self._color = QColor(color)
        self.setFixedSize(82, 82)

    def set_value(self, value: int, label: str = "") -> None:
        self._value = max(0, min(100, int(value)))
        self._label = label
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(8, 8, 66, 66)
        base = QPen(QColor("#EAECF0"), 7)
        base.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(base)
        painter.drawArc(rect, 0, 360 * 16)
        progress = QPen(self._color, 7)
        progress.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(progress)
        painter.drawArc(rect, 90 * 16, -int(360 * 16 * self._value / 100))
        painter.setPen(QColor(INK))
        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(8, 23, 66, 22), Qt.AlignmentFlag.AlignCenter, f"{self._value}%")
        if self._label:
            painter.setPen(self._color)
            font.setPointSize(6)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(7, 45, 68, 14), Qt.AlignmentFlag.AlignCenter, self._label)
        painter.end()


def _card(name: str = "MockupOrgCard") -> QFrame:
    frame = QFrame(objectName=name)
    frame.setStyleSheet(
        f"QFrame#{name}{{background:{WHITE};border:1px solid {BORDER};border-radius:14px;}}"
    )
    return frame


def _heading(text: str, size: int = 11) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color:{INK};font-size:{size}px;font-weight:850;background:transparent;border:none;"
    )
    return label


def _muted(text: str = "", size: int = 8) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        f"color:{MUTED};font-size:{size}px;background:transparent;border:none;"
    )
    return label


def _chip(text: str, tone: str = "blue") -> QLabel:
    colors = {
        "blue": (BLUE_SOFT, BLUE, "#D6E4FF"),
        "green": (GREEN_SOFT, GREEN, "#BBF7D0"),
        "amber": (AMBER_SOFT, AMBER, "#FED7AA"),
        "red": (RED_SOFT, RED, "#FECACA"),
        "purple": (PURPLE_SOFT, PURPLE, "#DDD6FE"),
        "neutral": ("#F2F4F7", "#475467", "#E4E7EC"),
    }
    bg, fg, border = colors.get(tone, colors["neutral"])
    label = QLabel(text)
    label.setStyleSheet(
        f"background:{bg};color:{fg};border:1px solid {border};border-radius:8px;"
        "padding:4px 8px;font-size:7px;font-weight:850;"
    )
    return label


def _friendly_event(value: str) -> str:
    key = str(value or "").strip().lower()
    mapping = {
        "library_saved": "Protected document saved locally",
        "batch_protected": "Batch document protected",
        "ocr_completed": "Local OCR completed",
        "preflight_completed": "Privacy preflight completed",
        "file_renamed": "Workspace item renamed",
        "file_moved": "Workspace item moved",
        "file_safe_deleted": "Workspace item moved to local trash",
        "encrypted_backup_created": "Encrypted backup created",
    }
    if key in mapping:
        return mapping[key]
    return key.replace("_", " ").strip().title() or "PrivacyGate activity"


def _format_when(raw: object) -> str:
    text = str(raw or "")
    if not text:
        return "—"
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return moment.strftime("%b %d · %H:%M")
    except ValueError:
        return text[:16]


class MockupOrganizationOverview(QWidget):
    """Visual-only Organization Overview based on the approved mockup.

    The view consumes existing TeamState/member/device/activity objects and never
    becomes a security or persistence boundary. Existing Organization controllers
    remain authoritative for all actions.
    """

    def __init__(self, main_window, dashboard, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.dashboard = dashboard
        self.team_page = dashboard.team_page
        self.activity = LocalActivityStore(main_window.library.data_dir)
        self.metric_values: dict[str, QLabel] = {}
        self.metric_details: dict[str, QLabel] = {}
        self.metric_rings: dict[str, _Ring] = {}
        self._build()
        self.render()
        self.team_page.state_changed.connect(lambda _state: QTimer.singleShot(0, self.render))
        self.team_page.policy_changed.connect(lambda _policy: QTimer.singleShot(0, self.render))
        main_window.protection_page.library_changed.connect(lambda _doc: QTimer.singleShot(0, self.render))

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea{{background:{BG};border:none;}}"
            "QScrollBar:vertical{background:transparent;width:7px;margin:2px;}"
            "QScrollBar::handle:vertical{background:#D0D5DD;border-radius:3px;min-height:28px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
        host = QWidget()
        host.setObjectName("MockupOrganizationOverviewHost")
        host.setStyleSheet(f"QWidget#MockupOrganizationOverviewHost{{background:{BG};}}")
        body = QVBoxLayout(host)
        body.setContentsMargins(22, 18, 22, 22)
        body.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title = QLabel("Organization")
        self.title.setStyleSheet(
            f"color:{INK};font-size:25px;font-weight:900;background:transparent;border:none;"
        )
        self.subtitle = _muted("Organization overview. Your policy, members and managed devices at a glance.", 9)
        title_box.addWidget(self.title)
        title_box.addWidget(self.subtitle)
        header.addLayout(title_box, 1)
        self.role_chip = _chip("MEMBER", "neutral")
        self.plan_chip = _chip("BUSINESS", "blue")
        header.addWidget(self.role_chip, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(self.plan_chip, 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(header)

        top = QGridLayout()
        top.setHorizontalSpacing(10)
        top.setVerticalSpacing(10)
        specs = (
            ("policy", "Policy status", "protect", "green"),
            ("protected", "Protected documents", "document", "blue"),
            ("blocked", "Blocked actions", "protect", "red"),
            ("devices", "Device compliance", "document", "green"),
            ("ai", "Recent AI use", "workflow", "purple"),
        )
        for column, spec in enumerate(specs):
            card = self._metric_card(*spec)
            top.addWidget(card, 0, column)
            top.setColumnStretch(column, 1)
        body.addLayout(top)

        middle = QHBoxLayout()
        middle.setSpacing(12)
        middle.addWidget(self._coverage_card(), 6)
        middle.addWidget(self._activity_card(), 5)
        body.addLayout(middle)

        lower = QHBoxLayout()
        lower.setSpacing(12)
        lower.addWidget(self._risks_card(), 7)
        lower.addWidget(self._team_card(), 3)
        body.addLayout(lower)

        privacy = QFrame(objectName="MockupPrivacyBoundary")
        privacy.setStyleSheet(
            "QFrame#MockupPrivacyBoundary{background:#F8FAFC;border:1px solid #E4E7EC;border-radius:12px;}"
        )
        row = QHBoxLayout(privacy)
        row.setContentsMargins(13, 10, 13, 10)
        shield = QLabel()
        shield.setPixmap(icon("protect", color=BLUE, size=18).pixmap(18, 18))
        row.addWidget(shield)
        note = _muted(
            "Organization shows control-plane and local metadata only. Document content, restore mappings and connector tokens remain on employee devices.",
            8,
        )
        row.addWidget(note, 1)
        body.addWidget(privacy)
        body.addStretch(1)

        scroll.setWidget(host)
        root.addWidget(scroll)

    def _metric_card(self, key: str, title: str, icon_name: str, tone: str) -> QFrame:
        card = _card(f"MockupMetric_{key}")
        card.setMinimumHeight(135)
        box = QVBoxLayout(card)
        box.setContentsMargins(13, 11, 13, 10)
        box.setSpacing(5)
        box.addWidget(_heading(title, 9))

        center = QHBoxLayout()
        center.setSpacing(8)
        if key in {"policy", "devices"}:
            ring = _Ring(color=GREEN)
            self.metric_rings[key] = ring
            center.addWidget(ring)
        else:
            palette = {
                "blue": (BLUE_SOFT, BLUE),
                "red": (RED_SOFT, RED),
                "purple": (PURPLE_SOFT, PURPLE),
                "green": (GREEN_SOFT, GREEN),
            }
            bg, fg = palette.get(tone, palette["blue"])
            bubble = QLabel()
            bubble.setFixedSize(34, 34)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setPixmap(icon(icon_name, color=fg, size=19).pixmap(19, 19))
            bubble.setStyleSheet(f"background:{bg};border-radius:10px;border:none;")
            center.addWidget(bubble)

        copy = QVBoxLayout()
        copy.setSpacing(0)
        value = QLabel("—")
        value.setStyleSheet(
            f"color:{INK};font-size:19px;font-weight:900;background:transparent;border:none;"
        )
        detail = _muted("", 7)
        copy.addWidget(value)
        copy.addWidget(detail)
        center.addLayout(copy, 1)
        box.addLayout(center)
        box.addStretch(1)
        self.metric_values[key] = value
        self.metric_details[key] = detail
        return card

    def _coverage_card(self) -> QFrame:
        card = _card("MockupCoverageCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(15, 13, 15, 13)
        box.setSpacing(9)
        top = QHBoxLayout()
        top.addWidget(_heading("Policy coverage", 10))
        top.addStretch(1)
        self.coverage_chip = _chip("NO POLICY", "neutral")
        top.addWidget(self.coverage_chip)
        box.addLayout(top)
        box.addWidget(_muted("Coverage reflects configured company policy rules and approved destinations — not document content.", 8))

        self.coverage_rows: dict[str, tuple[QLabel, QProgressBar]] = {}
        for key, title in (
            ("rules", "Sensitive-data rules"),
            ("ai", "Approved AI destinations"),
            ("apps", "Approved connected apps"),
            ("devices", "Managed device compliance"),
        ):
            row = QHBoxLayout()
            label = QLabel(title)
            label.setMinimumWidth(142)
            label.setStyleSheet(f"color:{TEXT};font-size:8px;font-weight:750;border:none;")
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(0)
            progress.setTextVisible(False)
            progress.setFixedHeight(8)
            progress.setStyleSheet(
                "QProgressBar{background:#EAECF0;border:none;border-radius:4px;}"
                f"QProgressBar::chunk{{background:{GREEN};border-radius:4px;}}"
            )
            value = QLabel("0%")
            value.setFixedWidth(34)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:800;border:none;")
            row.addWidget(label)
            row.addWidget(progress, 1)
            row.addWidget(value)
            box.addLayout(row)
            self.coverage_rows[key] = (value, progress)
        box.addStretch(1)
        return card

    def _activity_card(self) -> QFrame:
        card = _card("MockupActivityCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(15, 13, 15, 13)
        box.setSpacing(6)
        top = QHBoxLayout()
        top.addWidget(_heading("Recent activity", 10))
        top.addStretch(1)
        open_activity = QPushButton("View all")
        open_activity.setCursor(Qt.CursorShape.PointingHandCursor)
        open_activity.setStyleSheet(
            f"QPushButton{{background:transparent;color:{BLUE};border:none;padding:3px;font-size:8px;font-weight:850;}}"
        )
        controller = getattr(self.main_window, "_privacygate_redesign_sidebar_controller", None)
        open_activity.clicked.connect(
            lambda: controller._open_activity() if controller is not None else None
        )
        top.addWidget(open_activity)
        box.addLayout(top)

        self.activity_rows = QVBoxLayout()
        self.activity_rows.setSpacing(0)
        box.addLayout(self.activity_rows)
        box.addStretch(1)
        return card

    def _risks_card(self) -> QFrame:
        card = _card("MockupRisksCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(15, 13, 15, 13)
        box.addWidget(_heading("Top risks to monitor", 10))
        box.addWidget(_muted("Derived from current workspace policy, membership and device status.", 8))
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Risk", "Category", "Impact", "Status"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setShowGrid(False)
        table.setMinimumHeight(150)
        table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#344054;border:none;}"
            "QTableWidget::item{padding:7px;border-bottom:1px solid #F2F4F7;font-size:8px;}"
            "QHeaderView::section{background:#FFFFFF;color:#667085;border:none;border-bottom:1px solid #EAECF0;"
            "padding:7px;font-size:7px;font-weight:850;}"
        )
        for col in range(4):
            table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        self.risks_table = table
        box.addWidget(table, 1)
        return card

    def _team_card(self) -> QFrame:
        card = _card("MockupTeamCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(15, 13, 15, 13)
        box.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(_heading("Team at a glance", 10))
        top.addStretch(1)
        manage = QPushButton("Manage")
        manage.setCursor(Qt.CursorShape.PointingHandCursor)
        manage.setStyleSheet(
            f"QPushButton{{background:transparent;color:{BLUE};border:none;padding:3px;font-size:8px;font-weight:850;}}"
        )
        manage.clicked.connect(lambda: self.dashboard._select_tab(1))
        top.addWidget(manage)
        box.addLayout(top)
        self.team_rows: dict[str, QLabel] = {}
        for key, title, icon_name in (
            ("members", "Members", "contact"),
            ("admins", "Administrators", "settings"),
            ("disabled", "Disabled members", "history"),
            ("devices", "Managed devices", "document"),
        ):
            row = QHBoxLayout()
            ico = QLabel()
            ico.setFixedSize(22, 22)
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setPixmap(icon(icon_name, color="#475467", size=15).pixmap(15, 15))
            row.addWidget(ico)
            label = QLabel(title)
            label.setStyleSheet(f"color:{TEXT};font-size:8px;border:none;")
            row.addWidget(label, 1)
            value = QLabel("0")
            value.setStyleSheet(f"color:{INK};font-size:9px;font-weight:850;border:none;")
            row.addWidget(value)
            box.addLayout(row)
            self.team_rows[key] = value
        box.addStretch(1)
        return card

    def _clear_activity(self) -> None:
        while self.activity_rows.count():
            item = self.activity_rows.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child is not None:
                while child.count():
                    nested = child.takeAt(0)
                    if nested.widget() is not None:
                        nested.widget().deleteLater()

    def _activity_items(self) -> list[dict[str, object]]:
        try:
            rows = list(self.activity.recent(120))
        except Exception:
            return []
        team_page = self.team_page
        store = getattr(team_page, "_privacygate_workspace_store", None)
        active_key = ""
        if store is not None:
            try:
                active_key = str(store.load().active_key or "")
            except Exception:
                active_key = ""
        if not active_key:
            state = team_page.state
            active_key = f"org:{state.organization_id}" if state.organization_id else "personal"
        scoped = [row for row in rows if str(row.get("workspace_key") or "") == active_key]
        return scoped

    @staticmethod
    def _event_counts(rows: list[dict[str, object]]) -> tuple[int, int, int]:
        protected = 0
        blocked = 0
        ai_use = 0
        for row in rows:
            event = str(row.get("event_type") or "").lower()
            status = str(row.get("status") or "").lower()
            detail = str(row.get("detail") or "").lower()
            if "protect" in event or event in {"library_saved", "batch_completed"}:
                protected += 1
            if status not in {"", "ok", "success", "protected"} or "block" in event or "blocked" in detail:
                blocked += 1
            if any(token in event for token in ("ai", "preflight", "handoff")):
                ai_use += 1
        return protected, blocked, ai_use

    def _render_activity(self, rows: list[dict[str, object]]) -> None:
        self._clear_activity()
        if not rows:
            empty = _muted("No organization activity has been recorded on this device yet.", 8)
            empty.setMinimumHeight(70)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.activity_rows.addWidget(empty)
            return
        for index, row in enumerate(rows[:5]):
            line = QWidget()
            line_box = QHBoxLayout(line)
            line_box.setContentsMargins(0, 7, 0, 7)
            line_box.setSpacing(8)
            event = str(row.get("event_type") or "")
            status = str(row.get("status") or "ok").lower()
            tone = RED if status not in {"ok", "success", "protected"} else GREEN
            dot = QLabel("●")
            dot.setFixedWidth(12)
            dot.setStyleSheet(f"color:{tone};font-size:8px;border:none;")
            line_box.addWidget(dot)
            copy = QLabel(_friendly_event(event))
            copy.setStyleSheet(f"color:{TEXT};font-size:8px;font-weight:700;border:none;")
            line_box.addWidget(copy, 1)
            when = QLabel(_format_when(row.get("created_at")))
            when.setStyleSheet(f"color:{MUTED};font-size:7px;border:none;")
            line_box.addWidget(when)
            self.activity_rows.addWidget(line)
            if index < min(4, len(rows) - 1):
                divider = QFrame()
                divider.setFixedHeight(1)
                divider.setStyleSheet("background:#F2F4F7;border:none;")
                self.activity_rows.addWidget(divider)

    def _set_coverage(self, key: str, value: int) -> None:
        label, bar = self.coverage_rows[key]
        value = max(0, min(100, int(value)))
        label.setText(f"{value}%")
        bar.setValue(value)

    def _render_risks(self, *, policy, inactive_members: int, inactive_devices: int, blocked: int) -> None:
        risks: list[tuple[str, str, str, str]] = []
        if policy is None:
            risks.append(("Company policy unavailable", "Policy", "High", "Active"))
        else:
            blocked_ai = sum(1 for allowed in policy.allowed_ai.values() if not allowed)
            if blocked_ai:
                risks.append((f"{blocked_ai} AI destination(s) restricted", "AI Risk", "Low", "Controlled"))
            required = sum(
                1 for directive in policy.protection_rules.values()
                if directive is ProtectionDirective.REQUIRED_PROTECT
            )
            if required:
                risks.append((f"{required} mandatory protection rule(s)", "Data", "Low", "Enforced"))
        if inactive_devices:
            risks.append((f"{inactive_devices} device(s) not active", "Endpoint", "Medium", "Review"))
        if inactive_members:
            risks.append((f"{inactive_members} member(s) disabled/revoked", "Access", "Medium", "Review"))
        if blocked:
            risks.append((f"{blocked} blocked/failed local event(s)", "Activity", "Medium", "Monitor"))
        if not risks:
            risks.append(("No elevated risk derived from current metadata", "Workspace", "Low", "Normal"))

        self.risks_table.setRowCount(min(4, len(risks)))
        for row_index, values in enumerate(risks[:4]):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.risks_table.setItem(row_index, column, item)

    def render(self) -> None:
        state = self.team_page.state
        if not state.organization_id:
            return
        policy = state.policy
        members = list(self.team_page._members)
        devices = list(self.team_page._devices)
        active_members = [r for r in members if str(r.get("status") or "active").lower() == "active"]
        active_devices = [r for r in devices if str(r.get("status") or "active").lower() == "active"]
        inactive_members = max(0, len(members) - len(active_members))
        inactive_devices = max(0, len(devices) - len(active_devices))
        admins = sum(1 for r in active_members if str(r.get("role") or "").lower() in {"owner", "admin"})

        org_name = state.organization_name or (policy.organization_name if policy else "Organization")
        self.title.setText(org_name)
        self.subtitle.setText("Organization overview. Your policy, members and managed devices at a glance.")
        self.role_chip.setText((state.role or "member").upper())
        self.plan_chip.setText(state.plan.label.upper())

        activity_rows = self._activity_items()
        protected, blocked, ai_use = self._event_counts(activity_rows)

        policy_percent = 100 if policy is not None and state.membership_status == "active" else 0
        self.metric_rings["policy"].set_value(policy_percent, "ACTIVE" if policy else "NO POLICY")
        self.metric_values["policy"].setText(f"v{policy.version}" if policy else "—")
        self.metric_details["policy"].setText("Company policy synced" if policy else "Refresh required")

        self.metric_values["protected"].setText(str(protected))
        self.metric_details["protected"].setText("Recorded in this workspace on this device")
        self.metric_values["blocked"].setText(str(blocked))
        self.metric_details["blocked"].setText("Blocked or failed metadata events")

        device_percent = int(round(100 * len(active_devices) / len(devices))) if devices else 100
        self.metric_rings["devices"].set_value(device_percent, "COMPLIANT" if device_percent == 100 else "REVIEW")
        self.metric_values["devices"].setText(str(len(active_devices)))
        self.metric_details["devices"].setText(f"{len(devices)} managed device(s)")

        self.metric_values["ai"].setText(str(ai_use))
        self.metric_details["ai"].setText("Local AI/preflight activity records")

        if policy:
            rule_total = max(1, len(policy.protection_rules))
            rule_covered = sum(1 for directive in policy.protection_rules.values() if directive in {
                ProtectionDirective.REQUIRED_PROTECT,
                ProtectionDirective.DEFAULT_PROTECT,
                ProtectionDirective.USER_CHOICE,
                ProtectionDirective.ALLOW,
            })
            rules_pct = int(round(100 * rule_covered / rule_total))
            ai_total = max(1, len(policy.allowed_ai))
            ai_pct = int(round(100 * sum(1 for enabled in policy.allowed_ai.values() if enabled) / ai_total))
            app_total = max(1, len(policy.allowed_connectors))
            app_pct = int(round(100 * sum(1 for enabled in policy.allowed_connectors.values() if enabled) / app_total))
            self.coverage_chip.setText(f"POLICY v{policy.version}")
            self.coverage_chip.setStyleSheet(
                f"background:{GREEN_SOFT};color:{GREEN};border:1px solid #BBF7D0;border-radius:8px;"
                "padding:4px 8px;font-size:7px;font-weight:850;"
            )
        else:
            rules_pct = ai_pct = app_pct = 0
            self.coverage_chip.setText("NO POLICY")
        self._set_coverage("rules", rules_pct)
        self._set_coverage("ai", ai_pct)
        self._set_coverage("apps", app_pct)
        self._set_coverage("devices", device_percent)

        self._render_activity(activity_rows)
        self._render_risks(
            policy=policy,
            inactive_members=inactive_members,
            inactive_devices=inactive_devices,
            blocked=blocked,
        )

        self.team_rows["members"].setText(str(len(active_members)))
        self.team_rows["admins"].setText(str(admins))
        self.team_rows["disabled"].setText(str(inactive_members))
        self.team_rows["devices"].setText(str(len(devices)))


def apply_mockup_organization_overview_2026(main_window) -> MockupOrganizationOverview | None:
    """Replace only the visible Organization Overview stack page."""

    team_page = getattr(main_window, "team_page", None)
    dashboard = getattr(team_page, "_privacygate_premium_dashboard", None) if team_page is not None else None
    if team_page is None or dashboard is None:
        return None
    existing = getattr(dashboard, "_privacygate_mockup_overview_2026", None)
    if existing is not None:
        return existing

    stack = getattr(dashboard, "stack", None)
    if stack is None or stack.count() == 0:
        return None
    old = stack.widget(0)
    view = MockupOrganizationOverview(main_window, dashboard, dashboard)
    stack.removeWidget(old)
    old.hide()
    stack.insertWidget(0, view)
    dashboard.overview = view
    dashboard._privacygate_mockup_overview_2026 = view
    if stack.currentIndex() == 0:
        stack.setCurrentIndex(0)
    dashboard._style_tabs(0)
    return view
