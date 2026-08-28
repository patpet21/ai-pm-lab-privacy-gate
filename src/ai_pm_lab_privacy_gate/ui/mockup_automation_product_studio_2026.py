from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_mcp_automation_studio_2026 import (
    BLUE,
    BLUE_DARK,
    BLUE_SOFT,
    BORDER,
    CANVAS,
    GREEN,
    INK,
    MUTED,
    SURFACE,
    _ResponsiveGrid,
    _action_button,
    _page_shell,
    _safe_contact,
    _section_title,
    _show_use_case,
)

AMBER = "#B54708"
AMBER_SOFT = "#FFF7E8"
RED = "#B42318"
RED_SOFT = "#FEF3F2"
GREEN_SOFT = "#ECFDF3"
PURPLE = "#6941C6"
PURPLE_SOFT = "#F4F3FF"
SLATE = "#344054"


def _preview_badge(text: str = "PREVIEW DATA") -> QLabel:
    badge = QLabel(text)
    badge.setStyleSheet(
        "background:#F2F4F7;color:#475467;border:1px solid #E4E7EC;border-radius:8px;"
        "padding:4px 7px;font-size:7px;font-weight:900;"
    )
    return badge


def _small_button(text: str, callback, *, primary: bool = False, danger: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(32)
    if primary:
        button.setStyleSheet(
            f"QPushButton{{background:{BLUE};color:white;border:1px solid {BLUE};border-radius:8px;"
            "padding:6px 10px;font-size:8px;font-weight:850;}"
            f"QPushButton:hover{{background:{BLUE_DARK};border-color:{BLUE_DARK};}}"
        )
    elif danger:
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#B42318;border:1px solid #FDA29B;border-radius:8px;"
            "padding:6px 10px;font-size:8px;font-weight:850;}"
            "QPushButton:hover{background:#FEF3F2;}"
        )
    else:
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:8px;"
            "padding:6px 10px;font-size:8px;font-weight:800;}"
            "QPushButton:hover{background:#F9FAFB;border-color:#98A2B3;}"
        )
    button.clicked.connect(lambda _checked=False: callback())
    return button


def _status_chip(text: str, *, tone: str = "green") -> QLabel:
    palette = {
        "green": (GREEN, GREEN_SOFT, "#ABEFC6"),
        "amber": (AMBER, AMBER_SOFT, "#FEDF89"),
        "red": (RED, RED_SOFT, "#FECDCA"),
        "blue": (BLUE, BLUE_SOFT, "#CFE0FF"),
        "purple": (PURPLE, PURPLE_SOFT, "#D9D6FE"),
        "gray": ("#475467", "#F2F4F7", "#E4E7EC"),
    }
    fg, bg, border = palette.get(tone, palette["gray"])
    chip = QLabel(text.upper())
    chip.setStyleSheet(
        f"background:{bg};color:{fg};border:1px solid {border};border-radius:8px;"
        "padding:4px 7px;font-size:7px;font-weight:950;"
    )
    return chip


def _metric_card(icon_name: str, value: str, label: str, detail: str, *, tone: str = "blue") -> QFrame:
    tones = {
        "blue": (BLUE, BLUE_SOFT),
        "green": (GREEN, GREEN_SOFT),
        "amber": (AMBER, AMBER_SOFT),
        "red": (RED, RED_SOFT),
    }
    accent, soft = tones.get(tone, tones["blue"])
    card = QFrame()
    card.setMinimumHeight(98)
    card.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:13px;}}")
    row = QHBoxLayout(card)
    row.setContentsMargins(13, 12, 13, 12)
    row.setSpacing(10)

    bubble = QLabel()
    bubble.setFixedSize(36, 36)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon(icon_name, color=accent, size=18).pixmap(18, 18))
    bubble.setStyleSheet(f"background:{soft};border:none;border-radius:10px;")
    row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(1)
    number = QLabel(value)
    number.setStyleSheet(f"color:{INK};font-size:19px;font-weight:950;border:none;background:transparent;")
    heading = QLabel(label)
    heading.setStyleSheet(f"color:{INK};font-size:8.5px;font-weight:900;border:none;background:transparent;")
    note = QLabel(detail)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:7px;border:none;background:transparent;")
    copy.addWidget(number)
    copy.addWidget(heading)
    copy.addWidget(note)
    row.addLayout(copy, 1)
    return card


def _metric_strip(cards: list[QWidget]) -> QWidget:
    host = QWidget()
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(10)
    for index, card in enumerate(cards):
        grid.addWidget(card, 0, index)
        grid.setColumnStretch(index, 1)
    return host


