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
WHITE = "#FFFFFF"


class PlanAccountPanel(QFrame):
    """Compact plan overview for Settings.

    Keep selectors object-name scoped. QLabel inherits QFrame in Qt, so a broad
    `QFrame{...}` rule also paints borders around every label and bullet. That was
    the source of the boxed/text-grid appearance visible in the previous Settings UI.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PremiumPlanPanel")
        self.setStyleSheet(
            "QFrame#PremiumPlanPanel{background:transparent;border:none;}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Plan & Account")
        title.setStyleSheet(f"color:{NAVY};font-size:16px;font-weight:900;border:none;background:transparent;")
        note = QLabel("Your PrivacyGate plan, workspace entitlement and available tiers.")
        note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;background:transparent;")
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
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.cards: dict[PlanCode, QFrame] = {}
        self.markers: dict[PlanCode, QLabel] = {}
        self.buttons: dict[PlanCode, QPushButton] = {}

        plan_meta = {
            PlanCode.BASIC: (
                "protect",
                "Individual privacy",
                ["Local protection", "Local Library & Restore", "Personal workspace"],
            ),
            PlanCode.PRO: (
                "document",
                "Advanced individual workflows",
                ["Everything in Basic", "Advanced personal controls", "Premium individual features"],
            ),
            PlanCode.BUSINESS: (
                "workflow",
                "Teams & company policy",
                ["Everything in Pro", "Members & seats", "Managed company policy"],
            ),
            PlanCode.ENTERPRISE: (
                "settings",
                "Advanced organization control",
                ["Everything in Business", "Advanced administration", "Enterprise-ready controls"],
            ),
        }

        for column, definition in enumerate(all_plans()):
            object_name = f"PlanCard_{definition.code.value}"
            card = QFrame(objectName=object_name)
            card.setMinimumHeight(190)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 13, 14, 13)
            layout.setSpacing(6)
            icon_name, subtitle, bullets = plan_meta[definition.code]

            top = QHBoxLayout()
            bubble = QLabel()
            bubble.setFixedSize(38, 38)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setPixmap(icon(icon_name, color=TEAL, size=21).pixmap(21, 21))
            bubble.setStyleSheet("background:#E8F7F7;border:none;border-radius:19px;")
            top.addWidget(bubble)
            top.addStretch(1)
            marker = QLabel()
            marker.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            marker.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:900;border:none;background:transparent;")
            top.addWidget(marker)
            layout.addLayout(top)

            name = QLabel(definition.label)
            name.setStyleSheet(f"color:{NAVY};font-size:16px;font-weight:900;border:none;background:transparent;")
            sub = QLabel(subtitle)
            sub.setWordWrap(True)
            sub.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;background:transparent;")
            layout.addWidget(name)
            layout.addWidget(sub)
            layout.addSpacing(3)

            for bullet in bullets:
                item = QLabel(f"✓  {bullet}")
                item.setStyleSheet(f"color:{NAVY};font-size:8px;border:none;background:transparent;padding:1px 0;")
                layout.addWidget(item)

            layout.addStretch(1)
            button = QPushButton("Available plan")
            button.setEnabled(False)
            button.setMinimumHeight(30)
            button.setStyleSheet(
                "QPushButton{background:transparent;color:#78909E;border:none;border-top:1px solid #EDF2F5;"
                "padding:6px 4px;font-size:8px;font-weight:800;text-align:left;}"
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
            "background:#F3F8FA;border:none;border-radius:9px;padding:9px 11px;"
            f"color:{NAVY};font-size:8px;"
        )
        root.addWidget(self.account_summary)

    def update_state(self, state: TeamState) -> None:
        self.current_badge.setText(state.plan.label.upper())
        for code, card in self.cards.items():
            selected = code == state.plan
            object_name = card.objectName()
            card.setStyleSheet(
                (
                    f"QFrame#{object_name}{{background:#F1FBFB;border:2px solid #0B7F89;border-radius:13px;}}"
                )
                if selected
                else
                    f"QFrame#{object_name}{{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:13px;}}"
            )
            marker = self.markers[code]
            button = self.buttons[code]
            if selected:
                marker.setText("CURRENT PLAN")
                marker.setStyleSheet("color:#0B7F89;font-size:8px;font-weight:950;border:none;background:transparent;")
                button.setText("Current plan")
                button.setStyleSheet(
                    "QPushButton{background:transparent;color:#0B7F89;border:none;border-top:1px solid #CDE8E9;"
                    "padding:6px 4px;font-size:8px;font-weight:900;text-align:left;}"
                )
            else:
                marker.setText("")
                button.setText("Available plan")
                button.setStyleSheet(
                    "QPushButton{background:transparent;color:#78909E;border:none;border-top:1px solid #EDF2F5;"
                    "padding:6px 4px;font-size:8px;font-weight:800;text-align:left;}"
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
