from __future__ import annotations

from collections import Counter

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.domain.governance import (
    PrivacyRiskLevel,
    evaluate_privacy_risk,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.governance_repository import (
    GovernancePreferencesStore,
    verify_activity_integrity,
)
from ai_pm_lab_privacy_gate.ui.business_foundation import _engine_for_page
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.privacy_preflight import build_preflight_snapshot


NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
AMBER = "#A56A00"
RED = "#B54747"
BORDER = "#D7E2EA"
SOFT = "#F7FAFC"


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


def _button(text: str, *, primary: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(36)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        button.setStyleSheet(
            "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:8px;"
            "padding:7px 12px;font-size:9px;font-weight:850;}"
            "QPushButton:hover{background:#096D76;}"
        )
    else:
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;"
            "border-radius:8px;padding:7px 12px;font-size:9px;font-weight:800;}"
            "QPushButton:hover{background:#F2FAFA;border-color:#96C9CD;color:#0B7180;}"
        )
    return button


def _chip(text: str, tone: str = "neutral") -> QLabel:
    palette = {
        "green": ("#EAF7EF", GREEN, "#BFE4CD"),
        "amber": ("#FFF5E5", AMBER, "#F0D3A0"),
        "red": ("#FDECEC", RED, "#F1C1C1"),
        "teal": ("#EAF6F6", TEAL, "#BFE0E2"),
        "neutral": ("#F1F5F7", MUTED, BORDER),
    }
    bg, fg, border = palette.get(tone, palette["neutral"])
    label = QLabel(text)
    label.setStyleSheet(
        f"background:{bg};color:{fg};border:1px solid {border};border-radius:8px;"
        "padding:4px 8px;font-size:8px;font-weight:900;"
    )
    return label


def _metric_card(title: str, value: str, detail: str) -> tuple[QFrame, QLabel, QLabel]:
    card = _card(f"GovernanceMetric_{title.replace(' ', '_')}")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(13, 11, 13, 11)
    layout.setSpacing(2)
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:800;")
    number = QLabel(value)
    number.setStyleSheet(f"color:{NAVY};font-size:20px;font-weight:950;")
    note = QLabel(detail)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:8px;")
    layout.addWidget(heading)
    layout.addWidget(number)
    layout.addWidget(note)
    return card, number, note


def _value_row(label: str) -> tuple[QFrame, QLabel]:
    frame = QFrame(objectName="GovernanceValueRow")
    frame.setStyleSheet(
        "QFrame#GovernanceValueRow{background:#FFFFFF;border:1px solid #E1E8ED;border-radius:9px;}"
    )
    row = QHBoxLayout(frame)
    row.setContentsMargins(12, 8, 12, 8)
    row.setSpacing(10)
    left = QLabel(label)
    left.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:800;")
    right = QLabel("—")
    right.setWordWrap(True)
    right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    right.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:800;")
    row.addWidget(left)
    row.addStretch(1)
    row.addWidget(right, 2)
    return frame, right


class GovernanceCenterPage(QWidget):
    """Read-only governance surface over PrivacyGate's existing local state.

    It never runs protection, changes findings, saves documents, or performs an AI
    handoff. Protect remains the only operational document workflow.
    """

    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self.main_window = main_window
        self.protect = main_window.protection_page
        self.controller = getattr(main_window, "privacygate_feature_suite", None)
        self._build()
        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self._refresh_if_visible)
        self._timer.start()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(22, 18, 22, 18)
        shell_layout.setSpacing(12)

        header = QHBoxLayout()
        copy = QVBoxLayout()
        copy.setSpacing(2)
        copy.addWidget(_title("Governance", 26))
        copy.addWidget(
            _muted(
                "Local privacy and AI governance visibility. Policies may sync to the device; document content and detailed activity stay local.",
                10,
            )
        )
        header.addLayout(copy, 1)
        local = _chip("LOCAL GOVERNANCE", "teal")
        header.addWidget(local, alignment=Qt.AlignmentFlag.AlignTop)
        shell_layout.addLayout(header)

        nav = QFrame(objectName="GovernanceTabs")
        nav.setStyleSheet(
            "QFrame#GovernanceTabs{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:10px;}"
        )
        nav_row = QHBoxLayout(nav)
        nav_row.setContentsMargins(7, 6, 7, 6)
        nav_row.setSpacing(6)
        self.overview_button = QPushButton("Overview")
        self.preflight_button = QPushButton("Preflight / Privacy")
        for button in (self.overview_button, self.preflight_button):
            button.setCheckable(True)
            button.setMinimumHeight(34)
            button.setStyleSheet(
                "QPushButton{background:#F6F9FB;color:#425D70;border:1px solid #DFE7EC;"
                "border-radius:7px;padding:6px 13px;font-size:9px;font-weight:800;}"
                "QPushButton:checked{background:#0B7F89;color:#FFFFFF;border-color:#0B7F89;}"
            )
            nav_row.addWidget(button)
        nav_row.addStretch(1)
        protect_button = _button("Open Protect")
        protect_button.setIcon(icon("protect", color=NAVY, size=16))
        protect_button.setIconSize(QSize(16, 16))
        protect_button.clicked.connect(lambda: self.main_window._show_page(0))
        nav_row.addWidget(protect_button)
        shell_layout.addWidget(nav)

        self.stack = QStackedWidget()
        self.overview_page = self._build_overview()
        self.preflight_page = self._build_preflight()
        self.stack.addWidget(self.overview_page)
        self.stack.addWidget(self.preflight_page)
        shell_layout.addWidget(self.stack, 1)

        self.overview_button.clicked.connect(lambda: self._select(0))
        self.preflight_button.clicked.connect(lambda: self._select(1))
        self._select(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(shell)
        root.addWidget(scroll)

    def _build_overview(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(11)

        hero = QFrame(objectName="GovernanceOverviewHero")
        hero.setStyleSheet(
            "QFrame#GovernanceOverviewHero{background:#F1F8F8;border:1px solid #CBE4E6;border-radius:13px;}"
        )
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(16, 13, 16, 13)
        hero_copy = QVBoxLayout()
        self.overview_status = QLabel("NO ACTIVE DOCUMENT")
        self.overview_status.setStyleSheet(f"color:{NAVY};font-size:16px;font-weight:950;")
        self.overview_reason = _muted("Open Protect to scan a document or connected source.", 9)
        hero_copy.addWidget(self.overview_status)
        hero_copy.addWidget(self.overview_reason)
        hero_row.addLayout(hero_copy, 1)
        self.overview_risk = _chip("RISK · —", "neutral")
        hero_row.addWidget(self.overview_risk, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(hero)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        specs = (
            ("Workspace", "—", "Active privacy context"),
            ("Policy", "—", "Policy applied on this device"),
            ("Devices", "—", "Managed endpoint status"),
            ("Activity", "—", "Tamper-evident local metadata log"),
        )
        self.overview_metrics: dict[str, tuple[QLabel, QLabel]] = {}
        for column, (name, value, detail) in enumerate(specs):
            card, number, note = _metric_card(name, value, detail)
            metrics.addWidget(card, 0, column)
            self.overview_metrics[name] = (number, note)
        layout.addLayout(metrics)

        body = QHBoxLayout()
        body.setSpacing(11)

        current = _card("GovernanceCurrentPreflight")
        current_box = QVBoxLayout(current)
        current_box.setContentsMargins(14, 12, 14, 12)
        current_box.setSpacing(7)
        current_box.addWidget(_title("Current Preflight", 12))
        current_box.addWidget(
            _muted(
                "A read-only summary of the current Protect state. The final second scan still runs in the existing AI Privacy Preflight before save or AI handoff.",
                8,
            )
        )
        self.current_source = _muted("No current source", 9)
        self.current_counts = QLabel("Detected —   •   Protected —   •   Residual —")
        self.current_counts.setStyleSheet(f"color:{INK};font-size:9px;font-weight:800;")
        current_box.addWidget(self.current_source)
        current_box.addWidget(self.current_counts)
        current_box.addStretch(1)
        open_preflight = _button("Open Preflight / Privacy", primary=True)
        open_preflight.clicked.connect(lambda: self._select(1))
        current_box.addWidget(open_preflight, 0, Qt.AlignmentFlag.AlignLeft)
        body.addWidget(current, 5)

        activity = _card("GovernanceActivitySummary")
        activity_box = QVBoxLayout(activity)
        activity_box.setContentsMargins(14, 12, 14, 12)
        activity_box.setSpacing(7)
        activity_box.addWidget(_title("Local Evidence", 12))
        self.activity_integrity = _muted("Checking local activity integrity…", 9)
        self.activity_retention = _muted("Retention: local default", 8)
        self.activity_recent = _muted("No recent local activity.", 8)
        activity_box.addWidget(self.activity_integrity)
        activity_box.addWidget(self.activity_retention)
        activity_box.addWidget(self.activity_recent)
        activity_box.addStretch(1)
        body.addWidget(activity, 4)
        layout.addLayout(body, 1)

        boundary = QFrame(objectName="GovernanceBoundary")
        boundary.setStyleSheet(
            "QFrame#GovernanceBoundary{background:#EDF8F4;border:1px solid #B9DECD;border-radius:10px;}"
        )
        boundary_row = QHBoxLayout(boundary)
        boundary_row.setContentsMargins(12, 9, 12, 9)
        shield = QLabel()
        shield.setPixmap(icon("protect", color=GREEN, size=18).pixmap(18, 18))
        boundary_row.addWidget(shield)
        boundary_row.addWidget(
            _muted(
                "Governance reads existing local Protect, Preflight and Activity state. It does not upload document contents, change findings, or perform AI handoffs.",
                8,
            ),
            1,
        )
        layout.addWidget(boundary)
        return page

    def _build_preflight(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(11)

        status = QFrame(objectName="GovernancePreflightStatus")
        status.setStyleSheet(
            "QFrame#GovernancePreflightStatus{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:13px;}"
        )
        status_row = QHBoxLayout(status)
        status_row.setContentsMargins(15, 13, 15, 13)
        status_copy = QVBoxLayout()
        self.preflight_status = QLabel("NO ACTIVE DOCUMENT")
        self.preflight_status.setStyleSheet(f"color:{NAVY};font-size:17px;font-weight:950;")
        self.preflight_reason = _muted("Open Protect to begin.", 9)
        status_copy.addWidget(self.preflight_status)
        status_copy.addWidget(self.preflight_reason)
        status_row.addLayout(status_copy, 1)
        self.preflight_risk = _chip("RISK · —", "neutral")
        status_row.addWidget(self.preflight_risk, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(status)

        path_card = _card("GovernanceDataPath")
        path_box = QVBoxLayout(path_card)
        path_box.setContentsMargins(14, 11, 14, 11)
        path_box.addWidget(_title("Protected data path", 10))
        self.data_path = QLabel("No active source")
        self.data_path.setWordWrap(True)
        self.data_path.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.data_path.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:850;")
        path_box.addWidget(self.data_path)
        layout.addWidget(path_card)

        metric_grid = QGridLayout()
        metric_grid.setHorizontalSpacing(10)
        self.preflight_metrics: dict[str, QLabel] = {}
        for column, (name, detail) in enumerate(
            (
                ("Detected", "Sensitive items found in the source"),
                ("Protected", "Items replaced in the protected result"),
                ("Visible", "Detected items intentionally left visible"),
                ("Residual", "Possible items found by the last second scan"),
            )
        ):
            card, value, _note = _metric_card(name, "0", detail)
            metric_grid.addWidget(card, 0, column)
            self.preflight_metrics[name] = value
        layout.addLayout(metric_grid)

        details = QHBoxLayout()
        details.setSpacing(11)

        context = _card("GovernancePreflightContext")
        context_box = QVBoxLayout(context)
        context_box.setContentsMargins(13, 11, 13, 11)
        context_box.setSpacing(6)
        context_box.addWidget(_title("Protection context", 11))
        self.detail_values: dict[str, QLabel] = {}
        for label in ("Source", "Workspace", "Policy", "Profile", "Protection mode", "Second scan"):
            row, value = _value_row(label)
            self.detail_values[label] = value
            context_box.addWidget(row)
        details.addWidget(context, 5)

        checks = _card("GovernancePreflightChecks")
        checks_box = QVBoxLayout(checks)
        checks_box.setContentsMargins(13, 11, 13, 11)
        checks_box.setSpacing(7)
        checks_box.addWidget(_title("Policy & destination checks", 11))
        self.policy_check = _muted("No active policy check.", 9)
        self.destination_check = _muted("No AI destination has been selected.", 9)
        self.residual_categories = _muted("Residual categories: not available until the second scan runs.", 8)
        checks_box.addWidget(self.policy_check)
        checks_box.addWidget(self.destination_check)
        checks_box.addWidget(self.residual_categories)
        checks_box.addStretch(1)
        note = _muted(
            "This page is evidence/visibility only. The operational AI Privacy Preflight popup remains the security checkpoint immediately before save/copy/AI handoff.",
            8,
        )
        note.setStyleSheet(
            f"background:{SOFT};border:1px solid {BORDER};border-radius:8px;padding:8px;color:{MUTED};font-size:8px;"
        )
        checks_box.addWidget(note)
        details.addWidget(checks, 4)
        layout.addLayout(details, 1)
        return page

    def _select(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.overview_button.setChecked(index == 0)
        self.preflight_button.setChecked(index == 1)
        self.refresh()

    def _refresh_if_visible(self) -> None:
        if self.isVisible():
            self.refresh()

    def _workspace(self) -> tuple[str, str, bool]:
        team_page = getattr(self.main_window, "team_page", None)
        store = getattr(team_page, "_privacygate_workspace_store", None)
        if store is None:
            return "personal", "Personal", True
        try:
            context = store.load()
            descriptor = context.workspaces.get(context.active_key)
        except Exception:
            return "personal", "Personal", True
        if descriptor is None:
            return "personal", "Personal", True
        return str(descriptor.key), str(descriptor.name), bool(descriptor.personal)

    def _second_scan_state(self) -> tuple[bool, str]:
        metric = getattr(self.protect, "verification_metric", None)
        text = str(metric.text() if metric is not None else "").strip()
        lowered = text.lower()
        if lowered.startswith("verified:"):
            return True, "Verified clear"
        if lowered.startswith("warning:"):
            return True, text
        return False, "Pending final Preflight"

    def _risk(self):
        findings = tuple(getattr(self.protect, "current_findings", ()) or ())
        result = getattr(self.protect, "current_result", None)
        applied = tuple(getattr(result, "applied_findings", ()) or ()) if result is not None else ()
        finding_ids = {str(getattr(item, "finding_id", "") or "") for item in findings}
        applied_ids = {str(getattr(item, "finding_id", "") or "") for item in applied}
        protected = len(finding_ids & applied_ids) if finding_ids else len(applied)
        protected = min(len(findings), protected)
        residual = tuple(getattr(self.protect, "_last_residual", ()) or ())
        engine = _engine_for_page(self.protect)
        required = [
            item
            for item in findings
            if engine.must_protect(str(getattr(item, "entity_type", "") or ""))
        ]
        required_ids = {str(getattr(item, "finding_id", "") or "") for item in required}
        required_protected = len(required_ids & applied_ids)
        required_residual = sum(
            1
            for item in residual
            if engine.must_protect(str(getattr(item, "entity_type", "") or ""))
        )
        destination_allowed = True
        if engine.active:
            destination_allowed = any(engine.can_use_ai(key) for key in ("chatgpt", "claude", "other"))
        return evaluate_privacy_risk(
            detected=len(findings),
            protected=protected,
            allowed=max(0, len(findings) - protected),
            residual=len(residual),
            destination_allowed=destination_allowed,
            policy_required_total=len(required),
            policy_required_protected=required_protected,
            policy_required_residual=required_residual,
        )

    @staticmethod
    def _risk_tone(level: PrivacyRiskLevel) -> str:
        return {
            PrivacyRiskLevel.LOW: "green",
            PrivacyRiskLevel.MEDIUM: "amber",
            PrivacyRiskLevel.HIGH: "red",
        }[level]

    def _set_chip(self, label: QLabel, text: str, tone: str) -> None:
        palette = {
            "green": ("#EAF7EF", GREEN, "#BFE4CD"),
            "amber": ("#FFF5E5", AMBER, "#F0D3A0"),
            "red": ("#FDECEC", RED, "#F1C1C1"),
            "teal": ("#EAF6F6", TEAL, "#BFE0E2"),
            "neutral": ("#F1F5F7", MUTED, BORDER),
        }
        bg, fg, border = palette[tone]
        label.setText(text)
        label.setStyleSheet(
            f"background:{bg};color:{fg};border:1px solid {border};border-radius:8px;"
            "padding:4px 8px;font-size:8px;font-weight:900;"
        )

    def refresh(self) -> None:
        document = getattr(self.protect, "current_document", None)
        result = getattr(self.protect, "current_result", None)
        findings = tuple(getattr(self.protect, "current_findings", ()) or ())
        residual = tuple(getattr(self.protect, "_last_residual", ()) or ())
        workspace_key, workspace_name, personal = self._workspace()
        team_page = getattr(self.main_window, "team_page", None)
        policy = getattr(getattr(team_page, "state", None), "policy", None)
        if personal:
            policy = None

        snapshot = build_preflight_snapshot(
            self.protect,
            destination="Approved AI destination",
            delivery="selected at final handoff",
            residual_findings=residual,
        )
        risk = self._risk()
        second_scan_done, second_scan_text = self._second_scan_state()

        if document is None:
            status_text = "NO ACTIVE DOCUMENT"
            reason = "Open Protect to scan a document, pasted text, or connected source."
            tone = "neutral"
        elif result is None:
            status_text = "REVIEW IN PROTECT"
            reason = "The source has been scanned, but a protected result is not ready yet."
            tone = "amber"
        elif not second_scan_done:
            status_text = "PREFLIGHT PENDING"
            reason = "Protection is ready. The final second scan will run before save, copy, download or AI handoff."
            tone = "teal"
        elif risk.hard_block:
            status_text = "BLOCKED BY POLICY"
            reason = risk.reason
            tone = "red"
        elif risk.level is PrivacyRiskLevel.HIGH:
            status_text = "REVIEW REQUIRED"
            reason = risk.reason
            tone = "red"
        else:
            status_text = "READY FOR AI" if risk.level is PrivacyRiskLevel.LOW else "REVIEW RECOMMENDED"
            reason = risk.reason
            tone = "green" if risk.level is PrivacyRiskLevel.LOW else "amber"

        self.overview_status.setText(status_text)
        self.overview_reason.setText(reason)
        self.preflight_status.setText(status_text)
        self.preflight_reason.setText(reason)
        risk_text = f"RISK · {risk.level.label} · {risk.score}/100"
        self._set_chip(self.overview_risk, risk_text, self._risk_tone(risk.level))
        self._set_chip(self.preflight_risk, risk_text, self._risk_tone(risk.level))

        policy_text = f"v{policy.version}" if policy is not None else "Personal"
        self.overview_metrics["Workspace"][0].setText(workspace_name)
        self.overview_metrics["Workspace"][1].setText("Personal local context" if personal else "Company-managed context")
        self.overview_metrics["Policy"][0].setText(policy_text)
        self.overview_metrics["Policy"][1].setText(
            "No company policy" if policy is None else str(getattr(policy, "policy_name", "Company policy"))
        )

        devices = tuple(getattr(team_page, "_devices", ()) or ()) if team_page is not None else ()
        active_devices = [item for item in devices if str(item.get("status") or "active").lower() == "active"]
        compliant = 0
        for item in active_devices:
            if policy is None:
                compliant += 1
                continue
            raw = item.get("policy_version") or item.get("policyVersion") or 0
            try:
                compliant += int(raw or 0) >= int(policy.version)
            except (TypeError, ValueError):
                pass
        self.overview_metrics["Devices"][0].setText(
            "Local" if not devices else f"{compliant}/{len(active_devices)}"
        )
        self.overview_metrics["Devices"][1].setText(
            "No managed device list in Personal" if not devices else "Active devices on current policy"
        )

        source_line = snapshot.source_line
        self.current_source.setText(source_line)
        self.current_counts.setText(
            f"Detected {snapshot.detected}   •   Protected {snapshot.protected}   •   Residual {snapshot.residual}"
        )

        activity_count = 0
        activity_ok = True
        activity_message = "No local activity store available."
        recent_text = "No recent local activity."
        if self.controller is not None:
            try:
                recent = tuple(self.controller.activity.recent(500))
                activity_count = len(recent)
                integrity = verify_activity_integrity(self.controller.activity)
                activity_ok = bool(integrity.ok)
                activity_message = integrity.message
                snippets = []
                for event in recent[:4]:
                    event_type = str(event.get("event_type") or "activity").replace("_", " ").title()
                    status = str(event.get("status") or "ok").title()
                    snippets.append(f"{event_type} · {status}")
                recent_text = "\n".join(snippets) if snippets else "No recent local activity."
            except Exception as exc:
                activity_ok = False
                activity_message = f"Local activity status unavailable: {exc}"
        self.overview_metrics["Activity"][0].setText(str(activity_count))
        self.overview_metrics["Activity"][1].setText("Local metadata events")
        self.activity_integrity.setText(("✓ " if activity_ok else "⚠ ") + activity_message)
        self.activity_integrity.setStyleSheet(
            f"color:{GREEN if activity_ok else RED};font-size:9px;font-weight:850;"
        )
        retention_days = GovernancePreferencesStore(self.main_window.library.data_dir).retention_days()
        self.activity_retention.setText(
            f"Retention · {retention_days} days" if retention_days else "Retention · keep until changed locally"
        )
        self.activity_recent.setText(recent_text)

        self.preflight_metrics["Detected"].setText(str(snapshot.detected))
        self.preflight_metrics["Protected"].setText(str(snapshot.protected))
        self.preflight_metrics["Visible"].setText(str(snapshot.allowed))
        self.preflight_metrics["Residual"].setText(str(snapshot.residual) if second_scan_done else "—")

        self.data_path.setText(
            f"{source_line}   →   PrivacyGate local protection   →   protected copy   →   approved AI destination at handoff"
        )
        self.detail_values["Source"].setText(source_line)
        self.detail_values["Workspace"].setText(workspace_name)
        self.detail_values["Policy"].setText(
            "Personal · no company policy" if policy is None else f"{policy.policy_name} · v{policy.version}"
        )
        self.detail_values["Profile"].setText(snapshot.profile or "—")
        self.detail_values["Protection mode"].setText(snapshot.mode or "—")
        self.detail_values["Second scan"].setText(second_scan_text)

        engine = _engine_for_page(self.protect)
        if policy is None:
            self.policy_check.setText("✓ Personal context · no company-required protection rules are active.")
            self.policy_check.setStyleSheet(f"color:{GREEN};font-size:9px;font-weight:800;")
        else:
            required = [
                item
                for item in findings
                if engine.must_protect(str(getattr(item, "entity_type", "") or ""))
            ]
            applied = tuple(getattr(result, "applied_findings", ()) or ()) if result is not None else ()
            applied_ids = {str(getattr(item, "finding_id", "") or "") for item in applied}
            protected_required = sum(
                1 for item in required if str(getattr(item, "finding_id", "") or "") in applied_ids
            )
            missing = max(0, len(required) - protected_required)
            self.policy_check.setText(
                f"{'✓' if missing == 0 else '⚠'} Company policy v{policy.version} · mandatory protected {protected_required}/{len(required)}"
            )
            self.policy_check.setStyleSheet(
                f"color:{GREEN if missing == 0 else RED};font-size:9px;font-weight:800;"
            )

        destination_parts = []
        for key, label in (("chatgpt", "ChatGPT"), ("claude", "Claude"), ("other", "Other AI")):
            allowed = True if policy is None else engine.can_use_ai(key)
            destination_parts.append(f"{label}: {'allowed' if allowed else 'blocked'}")
        self.destination_check.setText("   •   ".join(destination_parts))
        self.destination_check.setStyleSheet(f"color:{INK};font-size:9px;font-weight:750;")

        if not second_scan_done:
            self.residual_categories.setText(
                "Residual categories · pending. The existing final Preflight runs the second scan before protected content leaves PrivacyGate."
            )
        elif not residual:
            self.residual_categories.setText("Residual categories · none detected by the last second scan.")
        else:
            counts = Counter(str(getattr(item, "entity_type", "") or "Sensitive data") for item in residual)
            summary = ", ".join(f"{key.replace('_', ' ').title()} ×{value}" for key, value in sorted(counts.items()))
            self.residual_categories.setText(f"Residual categories · {summary}")


def apply_governance_center_2026(main_window) -> None:
    """Add one Governance navigation entry without changing Protect behavior."""
    if bool(getattr(main_window, "_privacygate_governance_center_2026", False)):
        return
    main_window._privacygate_governance_center_2026 = True

    page = GovernanceCenterPage(main_window)
    page_index = main_window.pages.addWidget(page)
    main_window.governance_page = page
    main_window.governance_page_index = page_index

    button = QPushButton("Governance", objectName="NavButton")
    button.setCheckable(True)
    button.setToolTip("Governance")
    button.setIcon(icon("protect", color="#FFFFFF", size=20))
    button.setIconSize(QSize(20, 20))
    button.setStyleSheet(
        "QPushButton{background:transparent;color:#DCE7EF;border:none;border-radius:9px;"
        "padding:12px 14px;text-align:left;font-weight:650;min-height:24px;}"
        "QPushButton:hover{background:#0D3A5C;color:#FFFFFF;}"
        "QPushButton:checked{background:#0B7180;color:#FFFFFF;border-left:3px solid #D3A13B;}"
    )
    button.clicked.connect(lambda _checked=False: main_window._show_page(page_index))
    main_window.nav_group.addButton(button)

    settings_button = next(
        (item for item in main_window.nav_buttons if item.text() == "Settings"),
        None,
    )
    if settings_button is not None:
        layout_index = main_window.side_layout.indexOf(settings_button)
        main_window.side_layout.insertWidget(max(0, layout_index), button)
        list_index = main_window.nav_buttons.index(settings_button)
        main_window.nav_buttons.insert(list_index, button)
        main_window.nav_labels.insert(list_index, "Governance")
    else:
        main_window.side_layout.addWidget(button)
        main_window.nav_buttons.append(button)
        main_window.nav_labels.append("Governance")

    previous_show_page = main_window._show_page

    def show_page(index: int) -> None:
        if index == page_index:
            main_window.pages.setCurrentIndex(page_index)
            for item in main_window.nav_buttons:
                item.setChecked(False)
            button.setChecked(True)
            page.refresh()
            return
        previous_show_page(index)

    main_window._show_page = show_page