def _flow_chip(text: str, icon_name: str, *, protected: bool = False, external: bool = False) -> QFrame:
    frame = QFrame()
    if protected:
        frame.setStyleSheet("QFrame{background:#EEF4FF;border:1px solid #BBD3FF;border-radius:9px;}")
        fg = BLUE
    elif external:
        frame.setStyleSheet("QFrame{background:#F8FAFC;border:1px solid #D0D5DD;border-radius:9px;}")
        fg = SLATE
    else:
        frame.setStyleSheet("QFrame{background:#FFFFFF;border:1px solid #E4E7EC;border-radius:9px;}")
        fg = SLATE
    row = QHBoxLayout(frame)
    row.setContentsMargins(8, 6, 8, 6)
    row.setSpacing(5)
    glyph = QLabel()
    glyph.setPixmap(icon(icon_name, color=fg, size=14).pixmap(14, 14))
    glyph.setStyleSheet("border:none;background:transparent;")
    row.addWidget(glyph)
    label = QLabel(text)
    label.setStyleSheet(f"color:{fg};font-size:8px;font-weight:850;border:none;background:transparent;")
    row.addWidget(label)
    return frame


def _flow_row(source: str, destination: str, source_icon: str = "contact", destination_icon: str = "library") -> QWidget:
    widget = QWidget()
    row = QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(7)
    row.addWidget(_flow_chip(source, source_icon))
    arrow1 = QLabel("→")
    arrow1.setStyleSheet("color:#98A2B3;font-size:12px;font-weight:900;border:none;")
    row.addWidget(arrow1)
    row.addWidget(_flow_chip("PrivacyGate", "protect", protected=True))
    arrow2 = QLabel("→")
    arrow2.setStyleSheet("color:#98A2B3;font-size:12px;font-weight:900;border:none;")
    row.addWidget(arrow2)
    row.addWidget(_flow_chip(destination, destination_icon, external=destination not in {"Library", "Local folder"}))
    row.addStretch(1)
    return widget


def _detail_item(label: str, value: str, *, value_color: str = SLATE) -> QWidget:
    item = QWidget()
    box = QVBoxLayout(item)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(2)
    key = QLabel(label.upper())
    key.setStyleSheet("color:#98A2B3;font-size:6.5px;font-weight:900;border:none;")
    val = QLabel(value)
    val.setWordWrap(True)
    val.setStyleSheet(f"color:{value_color};font-size:8px;font-weight:800;border:none;")
    box.addWidget(key)
    box.addWidget(val)
    return item


def _show_preview_action(page: QWidget, title: str, message: str) -> None:
    box = QMessageBox(page)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(title)
    box.setInformativeText(message)
    box.exec()


def _automation_card(
    page: QWidget,
    *,
    title: str,
    source: str,
    destination: str,
    trigger: str,
    workspace: str,
    privacy_profile: str,
    approval: str,
    policy: str,
    last_run: str,
    status: str,
    status_tone: str,
    source_icon: str = "contact",
    destination_icon: str = "library",
) -> QFrame:
    card = QFrame()
    card.setMinimumHeight(262)
    card.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:14px;}}")
    box = QVBoxLayout(card)
    box.setContentsMargins(16, 15, 16, 14)
    box.setSpacing(11)

    top = QHBoxLayout()
    title_box = QVBoxLayout()
    title_box.setSpacing(2)
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{INK};font-size:12px;font-weight:950;border:none;")
    subtitle = QLabel("Protected workflow")
    subtitle.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;")
    title_box.addWidget(heading)
    title_box.addWidget(subtitle)
    top.addLayout(title_box, 1)
    top.addWidget(_status_chip(status, tone=status_tone), 0, Qt.AlignmentFlag.AlignTop)
    box.addLayout(top)

    box.addWidget(_flow_row(source, destination, source_icon, destination_icon))

    details = QGridLayout()
    details.setHorizontalSpacing(14)
    details.setVerticalSpacing(9)
    fields = [
        ("Trigger", trigger),
        ("Workspace", workspace),
        ("Privacy profile", privacy_profile),
        ("Approval", approval),
        ("Policy", policy),
        ("Last run", last_run),
    ]
    for index, (key, value) in enumerate(fields):
        details.addWidget(_detail_item(key, value), index // 3, index % 3)
    box.addLayout(details)

    boundary = QFrame()
    boundary.setStyleSheet("QFrame{background:#F8FAFC;border:1px solid #EAECF0;border-radius:9px;}")
    boundary_row = QHBoxLayout(boundary)
    boundary_row.setContentsMargins(9, 7, 9, 7)
    shield = QLabel()
    shield.setPixmap(icon("protect", color=BLUE, size=14).pixmap(14, 14))
    shield.setStyleSheet("border:none;background:transparent;")
    boundary_row.addWidget(shield)
    boundary_text = QLabel("Original data → local protection + residual check → protected data only")
    boundary_text.setWordWrap(True)
    boundary_text.setStyleSheet("color:#475467;font-size:7.5px;font-weight:750;border:none;background:transparent;")
    boundary_row.addWidget(boundary_text, 1)
    box.addWidget(boundary)

    actions = QHBoxLayout()
    actions.setSpacing(7)
    actions.addWidget(
        _small_button(
            "Run now",
            lambda: _show_preview_action(
                page,
                "Run automation",
                "This redesign is a product preview. The production runtime will execute the trigger, local PrivacyGate protection, policy check, approval rule and destination in that order. No original sensitive payload belongs in the run log.",
            ),
            primary=True,
        )
    )
    actions.addWidget(_small_button("Edit", lambda: _show_builder(page, title)))
    pause_label = "Resume" if status.lower() == "paused" else "Pause"
    actions.addWidget(
        _small_button(
            pause_label,
            lambda: _show_preview_action(
                page,
                f"{pause_label} automation",
                "Automation status controls are represented in this UI preview and will be wired to the runtime state store.",
            ),
        )
    )
    actions.addStretch(1)
    actions.addWidget(_small_button("•••", lambda: _show_preview_action(page, "Automation actions", "Duplicate · View policy snapshot · Archive")))
    box.addLayout(actions)
    return card


def _step_card(stage: str, title: str, description: str, icon_name: str, *, privacy: bool = False) -> QFrame:
    card = QFrame()
    if privacy:
        card.setStyleSheet("QFrame{background:#EEF4FF;border:1px solid #BBD3FF;border-radius:12px;}")
        stage_color = BLUE
    else:
        card.setStyleSheet("QFrame{background:#FFFFFF;border:1px solid #E4E7EC;border-radius:12px;}")
        stage_color = "#475467"
    row = QHBoxLayout(card)
    row.setContentsMargins(13, 11, 13, 11)
    row.setSpacing(11)
    bubble = QLabel()
    bubble.setFixedSize(34, 34)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon(icon_name, color=stage_color, size=17).pixmap(17, 17))
    bubble.setStyleSheet("background:#FFFFFF;border:1px solid #E4E7EC;border-radius:9px;")
    row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)
    copy = QVBoxLayout()
    copy.setSpacing(2)
    eyebrow = QLabel(stage)
    eyebrow.setStyleSheet(f"color:{stage_color};font-size:6.5px;font-weight:950;border:none;background:transparent;")
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{INK};font-size:10px;font-weight:900;border:none;background:transparent;")
    note = QLabel(description)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;background:transparent;")
    copy.addWidget(eyebrow)
    copy.addWidget(heading)
    copy.addWidget(note)
    row.addLayout(copy, 1)
    return card


