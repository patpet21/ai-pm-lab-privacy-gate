from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ai_pm_lab_privacy_gate.domain.plans import PlanCode
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.ui.iconography import icon

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7180"
MUTED = "#64788A"
BORDER = "#DCE5EA"


class PlanAccountPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PremiumPlanAccount")
        self.setStyleSheet(
            "QFrame#PremiumPlanAccount{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:14px;}"
        )
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 17, 18, 17)
        root.setSpacing(16)

        icon_box = QLabel()
        icon_box.setFixedSize(48, 48)
        icon_box.setPixmap(icon("document", color=TEAL, size=25).pixmap(QSize(25, 25)))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(
            "background:#EAF7F7;border:1px solid #CBE8E8;border-radius:14px;"
        )
        root.addWidget(icon_box, 0, Qt.AlignmentFlag.AlignTop)

        center = QVBoxLayout()
        center.setSpacing(3)
        eyebrow = QLabel("PLAN & ACCOUNT")
        eyebrow.setStyleSheet(f"color:{TEAL};font-size:8px;font-weight:900;letter-spacing:1px;border:none;background:transparent;")
        self.title = QLabel("PrivacyGate Basic")
        self.title.setStyleSheet(f"color:{NAVY};font-size:17px;font-weight:950;border:none;background:transparent;")
        self.subtitle = QLabel("Individual local-first privacy")
        self.subtitle.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;background:transparent;")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(f"color:{INK};font-size:9px;border:none;background:transparent;")
        center.addWidget(eyebrow)
        center.addWidget(self.title)
        center.addWidget(self.subtitle)
        center.addSpacing(4)
        center.addWidget(self.summary)
        root.addLayout(center, 1)

        right = QVBoxLayout()
        right.setSpacing(7)
        self.current_badge = QLabel("BASIC")
        self.current_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_badge.setStyleSheet(
            "background:#EAF7F7;color:#0B7180;border:1px solid #C5E5E6;"
            "border-radius:10px;padding:6px 11px;font-size:8px;font-weight:900;"
        )
        self.manage_button = QPushButton("View plan details", objectName="Secondary")
        self.manage_button.setIcon(icon("external", color=INK, size=16))
        self.manage_button.setIconSize(QSize(16, 16))
        self.manage_button.setEnabled(False)
        self.manage_button.setToolTip("Plan selection and access requests are coming in the next test step.")
        right.addWidget(self.current_badge, 0, Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.manage_button, 0, Qt.AlignmentFlag.AlignRight)
        right.addStretch(1)
        root.addLayout(right)

    def update_state(self, state: TeamState) -> None:
        plan = state.plan
        self.current_badge.setText(plan.label.upper())
        self.title.setText(f"PrivacyGate {plan.label}")

        if plan is PlanCode.BASIC:
            self.subtitle.setText("Individual local-first privacy")
        elif plan is PlanCode.PRO:
            self.subtitle.setText("Advanced individual PrivacyGate workflows")
        elif plan is PlanCode.BUSINESS:
            self.subtitle.setText("Organization privacy policy and managed workspaces")
        else:
            self.subtitle.setText("Enterprise organization controls")

        if state.organization_id:
            self.summary.setText(
                f"{state.organization_name or 'Organization'}  •  {state.role.title()}  •  "
                f"Entitlement {state.entitlement_status.title()}\n"
                "Organization policy is managed from the Organization workspace."
            )
        else:
            self.summary.setText(
                f"Individual account  •  Entitlement {state.entitlement_status.title()}\n"
                "Documents, Library contents and restore mappings remain local on this device."
            )


def install_plan_account_panel(settings_page, state: TeamState) -> PlanAccountPanel:
    panel = getattr(settings_page, "_privacygate_plan_account_panel", None)
    if isinstance(panel, PlanAccountPanel):
        panel.update_state(state)
        return panel

    panel = PlanAccountPanel(settings_page)
    mount = getattr(settings_page, "mount_plan_panel", None)
    if callable(mount):
        mount(panel)
    else:
        root = settings_page.layout()
        if isinstance(root, QVBoxLayout):
            root.insertWidget(1, panel)
    settings_page._privacygate_plan_account_panel = panel
    panel.update_state(state)
    return panel
