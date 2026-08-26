from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ai_pm_lab_privacy_gate.domain.plans import PlanCode, all_plans
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.ui.iconography import icon

NAVY = "#062B4F"
TEAL = "#0B7F89"
MUTED = "#61798A"
WHITE = "#FFFFFF"


class PlanAccountPanel(QFrame):
    """Compact current-account row for Settings, inspired by Codex settings."""

    def __init__(self, open_plans, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CurrentAccountPanel")
        self.setStyleSheet("QFrame#CurrentAccountPanel{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:15px;}")
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 15, 18, 15)
        root.setSpacing(10)
        title = QLabel("Your account")
        title.setStyleSheet(f"color:{NAVY};font-size:14px;font-weight:850;border:none;")
        root.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(12)
        avatar = QLabel()
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setPixmap(icon("contact", color=WHITE, size=20).pixmap(20, 20))
        avatar.setStyleSheet("background:#0B7F89;border:none;border-radius:20px;")
        row.addWidget(avatar)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.account_type = QLabel("Individual account")
        self.account_type.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:800;border:none;")
        self.account_detail = QLabel("Active entitlement")
        self.account_detail.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
        text.addWidget(self.account_type)
        text.addWidget(self.account_detail)
        row.addLayout(text, 1)
        self.plan_badge = QLabel("BASIC")
        self.plan_badge.setStyleSheet("background:#E8F7F7;color:#0B7F89;border:1px solid #B8E1E4;border-radius:10px;padding:6px 11px;font-size:9px;font-weight:900;")
        row.addWidget(self.plan_badge)
        update = QPushButton("Update plan")
        update.setCursor(Qt.CursorShape.PointingHandCursor)
        update.setStyleSheet("QPushButton{background:#0B7F89;color:white;border:none;border-radius:9px;padding:9px 14px;font-weight:800;}QPushButton:hover{background:#096D76;}")
        update.clicked.connect(open_plans)
        row.addWidget(update)
        root.addLayout(row)

    def update_state(self, state: TeamState) -> None:
        self.plan_badge.setText(state.plan.label.upper())
        if state.organization_id:
            self.account_type.setText(state.organization_name or "Organization account")
            self.account_detail.setText(f"{(state.role or 'member').title()} · {state.entitlement_status.title()} entitlement")
        else:
            self.account_type.setText("Individual account")
            self.account_detail.setText(f"Personal workspace · {state.entitlement_status.title()} entitlement")