def _show_builder(page: QWidget, template_name: str = "New automation") -> None:
    dialog = QDialog(page)
    dialog.setWindowTitle("Automation Builder")
    dialog.setMinimumWidth(720)
    dialog.setMinimumHeight(690)
    dialog.setStyleSheet(f"QDialog{{background:{CANVAS};}}")

    root = QVBoxLayout(dialog)
    root.setContentsMargins(20, 18, 20, 18)
    root.setSpacing(12)

    top = QHBoxLayout()
    copy = QVBoxLayout()
    copy.setSpacing(2)
    heading = QLabel(template_name if template_name != "New automation" else "Build a protected automation")
    heading.setStyleSheet(f"color:{INK};font-size:19px;font-weight:950;border:none;")
    note = QLabel("A guided workflow builder: business trigger first, PrivacyGate boundary always visible, human review where it matters.")
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
    copy.addWidget(heading)
    copy.addWidget(note)
    top.addLayout(copy, 1)
    top.addWidget(_status_chip("Privacy-first", tone="blue"), 0, Qt.AlignmentFlag.AlignTop)
    root.addLayout(top)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
    host = QWidget()
    host.setStyleSheet("background:transparent;")
    flow = QVBoxLayout(host)
    flow.setContentsMargins(0, 0, 0, 0)
    flow.setSpacing(7)

    steps = [
        ("WHEN", "New Gmail message", "Choose a connected source and the event that starts the workflow.", "contact", False),
        ("GET", "Email body + attachment", "Only the data required by the workflow moves to the local protection step.", "document", False),
        ("PRIVACYGATE", "Scan → Protect → Residual Check → Policy Check", "The privacy boundary is mandatory before any external AI or business destination.", "protect", True),
        ("APPROVAL", "Require human approval for Medium / High", "Low risk can be auto-approved when organization policy explicitly allows it.", "check", False),
        ("THEN", "Send protected copy / create task / save", "Only the protected output is eligible for an approved external destination.", "external", False),
    ]
    for index, (stage, title, description, icon_name, privacy) in enumerate(steps):
        flow.addWidget(_step_card(stage, title, description, icon_name, privacy=privacy))
        if index < len(steps) - 1:
            arrow = QLabel("↓")
            arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
            arrow.setStyleSheet("color:#98A2B3;font-size:13px;font-weight:950;border:none;")
            flow.addWidget(arrow)

    boundary = QFrame()
    boundary.setStyleSheet("QFrame{background:#101828;border:1px solid #101828;border-radius:12px;}")
    boundary_row = QHBoxLayout(boundary)
    boundary_row.setContentsMargins(13, 10, 13, 10)
    left = QLabel("ORIGINAL DATA")
    left.setStyleSheet("color:#D0D5DD;font-size:7px;font-weight:900;border:none;background:transparent;")
    center = QLabel("Protected locally by PrivacyGate")
    center.setStyleSheet("color:#FFFFFF;font-size:8px;font-weight:950;border:none;background:transparent;")
    right = QLabel("PROTECTED DATA ONLY")
    right.setStyleSheet("color:#B2DDFF;font-size:7px;font-weight:900;border:none;background:transparent;")
    boundary_row.addWidget(left)
    boundary_row.addStretch(1)
    boundary_row.addWidget(center)
    boundary_row.addStretch(1)
    boundary_row.addWidget(right)
    flow.addWidget(boundary)

    managed = QLabel("Organization-ready · Policy version snapshot · Allowed destinations · Approval rule · Owner · Metadata-only run history")
    managed.setWordWrap(True)
    managed.setStyleSheet("color:#475467;font-size:7.5px;font-weight:750;border:none;padding:3px;")
    flow.addWidget(managed)
    scroll.setWidget(host)
    root.addWidget(scroll, 1)

    actions = QHBoxLayout()
    actions.addWidget(_small_button("Cancel", dialog.reject))
    actions.addStretch(1)
    actions.addWidget(
        _small_button(
            "Save draft",
            lambda: _show_preview_action(
                page,
                "Draft saved",
                "The final runtime will persist only workflow configuration and metadata here, never the original sensitive payload.",
            ),
        )
    )
    actions.addWidget(
        _small_button(
            "Activate automation",
            lambda: _show_preview_action(
                page,
                "Activation preview",
                "Before activation, PrivacyGate will validate connected apps, privacy profile, allowed AI destinations, approval rules and organization policy compatibility.",
            ),
            primary=True,
        )
    )
    root.addLayout(actions)
    dialog.exec()


