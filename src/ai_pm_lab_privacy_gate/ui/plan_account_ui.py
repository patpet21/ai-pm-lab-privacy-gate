from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from ai_pm_lab_privacy_gate.domain.plans import PlanCode, all_plans
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState


NAVY = "#062B4F"
TEAL = "#0B7180"
MUTED = "#61798A"
BORDER = "#DCE5EA"
SOFT = "#F7FAFC"


class PlanAccountPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(9)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Plan & Account")
        title.setStyleSheet(f"color:{NAVY};font-size:17px;font-weight:900;")
        note = QLabel(
            "Your plan is assigned by PrivacyGate entitlement. Business and Enterprise "
            "organization controls are managed from Organization."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};font-size:9px;")
        title_box.addWidget(title)
        title_box.addWidget(note)
        top.addLayout(title_box, 1)

        self.current_badge = QLabel("BASIC")
        self.current_badge.setStyleSheet(
            "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
            "border-radius:9px;padding:6px 10px;font-size:9px;font-weight:900;"
        )
        top.addWidget(self.current_badge, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(top)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.cards: dict[PlanCode, QFrame] = {}
        self.markers: dict[PlanCode, QLabel] = {}
        for column, definition in enumerate(all_plans()):
            card = QFrame()
            layout = QVBoxLayout(card)
            layout.setContentsMargins(11, 9, 11, 9)
            layout.setSpacing(3)
            name = QLabel(definition.label)
            name.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:900;")
            desc = QLabel(definition.description)
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color:{MUTED};font-size:8px;")
            marker = QLabel()
            marker.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:900;")
            layout.addWidget(name)
            layout.addWidget(desc)
            layout.addStretch(1)
            layout.addWidget(marker)
            grid.addWidget(card, 0, column)
            self.cards[definition.code] = card
            self.markers[definition.code] = marker
        root.addLayout(grid)

        self.account_summary = QLabel()
        self.account_summary.setWordWrap(True)
        self.account_summary.setStyleSheet(
            f"background:{SOFT};border:1px solid {BORDER};border-radius:8px;"
            f"padding:8px;color:{NAVY};font-size:9px;"
        )
        root.addWidget(self.account_summary)

    def update_state(self, state: TeamState) -> None:
        self.current_badge.setText(state.plan.label.upper())
        for code, card in self.cards.items():
            selected = code == state.plan
            card.setStyleSheet(
                (
                    "QFrame{background:#F0FAFA;border:2px solid #0B7180;border-radius:10px;}"
                )
                if selected
                else (
                    f"QFrame{{background:#FFFFFF;border:1px solid {BORDER};border-radius:10px;}}"
                )
            )
            if selected:
                self.markers[code].setText("CURRENT PLAN")
                self.markers[code].setStyleSheet(
                    f"color:{TEAL};font-size:8px;font-weight:950;"
                )
            elif code is PlanCode.BASIC:
                self.markers[code].setText("FREE • INDIVIDUAL")
            elif code is PlanCode.PRO:
                self.markers[code].setText("PREMIUM • INDIVIDUAL")
            elif code is PlanCode.BUSINESS:
                self.markers[code].setText("ORGANIZATION + POLICY")
            else:
                self.markers[code].setText("ADVANCED ORGANIZATION")

        if state.organization_id:
            self.account_summary.setText(
                f"Organization: {state.organization_name or 'Organization'}  •  "
                f"Role: {state.role.title()}  •  "
                f"Entitlement: {state.entitlement_status.title()}"
            )
        else:
            self.account_summary.setText(
                f"Individual account  •  {state.plan.label}  •  "
                f"Entitlement: {state.entitlement_status.title()}"
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