class PlansPage(QWidget):
    """Dedicated plan comparison page, kept out of day-to-day Settings."""

    def __init__(self, back_to_settings, contact_sales, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PlansPage")
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(18)
        top = QHBoxLayout()
        back = QPushButton("Back to Settings")
        back.setIcon(icon("restore", color=MUTED, size=16))
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setStyleSheet("QPushButton{background:transparent;color:#61798A;border:none;padding:7px;font-weight:700;}QPushButton:hover{color:#0B7F89;}")
        back.clicked.connect(back_to_settings)
        top.addWidget(back)
        top.addStretch(1)
        root.addLayout(top)
        title = QLabel("Choose the plan that fits your work")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{NAVY};font-size:25px;font-weight:900;")
        subtitle = QLabel("PrivacyGate stays local-first on every plan. Business and Enterprise add managed controls.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;")
        root.addWidget(title)
        root.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        self.cards: dict[PlanCode, QFrame] = {}
        self.markers: dict[PlanCode, QLabel] = {}
        self.actions: dict[PlanCode, QPushButton] = {}
        meta = {
            PlanCode.BASIC: ("protect", "Essential local privacy", ("Protect documents locally", "Library and Restore", "Personal workspace")),
            PlanCode.PRO: ("document", "Advanced individual work", ("Everything in Basic", "Premium personal controls", "Advanced local workflows")),
            PlanCode.BUSINESS: ("workflow", "Built for teams", ("Everything in Pro", "Members and managed devices", "Company privacy policy")),
            PlanCode.ENTERPRISE: ("settings", "Advanced organization control", ("Everything in Business", "Enterprise identity", "Audit-ready controls")),
        }
        for column, definition in enumerate(all_plans()):
            card = QFrame(objectName=f"PlanCard_{definition.code.value}")
            card.setMinimumHeight(360)
            box = QVBoxLayout(card)
            box.setContentsMargins(18, 18, 18, 18)
            box.setSpacing(9)
            icon_name, tagline, bullets = meta[definition.code]
            head = QHBoxLayout()
            bubble = QLabel()
            bubble.setFixedSize(42, 42)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setPixmap(icon(icon_name, color=TEAL, size=22).pixmap(22, 22))
            bubble.setStyleSheet("background:#E8F7F7;border:none;border-radius:21px;")
            head.addWidget(bubble)
            head.addStretch(1)
            marker = QLabel()
            marker.setStyleSheet("color:#0B7F89;font-size:8px;font-weight:900;border:none;")
            head.addWidget(marker)
            box.addLayout(head)
            name = QLabel(definition.label)
            name.setStyleSheet(f"color:{NAVY};font-size:20px;font-weight:900;border:none;")
            box.addWidget(name)
            tag = QLabel(tagline)
            tag.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
            box.addWidget(tag)
            box.addSpacing(14)
            for bullet in bullets:
                label = QLabel(f"-  {bullet}")
                label.setWordWrap(True)
                label.setStyleSheet(f"color:{NAVY};font-size:9px;border:none;padding:3px 0;")
                box.addWidget(label)
            box.addStretch(1)
            action = QPushButton("Contact us")
            action.setCursor(Qt.CursorShape.PointingHandCursor)
            action.clicked.connect(contact_sales)
            box.addWidget(action)
            grid.addWidget(card, 0, column)
            self.cards[definition.code] = card
            self.markers[definition.code] = marker
            self.actions[definition.code] = action
        root.addLayout(grid)
        root.addStretch(1)
        self.setStyleSheet(
            "QWidget#PlansPage{background:#F7FAFC;}"
            "QWidget#PlansPage QLabel{background:transparent;border:none;}"
        )

    def update_state(self, state: TeamState) -> None:
        for code, card in self.cards.items():
            current = code == state.plan
            card.setStyleSheet(
                f"QFrame#{card.objectName()}{{background:{'#F1FBFB' if current else '#FFFFFF'};"
                f"border:{'2px solid #0B7F89' if current else '1px solid #DCE5EA'};border-radius:16px;}}"
            )
            self.markers[code].setText("CURRENT PLAN" if current else "")
            action = self.actions[code]
            action.setText("Your current plan" if current else ("Contact sales" if code.is_team_plan else "Update plan"))
            action.setEnabled(not current)
            action.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:%s;border-radius:9px;padding:10px;font-weight:800;}"
                % ("#EEF3F5" if current else "#0B7F89", "#78909E" if current else "white", "1px solid #DCE5EA" if current else "none")
            )


def install_plan_account_panel(main_window, state: TeamState) -> PlanAccountPanel:
    settings_page = main_window.settings_page
    panel = getattr(settings_page, "_privacygate_plan_account_panel", None)
    if isinstance(panel, PlanAccountPanel):
        panel.update_state(state)
        return panel

    settings_index = main_window.pages.indexOf(settings_page)
    plans_page = PlansPage(lambda: main_window._show_page(settings_index), main_window.local_automation_page._contact, main_window)
    plans_index = main_window.pages.addWidget(plans_page)

    def open_plans() -> None:
        main_window.pages.setCurrentIndex(plans_index)
        for button in main_window.nav_buttons:
            button.setChecked(False)
        plans_page.update_state(getattr(main_window.team_page, "state", state))

    panel = PlanAccountPanel(open_plans, settings_page)
    root = settings_page.layout()
    if isinstance(root, QVBoxLayout):
        root.insertWidget(1, panel)
    settings_page._privacygate_plan_account_panel = panel
    main_window.plans_page = plans_page
    main_window.plans_page_index = plans_index
    panel.update_state(state)
    plans_page.update_state(state)
    return panel