def _template_card(
    page: QWidget,
    *,
    icon_name: str,
    title: str,
    description: str,
    badge: str,
    audience: str,
    workflow: str,
    outcome: str,
) -> QFrame:
    card = QFrame()
    card.setMinimumHeight(218)
    card.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:14px;}}")
    box = QVBoxLayout(card)
    box.setContentsMargins(15, 14, 15, 14)
    box.setSpacing(8)

    top = QHBoxLayout()
    bubble = QLabel()
    bubble.setFixedSize(38, 38)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon(icon_name, color=BLUE, size=19).pixmap(19, 19))
    bubble.setStyleSheet(f"background:{BLUE_SOFT};border:none;border-radius:11px;")
    top.addWidget(bubble)
    top.addStretch(1)
    top.addWidget(_status_chip(badge, tone="gray"), 0, Qt.AlignmentFlag.AlignTop)
    box.addLayout(top)

    heading = QLabel(title)
    heading.setWordWrap(True)
    heading.setStyleSheet(f"color:{INK};font-size:11px;font-weight:950;border:none;")
    note = QLabel(description)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
    box.addWidget(heading)
    box.addWidget(note)
    box.addStretch(1)

    actions = QHBoxLayout()
    actions.setSpacing(7)
    actions.addWidget(_small_button("Preview flow", lambda: _show_use_case(page, title, audience, workflow, outcome)))
    actions.addWidget(_small_button("Use template", lambda: _show_builder(page, title), primary=True))
    box.addLayout(actions)
    return card


def _advisory_banner(page: QWidget) -> QFrame:
    banner = QFrame()
    banner.setStyleSheet("QFrame{background:#101828;border:1px solid #101828;border-radius:15px;}")
    row = QHBoxLayout(banner)
    row.setContentsMargins(17, 15, 17, 15)
    row.setSpacing(13)

    bubble = QLabel()
    bubble.setFixedSize(42, 42)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon("workflow", color="#FFFFFF", size=21).pixmap(21, 21))
    bubble.setStyleSheet("background:#344054;border:none;border-radius:12px;")
    row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(3)
    eyebrow = QLabel("AI & AUTOMATION ADVISORY · PM-LED DELIVERY")
    eyebrow.setStyleSheet("color:#84CAFF;font-size:7px;font-weight:950;border:none;background:transparent;")
    title = QLabel("Have a business process worth automating?")
    title.setStyleSheet("color:#FFFFFF;font-size:12px;font-weight:950;border:none;background:transparent;")
    note = QLabel("Turn a real workflow into a scoped AI use case: process map → privacy boundary → human approvals → tool integration → implementation roadmap.")
    note.setWordWrap(True)
    note.setStyleSheet("color:#D0D5DD;font-size:8px;border:none;background:transparent;")
    copy.addWidget(eyebrow)
    copy.addWidget(title)
    copy.addWidget(note)
    row.addLayout(copy, 1)

    row.addWidget(_small_button("Discuss your workflow", lambda: _safe_contact(page), primary=True), 0, Qt.AlignmentFlag.AlignVCenter)
    return banner


