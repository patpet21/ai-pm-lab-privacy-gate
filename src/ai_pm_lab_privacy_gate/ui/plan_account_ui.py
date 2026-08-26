from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ai_pm_lab_privacy_gate.domain.plans import PlanCode, all_plans
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.ui.iconography import icon

NAVY = "#062B4F"
TEAL = "#0B7F89"
MUTED = "#61798A"
BORDER = "#DCE5EA"
GREEN = "#23824B"
WHITE = "#FFFFFF"


class PlanAccountPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PremiumPlanPanel")
        self.setStyleSheet(
            "QFrame#PremiumPlanPanel{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:16px;}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Plan & Account")
        title.setStyleSheet(f"color:{NAVY};font-size:16px;font-weight:900;")
        note = QLabel("Review your current PrivacyGate entitlement and available product tiers.")
        note.setStyleSheet(f"color:{MUTED};font-size:9px;")
        title_box.addWidget(title)
        title_box.addWidget(note)
        header.addLayout(title_box, 1)
        self.current_badge = QLabel("BASIC")
        self.current_badge.setStyleSheet(
            "background:#E8F7F7;color:#0B7F89;border:1px solid #B8E1E4;border-radius:10px;"
            "padding:6px 11px;font-size:9px;font-weight:900;"
        )
        header.addWidget(self.current_badge, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        self.cards: dict[PlanCode, QFrame] = {}
        self.markers: dict[PlanCode, QLabel] = {}
        self.buttons: dict[PlanCode, QPushButton] = {}

        plan_meta = {
            PlanCode.BASIC: ("protect", "Individual privacy", ["Local protection", "Local Library & Restore", "Personal workspace"]),
            PlanCode.PRO: ("document", "Advanced individual workflows", ["Everything in Basic", "Advanced personal controls", "Premium individual features"]),
            PlanCode.BUSINESS: ("workflow", "Teams & company policy", ["Everything in Pro", "Members & seats", "Managed company policy"]),
            PlanCode.ENTERPRISE: ("settings", "Advanced organization control", ["Everything in Business", "Advanced administration", "Enterprise-ready controls"]),
        }

        for column, definition in enumerate(all_plans()):
            card = QFrame()
            card.setMinimumHeight(210)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(15, 14, 15, 14)
            layout.setSpacing(8)
            icon_name, subtitle, bullets = plan_meta[definition.code]

            top = QHBoxLayout()
            bubble = QLabel()
            bubble.setFixedSize(40, 40)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setPixmap(icon(icon_name, color=TEAL, size=22).pixmap(22, 22))
            bubble.setStyleSheet("background:#E8F7F7;border-radius:20px;")
            top.addWidget(bubble)
            top.addStretch(1)
            marker = QLabel()
            marker.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            marker.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:900;")
            top.addWidget(marker)
            layout.addLayout(top)

            name = QLabel(definition.label)
            name.setStyleSheet(f"color:{NAVY};font-size:17px;font-weight:900;")
            sub = QLabel(subtitle)
            sub.setWordWrap(True)
            sub.setStyleSheet(f"color:{MUTED};font-size:9px;")
            layout.addWidget(name)
            layout.addWidget(sub)

            for bullet in bullets:
                item = QLabel(f"✓  {bullet}")
                item.setStyleSheet(f"color:{NAVY};font-size:9px;")
                layout.addWidget(item)

            layout.addStretch(1)
            button = QPushButton("Request access")
            button.setEnabled(False)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton{background:#F4F7F9;color:#7B8F9E;border:1px solid #DCE5EA;border-radius:9px;"
                "padding:8px 10px;font-size:9px;font-weight:800;}"
            )
            layout.addWidget(button)
            grid.addWidget(card, 0, column)
            self.cards[definition.code] = card
            self.markers[definition.code] = marker
            self.buttons[definition.code] = button

        root.addLayout(grid)

        self.account_summary = QLabel()
        self.account_summary.setWordWrap(True)
        self.account_summary.setStyleSheet(
            "background:#F8FBFC;border:1px solid #E3EAEE;border-radius:10px;padding:10px;"
            f"color:{NAVY};font-size:9px;"
        )
        root.addWidget(self.account_summary)

    def update_state(self, state: TeamState) -> None:
        self.current_badge.setText(state.plan.label.upper())
        for code, card in self.cards.items():
            selected = code == state.plan
            card.setStyleSheet(
                (
                    "QFrame{background:#F1FBFB;border:2px solid #0B7F89;border-radius:13px;}"
                )
                if selected
                else
                    "QFrame{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:13px;}"
            )
            marker = self.markers[code]
            button = self.buttons[code]
            if selected:
                marker.setText("CURRENT PLAN")
                marker.setStyleSheet("color:#0B7F89;font-size:8px;font-weight:950;")
                button.setText("Current plan")
                button.setEnabled(False)
                button.setStyleSheet(
                    "QPushButton{background:#E8F7F7;color:#0B7F89;border:1px solid #B8E1E4;border-radius:9px;"
                    "padding:8px 10px;font-size:9px;font-weight:900;}"
                )
            else:
                marker.setText("")
                button.setText("Request access")
                button.setEnabled(False)
                button.setStyleSheet(
                    "QPushButton{background:#F4F7F9;color:#7B8F9E;border:1px solid #DCE5EA;border-radius:9px;"
                    "padding:8px 10px;font-size:9px;font-weight:800;}"
                )

        if state.organization_id:
            self.account_summary.setText(
                f"Organization: {state.organization_name or 'Organization'}   •   Role: {state.role.title()}   •   "
                f"Entitlement: {state.entitlement_status.title()}"
            )
        else:
            self.account_summary.setText(
                f"Individual account   •   {state.plan.label}   •   Entitlement: {state.entitlement_status.title()}"
            )


def install_plan_account_panel(settings_page, state: TeamState) -> PlanAccountPanel:
    panel = getattr(settings_page, "_privacygate_plan_account_panel", None)
    if isinstance(panel, PlanAccountPanel):
        panel.update_state(state)
        return panel

    panel = PlanAccountPanel(settings_page)
    root = settings_page.layout()
    if isinstance(root, QVBoxLayout):
        root.insertWidget(1, panel)
    settings_page._privacygate_plan_account_panel = panel
    panel.update_state(state)
    return panel
