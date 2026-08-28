from __future__ import annotations

"""Privacy-first AI Workflows surface.

This late presentation layer deliberately keeps Protect as the product core.
It does not pretend that PrivacyGate is a general-purpose automation engine.
Existing Protect, Library and MCP/AI Direct controllers remain authoritative;
this page explains and launches privacy-safe AI workflows around them.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_mcp_automation_studio_2026 import (
    BLUE,
    BLUE_DARK,
    BLUE_SOFT,
    BORDER,
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
GREEN_SOFT = "#ECFDF3"
AMBER_SOFT = "#FFF7E8"
SLATE = "#344054"


def _small_button(text: str, callback, *, primary: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(32)
    if primary:
        button.setStyleSheet(
            f"QPushButton{{background:{BLUE};color:#FFFFFF;border:1px solid {BLUE};border-radius:8px;"
            "padding:6px 10px;font-size:8px;font-weight:850;}"
            f"QPushButton:hover{{background:{BLUE_DARK};border-color:{BLUE_DARK};}}"
        )
    else:
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:8px;"
            "padding:6px 10px;font-size:8px;font-weight:800;}"
            "QPushButton:hover{background:#F9FAFB;border-color:#98A2B3;}"
        )
    button.clicked.connect(lambda _checked=False: callback())
    return button


def _status_chip(text: str, *, tone: str = "blue") -> QLabel:
    palette = {
        "blue": (BLUE, BLUE_SOFT, "#CFE0FF"),
        "green": (GREEN, GREEN_SOFT, "#ABEFC6"),
        "amber": (AMBER, AMBER_SOFT, "#FEDF89"),
        "gray": ("#475467", "#F2F4F7", "#E4E7EC"),
    }
    fg, bg, border = palette.get(tone, palette["gray"])
    chip = QLabel(text.upper())
    chip.setStyleSheet(
        f"background:{bg};color:{fg};border:1px solid {border};border-radius:8px;"
        "padding:4px 7px;font-size:7px;font-weight:950;"
    )
    return chip


def _open_existing_page(page: QWidget, attribute: str) -> None:
    main_window = page.window()
    pages = getattr(main_window, "pages", None)
    target = getattr(main_window, attribute, None)
    if pages is not None and target is not None:
        pages.setCurrentWidget(target)
        controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
        if controller is not None and callable(getattr(controller, "_sync_checked_state", None)):
            controller._sync_checked_state()


def _flow_step(
    number: str,
    title: str,
    note: str,
    icon_name: str,
    *,
    tone: str = "gray",
    status: str = "",
) -> QFrame:
    tones = {
        "blue": (BLUE, BLUE_SOFT, "#CFE0FF"),
        "green": (GREEN, GREEN_SOFT, "#ABEFC6"),
        "amber": (AMBER, AMBER_SOFT, "#FEDF89"),
        "gray": (SLATE, "#F8FAFC", "#E4E7EC"),
    }
    accent, soft, border = tones.get(tone, tones["gray"])
    card = QFrame()
    card.setMinimumHeight(118)
    card.setStyleSheet(
        f"QFrame{{background:{SURFACE};border:1px solid {border};border-radius:13px;}}"
    )
    box = QVBoxLayout(card)
    box.setContentsMargins(13, 12, 13, 12)
    box.setSpacing(6)

    top = QHBoxLayout()
    bubble = QLabel()
    bubble.setFixedSize(34, 34)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon(icon_name, color=accent, size=17).pixmap(17, 17))
    bubble.setStyleSheet(f"background:{soft};border:none;border-radius:9px;")
    top.addWidget(bubble)
    top.addStretch(1)
    if status:
        top.addWidget(_status_chip(status, tone=tone))
    box.addLayout(top)

    eyebrow = QLabel(number)
    eyebrow.setStyleSheet(
        f"color:{accent};font-size:6.5px;font-weight:950;border:none;background:transparent;"
    )
    heading = QLabel(title)
    heading.setStyleSheet(
        f"color:{INK};font-size:10px;font-weight:950;border:none;background:transparent;"
    )
    detail = QLabel(note)
    detail.setWordWrap(True)
    detail.setStyleSheet(
        f"color:{MUTED};font-size:7.5px;border:none;background:transparent;"
    )
    box.addWidget(eyebrow)
    box.addWidget(heading)
    box.addWidget(detail)
    return card


def _privacy_flow() -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame{background:#FFFFFF;border:1px solid #D9E4FF;border-radius:15px;}"
    )
    box = QVBoxLayout(frame)
    box.setContentsMargins(15, 14, 15, 14)
    box.setSpacing(11)

    top = QHBoxLayout()
    copy = QVBoxLayout()
    copy.setSpacing(2)
    eyebrow = QLabel("THE PRIVACYGATE WORKFLOW")
    eyebrow.setStyleSheet(
        f"color:{BLUE};font-size:7px;font-weight:950;border:none;background:transparent;"
    )
    title = QLabel("Protect is the core. Workflows begin when protected data is ready for AI.")
    title.setStyleSheet(
        f"color:{INK};font-size:12px;font-weight:950;border:none;background:transparent;"
    )
    note = QLabel(
        "PrivacyGate does not need to replace your CRM, project tool or automation platform. "
        "It creates the safe boundary before AI, then controls what can happen next."
    )
    note.setWordWrap(True)
    note.setStyleSheet(
        f"color:{MUTED};font-size:8px;border:none;background:transparent;"
    )
    copy.addWidget(eyebrow)
    copy.addWidget(title)
    copy.addWidget(note)
    top.addLayout(copy, 1)
    top.addWidget(_status_chip("Privacy-first", tone="blue"), 0, Qt.AlignmentFlag.AlignTop)
    box.addLayout(top)

    grid = QGridLayout()
    grid.setHorizontalSpacing(9)
    grid.setVerticalSpacing(9)
    steps = (
        _flow_step(
            "01 · CORE",
            "Protect",
            "Choose a real document in Protect, scan locally, protect sensitive values and run Privacy Check.",
            "protect",
            tone="blue",
            status="Available now",
        ),
        _flow_step(
            "02 · SAFE AI",
            "Use with approved AI",
            "Library + MCP / AI Direct lets the AI work from the protected copy instead of the original data.",
            "workflow",
            tone="green",
            status="Available now",
        ),
        _flow_step(
            "03 · CONTROL",
            "Check AI output",
            "Inspect the AI response before it is reused externally; detect accidental sensitive output or policy conflicts.",
            "check",
            tone="amber",
            status="Next layer",
        ),
        _flow_step(
            "04 · OPTIONAL ACTION",
            "Turn insight into action",
            "Only when useful: save a report, create project actions, draft an email or send approved output to another tool.",
            "external",
            tone="gray",
            status="Optional",
        ),
    )
    for index, step in enumerate(steps):
        grid.addWidget(step, 0, index)
        grid.setColumnStretch(index, 1)
    box.addLayout(grid)

    boundary = QLabel(
        "ORIGINAL DATA  →  PRIVACYGATE LOCAL PROTECTION  →  PROTECTED DATA ONLY  →  AI  →  OUTPUT CHECK  →  APPROVED ACTION"
    )
    boundary.setAlignment(Qt.AlignmentFlag.AlignCenter)
    boundary.setWordWrap(True)
    boundary.setStyleSheet(
        "background:#101828;color:#FFFFFF;border:1px solid #101828;border-radius:10px;"
        "padding:9px 12px;font-size:7.5px;font-weight:900;"
    )
    box.addWidget(boundary)
    return frame


def _workflow_card(
    page: QWidget,
    *,
    icon_name: str,
    title: str,
    description: str,
    badge: str,
    ai_value: str,
    optional_action: str,
    audience: str,
    workflow: str,
    outcome: str,
) -> QFrame:
    card = QFrame()
    card.setMinimumHeight(250)
    card.setStyleSheet(
        f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:14px;}}"
    )
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

    value = QLabel(f"AI VALUE  ·  {ai_value}")
    value.setWordWrap(True)
    value.setStyleSheet(
        "background:#F0F7FF;color:#344054;border:1px solid #D9E4FF;border-radius:8px;"
        "padding:6px 8px;font-size:7px;font-weight:850;"
    )
    action = QLabel(f"OPTIONAL NEXT STEP  ·  {optional_action}")
    action.setWordWrap(True)
    action.setStyleSheet(
        "background:#F8FAFC;color:#475467;border:1px solid #EAECF0;border-radius:8px;"
        "padding:6px 8px;font-size:7px;font-weight:800;"
    )
    box.addWidget(value)
    box.addWidget(action)
    box.addStretch(1)

    actions = QHBoxLayout()
    actions.setSpacing(7)
    actions.addWidget(
        _small_button(
            "Preview workflow",
            lambda: _show_use_case(page, title, audience, workflow, outcome),
        )
    )
    actions.addWidget(
        _small_button(
            "Start in Protect",
            lambda: _open_existing_page(page, "protection_page"),
            primary=True,
        )
    )
    box.addLayout(actions)
    return card


def _hero(page: QWidget) -> QFrame:
    hero = QFrame()
    hero.setStyleSheet(
        "QFrame{background:#FFFFFF;border:1px solid #D9E4FF;border-radius:15px;}"
    )
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
    eyebrow = QLabel("PRIVACY-FIRST AI WORKFLOWS")
    eyebrow.setStyleSheet(
        f"color:{BLUE};font-size:7px;font-weight:950;border:none;background:transparent;"
    )
    title = QLabel("Protect first. Use AI safely. Control what comes back.")
    title.setStyleSheet(
        f"color:{INK};font-size:14px;font-weight:950;border:none;background:transparent;"
    )
    note = QLabel(
        "Turn protected documents into useful AI analysis without turning PrivacyGate into another Zapier or n8n. "
        "Protect remains the core; reports, tasks and other actions are optional outcomes of approved AI work."
    )
    note.setWordWrap(True)
    note.setStyleSheet(
        f"color:{MUTED};font-size:8.5px;border:none;background:transparent;"
    )
    copy.addWidget(eyebrow)
    copy.addWidget(title)
    copy.addWidget(note)
    row.addLayout(copy, 1)

    actions = QVBoxLayout()
    actions.setSpacing(7)
    actions.addWidget(
        _action_button(
            "Start in Protect",
            lambda: _open_existing_page(page, "protection_page"),
            primary=True,
        )
    )
    actions.addWidget(
        _small_button(
            "MCP & AI Direct",
            lambda: _open_existing_page(page, "cloud_automation_page"),
        )
    )
    row.addLayout(actions)
    return hero


def _output_control_card() -> QFrame:
    card = QFrame()
    card.setStyleSheet(
        "QFrame{background:#101828;border:1px solid #101828;border-radius:15px;}"
    )
    row = QHBoxLayout(card)
    row.setContentsMargins(17, 15, 17, 15)
    row.setSpacing(13)

    bubble = QLabel()
    bubble.setFixedSize(42, 42)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon("protect", color="#FFFFFF", size=21).pixmap(21, 21))
    bubble.setStyleSheet("background:#344054;border:none;border-radius:12px;")
    row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(3)
    eyebrow = QLabel("NEXT PRODUCT LAYER · OUTPUT PRIVACY")
    eyebrow.setStyleSheet(
        "color:#84CAFF;font-size:7px;font-weight:950;border:none;background:transparent;"
    )
    title = QLabel("Protect what goes into AI. Control what comes out.")
    title.setStyleSheet(
        "color:#FFFFFF;font-size:12px;font-weight:950;border:none;background:transparent;"
    )
    note = QLabel(
        "After AI analysis, PrivacyGate can re-check the response before it is saved, restored locally, turned into tasks, "
        "or sent to another approved destination. This is the natural extension of the current privacy boundary."
    )
    note.setWordWrap(True)
    note.setStyleSheet(
        "color:#D0D5DD;font-size:8px;border:none;background:transparent;"
    )
    copy.addWidget(eyebrow)
    copy.addWidget(title)
    copy.addWidget(note)
    row.addLayout(copy, 1)
    return card


def _advisory_banner(page: QWidget) -> QFrame:
    banner = QFrame()
    banner.setStyleSheet(
        "QFrame{background:#F0F7FF;border:1px solid #CFE0FF;border-radius:14px;}"
    )
    row = QHBoxLayout(banner)
    row.setContentsMargins(15, 13, 15, 13)
    row.setSpacing(11)

    glyph = QLabel()
    glyph.setFixedSize(36, 36)
    glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
    glyph.setPixmap(icon("workflow", color=BLUE, size=18).pixmap(18, 18))
    glyph.setStyleSheet(f"background:{BLUE_SOFT};border:none;border-radius:10px;")
    row.addWidget(glyph)

    copy = QVBoxLayout()
    copy.setSpacing(2)
    eyebrow = QLabel("AI WORKFLOW ADVISORY · PM-LED DELIVERY")
    eyebrow.setStyleSheet(
        f"color:{BLUE};font-size:7px;font-weight:950;border:none;background:transparent;"
    )
    title = QLabel("Need a controlled AI workflow around your real process?")
    title.setStyleSheet(
        f"color:{INK};font-size:10px;font-weight:950;border:none;background:transparent;"
    )
    note = QLabel(
        "Map the process, define the PrivacyGate boundary, choose the approved AI, design human review, then connect only the downstream actions that create real business value."
    )
    note.setWordWrap(True)
    note.setStyleSheet(
        f"color:{MUTED};font-size:7.5px;border:none;background:transparent;"
    )
    copy.addWidget(eyebrow)
    copy.addWidget(title)
    copy.addWidget(note)
    row.addLayout(copy, 1)
    row.addWidget(
        _small_button("Discuss a workflow", lambda: _safe_contact(page), primary=True)
    )
    return banner


def _rebuild_workflows(page: QWidget) -> None:
    body = _page_shell(
        page,
        "AI Workflows",
        "Use PrivacyGate as the privacy boundary for AI work: protect real data first, analyze only the protected copy, then control the output before any optional business action.",
    )

    body.addWidget(_hero(page))
    body.addWidget(_privacy_flow())
    body.addWidget(
        _section_title(
            "Privacy-first workflow ideas",
            "These workflows start with a real privacy problem and use AI only after Protect has created a safe working copy.",
        )
    )

    workflows = [
        dict(
            icon_name="document",
            title="Analyze a contractor estimate",
            description="Protect identities, account details and confidential project data before asking AI to review a real estimate.",
            badge="Construction",
            ai_value="Cost analysis · scope gaps · risk flags · contractor questions",
            optional_action="Save a reviewed report or turn approved action items into project tasks",
            audience="Project managers, owners, contractors and real-estate teams reviewing bids or estimates.",
            workflow="Estimate → PrivacyGate Protect → approved AI analysis → output check → reviewed report / optional project actions.",
            outcome="Useful cost and risk analysis without exposing the original sensitive estimate to the AI provider.",
        ),
        dict(
            icon_name="protect",
            title="Review a lease or contract with AI",
            description="De-identify personal and business-sensitive terms first, then use AI to find obligations, gaps and review questions.",
            badge="Legal / Property",
            ai_value="Clause review · obligations · missing information · questions",
            optional_action="Save a protected review memo or prepare approved follow-up questions",
            audience="Property managers, brokers, project teams and small businesses reviewing sensitive agreements.",
            workflow="Lease / contract → PrivacyGate Protect → approved AI review → output check → review memo / questions.",
            outcome="AI-assisted document review while keeping names, contacts, identifiers and other protected values outside the AI prompt.",
        ),
        dict(
            icon_name="workflow",
            title="Compare protected proposals",
            description="Protect two or more proposals, then let AI compare scope, exclusions, costs and differences using only safe copies.",
            badge="PM",
            ai_value="Side-by-side comparison · exclusions · cost differences · decision support",
            optional_action="Export a comparison report or create approved follow-up actions",
            audience="Project managers, procurement teams and property owners comparing vendor proposals.",
            workflow="Proposal A + B → PrivacyGate Protect → approved AI comparison → output check → decision report.",
            outcome="Faster comparison without sending the original vendor or client-sensitive documents to AI.",
        ),
        dict(
            icon_name="check",
            title="Extract project risks & action items",
            description="Use a protected report, meeting note or project document to identify risks and actions after the privacy step is complete.",
            badge="Projects",
            ai_value="Risk extraction · action items · owners · due-date suggestions",
            optional_action="Create ClickUp / Asana tasks only from the reviewed AI output",
            audience="Project managers and operations teams that already work from recurring reports or meeting notes.",
            workflow="Protected project document → approved AI extraction → output check → human review → optional task creation.",
            outcome="Actionable project follow-up from protected data; task creation is an outcome, not the privacy workflow itself.",
        ),
        dict(
            icon_name="library",
            title="Summarize an owner or property report",
            description="Protect tenant, owner, vendor and financial details before AI creates a concise management-level summary.",
            badge="Reporting",
            ai_value="Executive summary · issues · trends · decisions needed",
            optional_action="Save PDF/TXT or prepare an approved client email",
            audience="Property managers, consultants and project teams producing recurring stakeholder reports.",
            workflow="Report → PrivacyGate Protect → approved AI summary → output check → human review → export / delivery.",
            outcome="Faster reporting while sensitive source details remain protected before AI use.",
        ),
        dict(
            icon_name="document",
            title="Review sensitive financial documents",
            description="Protect account identifiers and confidential values, then use AI to analyze invoices, statements or cost reports safely.",
            badge="Finance",
            ai_value="Variance review · unusual costs · missing items · management questions",
            optional_action="Save analysis to Library or include approved findings in a report",
            audience="Small businesses, property teams and project managers reviewing invoices, statements or cost reports.",
            workflow="Financial document → PrivacyGate Protect → approved AI analysis → output check → reviewed findings / report.",
            outcome="AI-assisted financial review without unnecessarily exposing the source document's sensitive identifiers.",
        ),
    ]
    cards = [_workflow_card(page, **spec) for spec in workflows]
    body.addWidget(_ResponsiveGrid(cards, max_columns=3))
    body.addWidget(_output_control_card())
    body.addWidget(_advisory_banner(page))
    body.addStretch(1)


def _rename_navigation(main_window) -> None:
    controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    if controller is None:
        return
    for button in tuple(getattr(controller, "_buttons", ()) or ()):
        if str(button.text()).strip() == "Automation":
            button.setText("Workflows")
            button.setToolTip("AI Workflows")


def apply_mockup_ai_workflows_2026(main_window) -> None:
    """Replace the automation-preview framing with privacy-first AI Workflows."""
    if bool(getattr(main_window, "_privacygate_mockup_ai_workflows_2026", False)):
        return
    main_window._privacygate_mockup_ai_workflows_2026 = True

    page = getattr(main_window, "local_automation_page", None)
    if page is not None:
        _rebuild_workflows(page)
    _rename_navigation(main_window)