def _my_automations_tab(page: QWidget) -> QWidget:
    tab = QWidget()
    tab.setStyleSheet("background:transparent;")
    body = QVBoxLayout(tab)
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(12)
    body.addWidget(_section_title("My automations", "Operational workflows with a visible privacy boundary, approval rule and organization policy status."))

    cards = [
        _automation_card(
            page,
            title="Gmail → Protect → Library",
            source="Gmail",
            destination="Library",
            trigger="New message + attachment",
            workspace="privacygataway",
            privacy_profile="Real Estate Sensitive",
            approval="Not required",
            policy="✓ Policy v2 allowed",
            last_run="Today · 18:42 · Success",
            status="Active",
            status_tone="green",
            source_icon="contact",
            destination_icon="library",
        ),
        _automation_card(
            page,
            title="Drive → Protect → ChatGPT",
            source="Google Drive",
            destination="ChatGPT",
            trigger="New file in approved folder",
            workspace="privacygataway",
            privacy_profile="Standard + residual check",
            approval="Required · Medium+",
            policy="✓ Allowed with approval",
            last_run="Today · 17:11 · Waiting",
            status="Needs approval",
            status_tone="amber",
            source_icon="document",
            destination_icon="external",
        ),
        _automation_card(
            page,
            title="Folder → Protect → ClickUp",
            source="Local folder",
            destination="ClickUp",
            trigger="Manual / watched folder",
            workspace="privacygataway",
            privacy_profile="Project Sensitive",
            approval="Low risk auto-approved",
            policy="✓ Policy v2 allowed",
            last_run="Yesterday · 16:05 · Success",
            status="Active",
            status_tone="green",
            source_icon="document",
            destination_icon="workflow",
        ),
    ]
    body.addWidget(_ResponsiveGrid(cards, max_columns=2))

    custom = QFrame()
    custom.setStyleSheet("QFrame{background:#F0F7FF;border:1px solid #CFE0FF;border-radius:13px;}")
    row = QHBoxLayout(custom)
    row.setContentsMargins(14, 12, 14, 12)
    shield = QLabel()
    shield.setPixmap(icon("protect", color=BLUE, size=19).pixmap(19, 19))
    shield.setStyleSheet("border:none;background:transparent;")
    row.addWidget(shield)
    copy = QVBoxLayout()
    copy.setSpacing(1)
    heading = QLabel("PrivacyGate is the control point — not just another automation step")
    heading.setStyleSheet(f"color:{INK};font-size:9px;font-weight:900;border:none;background:transparent;")
    note = QLabel("Original data stays on the protected side of the workflow. External AI and business apps receive only policy-approved protected output.")
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;background:transparent;")
    copy.addWidget(heading)
    copy.addWidget(note)
    row.addLayout(copy, 1)
    body.addWidget(custom)
    return tab


def _templates_tab(page: QWidget) -> QWidget:
    tab = QWidget()
    tab.setStyleSheet("background:transparent;")
    body = QVBoxLayout(tab)
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(12)
    body.addWidget(_section_title("Workflow templates", "Start from a proven business pattern, preview the privacy-aware flow, then adapt it to the client's real systems and approval rules."))

    templates = [
        dict(
            icon_name="contact",
            title="Social content automation",
            description="Approved idea → AI-assisted draft → human approval → schedule Instagram and LinkedIn publishing.",
            badge="Marketing",
            audience="Small businesses, real-estate teams, consultants and local brands that post repeatedly but lack a consistent content process.",
            workflow="Content brief → AI-assisted draft → brand/privacy review → human approval → scheduler → Instagram / LinkedIn.",
            outcome="A repeatable content engine with approval before publishing and less manual copying between tools.",
        ),
        dict(
            icon_name="workflow",
            title="Lead intake & follow-up",
            description="New form or email inquiry → classify → CRM/task → assign owner → prepare approved follow-up.",
            badge="Sales",
            audience="Service businesses, brokers, contractors and small sales teams.",
            workflow="Form/email → validate and classify → CRM/ClickUp/Asana → owner assignment → human-approved follow-up.",
            outcome="Faster lead response and fewer inquiries lost between inboxes and task systems.",
        ),
        dict(
            icon_name="document",
            title="Email & document intake",
            description="Inbound email/file → PrivacyGate → classify → approved storage → task or notification.",
            badge="Operations",
            audience="Property managers, project teams and professional-services firms receiving documents by email.",
            workflow="Inbox/file → local privacy protection → classification → approved storage → task / notification.",
            outcome="A cleaner intake queue with sensitive data handled before downstream AI or automation steps.",
        ),
        dict(
            icon_name="protect",
            title="Property maintenance intake",
            description="Tenant request → protect personal data → categorize issue → create maintenance task → notify owner.",
            badge="Property",
            audience="Property managers and small building operations teams.",
            workflow="Maintenance request → protect tenant data → classify urgency/category → task system → assignment and status notification.",
            outcome="Less manual triage and a consistent handoff from incoming request to accountable task owner.",
        ),
        dict(
            icon_name="contact",
            title="Meeting to tasks",
            description="Meeting notes → protect sensitive details → extract actions → ClickUp/Asana → reviewable summary.",
            badge="PM",
            audience="Project managers, agencies and operations teams with recurring meetings.",
            workflow="Meeting notes → privacy review → action extraction → task creation → owner/deadline review → summary.",
            outcome="Fewer missed actions and less manual transcription from meeting notes into project tools.",
        ),
        dict(
            icon_name="library",
            title="Owner / client reporting",
            description="Approved source updates → protected AI summary → human review → recurring client delivery.",
            badge="Reporting",
            audience="Property managers, consultants and project teams producing recurring status reports.",
            workflow="Approved source updates → consolidate → protect sensitive details → AI-assisted summary → human approval → email/report delivery.",
            outcome="Consistent recurring reporting with less manual compilation and a clear review point before delivery.",
        ),
    ]
    cards = [_template_card(page, **spec) for spec in templates]
    body.addWidget(_ResponsiveGrid(cards, max_columns=3))
    body.addWidget(_advisory_banner(page))
    return tab


def _timeline_event(time_text: str, title: str, detail: str, *, tone: str = "green") -> QWidget:
    widget = QWidget()
    row = QHBoxLayout(widget)
    row.setContentsMargins(0, 5, 0, 5)
    row.setSpacing(10)
    time = QLabel(time_text)
    time.setFixedWidth(55)
    time.setStyleSheet("color:#98A2B3;font-size:7px;font-weight:800;border:none;")
    row.addWidget(time, 0, Qt.AlignmentFlag.AlignTop)
    dot = QLabel("●")
    dot_color = {"green": GREEN, "blue": BLUE, "amber": AMBER, "red": RED}.get(tone, BLUE)
    dot.setStyleSheet(f"color:{dot_color};font-size:10px;border:none;")
    row.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
    copy = QVBoxLayout()
    copy.setSpacing(1)
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{INK};font-size:8.5px;font-weight:850;border:none;")
    note = QLabel(detail)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;")
    copy.addWidget(heading)
    copy.addWidget(note)
    row.addLayout(copy, 1)
    return widget


def _run_summary_card(title: str, route: str, time_text: str, result: str, tone: str, detail: str) -> QFrame:
    card = QFrame()
    card.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:12px;}}")
    box = QVBoxLayout(card)
    box.setContentsMargins(13, 12, 13, 12)
    box.setSpacing(5)
    top = QHBoxLayout()
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{INK};font-size:9.5px;font-weight:900;border:none;")
    top.addWidget(heading, 1)
    top.addWidget(_status_chip(result, tone=tone))
    box.addLayout(top)
    route_label = QLabel(route)
    route_label.setStyleSheet("color:#475467;font-size:8px;font-weight:800;border:none;")
    note = QLabel(detail)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;")
    stamp = QLabel(time_text)
    stamp.setStyleSheet("color:#98A2B3;font-size:7px;font-weight:800;border:none;")
    box.addWidget(route_label)
    box.addWidget(note)
    box.addWidget(stamp)
    return card


def _runs_tab(page: QWidget) -> QWidget:
    tab = QWidget()
    tab.setStyleSheet("background:transparent;")
    body = QVBoxLayout(tab)
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(12)

    banner = QFrame()
    banner.setStyleSheet("QFrame{background:#F0F7FF;border:1px solid #CFE0FF;border-radius:13px;}")
    row = QHBoxLayout(banner)
    row.setContentsMargins(14, 11, 14, 11)
    glyph = QLabel()
    glyph.setPixmap(icon("history", color=BLUE, size=18).pixmap(18, 18))
    glyph.setStyleSheet("border:none;background:transparent;")
    row.addWidget(glyph)
    copy = QVBoxLayout()
    copy.setSpacing(1)
    heading = QLabel("Metadata-only run history")
    heading.setStyleSheet(f"color:{INK};font-size:9px;font-weight:900;border:none;background:transparent;")
    note = QLabel("Track triggers, finding counts, protection outcome, policy decision, approval and destination — never original document content.")
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;background:transparent;")
    copy.addWidget(heading)
    copy.addWidget(note)
    row.addLayout(copy, 1)
    row.addWidget(_preview_badge())
    body.addWidget(banner)

    body.addWidget(_section_title("Recent runs", "Operational visibility without turning the audit log into another copy of sensitive data."))
    summaries = [
        _run_summary_card("Gmail intake #1842", "Gmail → PrivacyGate → ClickUp", "Today · 18:43 · 1m 19s", "Success", "green", "14 findings protected · residual 0 · Policy v2 passed · approved"),
        _run_summary_card("Drive handoff #1841", "Drive → PrivacyGate → ChatGPT", "Today · 17:11", "Waiting", "amber", "12 findings protected · residual 0 · medium risk · approval required"),
        _run_summary_card("Owner report #1840", "Library → PrivacyGate → Email", "Today · 15:05 · 42s", "Blocked", "red", "Policy v2 blocked destination before external handoff · no payload sent"),
    ]
    body.addWidget(_ResponsiveGrid(summaries, max_columns=3))

    timeline = QFrame()
    timeline.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:14px;}}")
    box = QVBoxLayout(timeline)
    box.setContentsMargins(15, 13, 15, 13)
    box.setSpacing(0)
    top = QHBoxLayout()
    title = QLabel("Latest successful run · Gmail intake #1842")
    title.setStyleSheet(f"color:{INK};font-size:10px;font-weight:950;border:none;")
    top.addWidget(title, 1)
    top.addWidget(_status_chip("Policy v2", tone="blue"))
    box.addLayout(top)
    events = [
        ("18:42:04", "Gmail trigger received", "Approved connected account · attachment available", "blue"),
        ("18:42:05", "Attachment loaded locally", "Source metadata captured; original content not added to run history", "blue"),
        ("18:42:06", "14 findings detected", "Real Estate Sensitive privacy profile", "blue"),
        ("18:42:07", "14 findings protected", "Local protection completed", "green"),
        ("18:42:07", "Residual check passed", "Residual findings: 0", "green"),
        ("18:42:08", "Policy v2 passed", "Destination allowed with human approval", "green"),
        ("18:43:21", "Human approved", "Approval metadata recorded", "green"),
        ("18:43:23", "ClickUp task created", "Protected data only sent to destination", "green"),
    ]
    for time_text, event_title, detail, tone in events:
        box.addWidget(_timeline_event(time_text, event_title, detail, tone=tone))
    body.addWidget(timeline)
    return tab


def _approval_rule(title: str, description: str, outcome: str, *, tone: str) -> QFrame:
    card = QFrame()
    card.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:11px;}}")
    row = QHBoxLayout(card)
    row.setContentsMargins(12, 10, 12, 10)
    row.setSpacing(9)
    row.addWidget(_status_chip(title, tone=tone))
    copy = QVBoxLayout()
    copy.setSpacing(1)
    note = QLabel(description)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{SLATE};font-size:8px;font-weight:800;border:none;")
    result = QLabel(outcome)
    result.setStyleSheet(f"color:{MUTED};font-size:7px;border:none;")
    copy.addWidget(note)
    copy.addWidget(result)
    row.addLayout(copy, 1)
    return card


def _approvals_tab(page: QWidget) -> QWidget:
    tab = QWidget()
    tab.setStyleSheet("background:transparent;")
    body = QVBoxLayout(tab)
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(12)
    body.addWidget(_section_title("Approval queue", "Review the protected copy and policy result before an approved external AI or business destination receives anything."))

    queue = QFrame()
    queue.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid #FEDF89;border-radius:15px;}}")
    box = QVBoxLayout(queue)
    box.setContentsMargins(16, 14, 16, 14)
    box.setSpacing(11)
    top = QHBoxLayout()
    title_box = QVBoxLayout()
    eyebrow = QLabel("WAITING FOR APPROVAL")
    eyebrow.setStyleSheet(f"color:{AMBER};font-size:7px;font-weight:950;border:none;")
    heading = QLabel("Drive → PrivacyGate → ChatGPT")
    heading.setStyleSheet(f"color:{INK};font-size:13px;font-weight:950;border:none;")
    title_box.addWidget(eyebrow)
    title_box.addWidget(heading)
    top.addLayout(title_box, 1)
    top.addWidget(_status_chip("Medium risk", tone="amber"))
    box.addLayout(top)

    box.addWidget(_flow_row("Google Drive", "ChatGPT", "document", "external"))

    stats = QGridLayout()
    stats.setHorizontalSpacing(18)
    stats.setVerticalSpacing(8)
    values = [
        ("Findings protected", "12"),
        ("Residual findings", "0"),
        ("Policy", "Allowed with approval"),
        ("Workspace", "privacygataway"),
        ("Privacy profile", "Standard + residual check"),
        ("Destination", "ChatGPT · approved AI"),
    ]
    for index, item in enumerate(values):
        stats.addWidget(_detail_item(*item), index // 3, index % 3)
    box.addLayout(stats)

    privacy_note = QFrame()
    privacy_note.setStyleSheet("QFrame{background:#F0F7FF;border:1px solid #CFE0FF;border-radius:10px;}")
    note_row = QHBoxLayout(privacy_note)
    note_row.setContentsMargins(10, 8, 10, 8)
    shield = QLabel()
    shield.setPixmap(icon("protect", color=BLUE, size=16).pixmap(16, 16))
    shield.setStyleSheet("border:none;background:transparent;")
    note_row.addWidget(shield)
    text = QLabel("Approval is based on the protected copy and metadata. The original sensitive document is not exposed in the approval queue.")
    text.setWordWrap(True)
    text.setStyleSheet("color:#344054;font-size:7.5px;font-weight:750;border:none;background:transparent;")
    note_row.addWidget(text, 1)
    box.addWidget(privacy_note)

    actions = QHBoxLayout()
    actions.addWidget(
        _small_button(
            "Preview protected copy",
            lambda: _show_preview_action(
                page,
                "Protected copy preview",
                "Production behavior: open the protected artifact only. The original stays local and restore mappings remain outside the approval surface.",
            ),
        )
    )
    actions.addStretch(1)
    actions.addWidget(
        _small_button(
            "Reject",
            lambda: _show_preview_action(
                page,
                "Approval rejected",
                "The production runtime will stop the external handoff and store only the approval decision metadata.",
            ),
            danger=True,
        )
    )
    actions.addWidget(
        _small_button(
            "Approve",
            lambda: _show_preview_action(
                page,
                "Approval accepted",
                "The production runtime will continue only with the protected artifact and the policy-approved destination.",
            ),
            primary=True,
        )
    )
    box.addLayout(actions)
    body.addWidget(queue)

    body.addWidget(_section_title("Organization approval rules", "Keep the decision model simple enough to understand at a glance and enforce centrally from Policy Center."))
    rules = [
        _approval_rule("Low", "No residual findings and approved destination", "Auto approve when organization policy allows", tone="green"),
        _approval_rule("Medium", "Protected output is clean but the workflow or destination requires review", "Require human approval", tone="amber"),
        _approval_rule("High", "Residual risk, disallowed destination or policy conflict", "Block before external handoff", tone="red"),
    ]
    body.addWidget(_ResponsiveGrid(rules, max_columns=3))
    return tab


def _tab_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setCheckable(True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(36)
    button.setStyleSheet(
        "QPushButton{background:transparent;color:#667085;border:none;border-bottom:2px solid transparent;"
        "padding:8px 12px;font-size:9px;font-weight:850;}"
        "QPushButton:hover{color:#344054;background:#F9FAFB;}"
        f"QPushButton:checked{{color:{BLUE};border-bottom:2px solid {BLUE};background:#F8FAFF;}}"
    )
    return button


def _build_tabs(page: QWidget) -> QWidget:
    wrapper = QWidget()
    wrapper.setStyleSheet("background:transparent;")
    root = QVBoxLayout(wrapper)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(12)

    nav = QFrame()
    nav.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:12px;}}")
    nav_row = QHBoxLayout(nav)
    nav_row.setContentsMargins(8, 0, 8, 0)
    nav_row.setSpacing(1)

    stack = QStackedWidget()
    stack.setStyleSheet("QStackedWidget{background:transparent;border:none;}")
    pages = [
        ("My automations", _my_automations_tab(page)),
        ("Templates", _templates_tab(page)),
        ("Runs", _runs_tab(page)),
        ("Approvals", _approvals_tab(page)),
    ]
    group = QButtonGroup(wrapper)
    group.setExclusive(True)
    buttons: list[QPushButton] = []
    for index, (label, content) in enumerate(pages):
        button = _tab_button(label)
        group.addButton(button, index)
        nav_row.addWidget(button)
        buttons.append(button)
        stack.addWidget(content)
    nav_row.addStretch(1)
    buttons[0].setChecked(True)
    stack.setCurrentIndex(0)
    group.idClicked.connect(stack.setCurrentIndex)

    root.addWidget(nav)
    root.addWidget(stack)
    wrapper._automation_tab_group = group
    wrapper._automation_stack = stack
    return wrapper


def _product_hero(page: QWidget) -> QFrame:
    hero = QFrame()
    hero.setStyleSheet("QFrame{background:#FFFFFF;border:1px solid #D9E4FF;border-radius:15px;}")
    row = QHBoxLayout(hero)
    row.setContentsMargins(17, 15, 17, 15)
    row.setSpacing(13)

    bubble = QLabel()
    bubble.setFixedSize(46, 46)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon("workflow", color=BLUE, size=23).pixmap(23, 23))
    bubble.setStyleSheet(f"background:{BLUE_SOFT};border:none;border-radius:13px;")
    row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(3)
    eyebrow_row = QHBoxLayout()
    eyebrow = QLabel("PROTECTED AUTOMATION CONTROL PLANE")
    eyebrow.setStyleSheet(f"color:{BLUE};font-size:7px;font-weight:950;border:none;background:transparent;")
    eyebrow_row.addWidget(eyebrow)
    eyebrow_row.addWidget(_preview_badge("PRODUCT PREVIEW"))
    eyebrow_row.addStretch(1)
    title = QLabel("Automate the work. Keep PrivacyGate in control.")
    title.setStyleSheet(f"color:{INK};font-size:14px;font-weight:950;border:none;background:transparent;")
    note = QLabel("Build repeatable AI and business workflows where local protection, residual checks, policy and human approval happen before external handoff.")
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:8.5px;border:none;background:transparent;")
    copy.addLayout(eyebrow_row)
    copy.addWidget(title)
    copy.addWidget(note)
    row.addLayout(copy, 1)

    actions = QVBoxLayout()
    actions.setSpacing(7)
    actions.addWidget(_action_button("+ New automation", lambda: _show_builder(page), primary=True))
    actions.addWidget(_small_button("AI workflow advisory", lambda: _safe_contact(page)))
    row.addLayout(actions)
    return hero


def _rebuild_automation_product(page: QWidget) -> None:
    body = _page_shell(
        page,
        "Automation Studio",
        "Build, run and govern privacy-safe automations — then turn proven workflows into repeatable AI solutions for real teams and clients.",
    )

    body.addWidget(_product_hero(page))
    body.addWidget(
        _metric_strip(
            [
                _metric_card("workflow", "3", "Active automations", "Protected workflows currently enabled", tone="blue"),
                _metric_card("history", "18", "Runs today", "Success, review and blocked outcomes", tone="green"),
                _metric_card("check", "1", "Waiting approval", "Human review required before handoff", tone="amber"),
                _metric_card("protect", "0", "Blocked by policy", "No unresolved policy conflicts", tone="green"),
            ]
        )
    )
    body.addWidget(_build_tabs(page))
    body.addStretch(1)


def apply_mockup_automation_product_studio_2026(main_window) -> None:
    if bool(getattr(main_window, "_privacygate_mockup_automation_product_studio_2026", False)):
        return
    main_window._privacygate_mockup_automation_product_studio_2026 = True

    page = getattr(main_window, "local_automation_page", None)
    if page is not None:
        _rebuild_automation_product(page)
