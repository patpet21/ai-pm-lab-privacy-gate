from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_redesign_shell_2026 import _clear_layout


BLUE = "#2563EB"
BLUE_DARK = "#1D4ED8"
BLUE_SOFT = "#EEF4FF"
INK = "#101828"
MUTED = "#667085"
BORDER = "#E4E7EC"
SURFACE = "#FFFFFF"
CANVAS = "#F8FAFC"
TEAL = "#0B7F89"
GREEN = "#16A34A"


class _ResponsiveGrid(QWidget):
    def __init__(self, cards: list[QWidget], *, max_columns: int = 3, parent=None) -> None:
        super().__init__(parent)
        self.cards = cards
        self.max_columns = max(1, max_columns)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self._columns = 0
        self._reflow(force=True)

    def _column_count(self) -> int:
        width = max(0, self.width())
        if self.max_columns >= 3 and width >= 1120:
            return 3
        if width >= 690:
            return min(2, self.max_columns)
        return 1

    def _reflow(self, *, force: bool = False) -> None:
        columns = self._column_count()
        if columns == self._columns and not force:
            return
        self._columns = columns
        for card in self.cards:
            self.grid.removeWidget(card)
        for index, card in enumerate(self.cards):
            self.grid.addWidget(card, index // columns, index % columns)
        for column in range(self.max_columns):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._reflow()


def _page_shell(page: QWidget, title: str, subtitle: str) -> QVBoxLayout:
    root = page.layout()
    if root is None:
        root = QVBoxLayout(page)
    else:
        _clear_layout(root)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    page.setStyleSheet(f"background:{CANVAS};")

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

    host = QWidget()
    host.setStyleSheet("background:transparent;")
    body = QVBoxLayout(host)
    body.setContentsMargins(24, 22, 24, 24)
    body.setSpacing(16)

    heading = QLabel(title)
    heading.setStyleSheet(f"color:{INK};font-size:27px;font-weight:950;border:none;background:transparent;")
    note = QLabel(subtitle)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;background:transparent;")
    body.addWidget(heading)
    body.addWidget(note)

    scroll.setWidget(host)
    root.addWidget(scroll)
    page._mockup_scroll_host = host
    page._mockup_scroll = scroll
    return body


def _section_title(title: str, subtitle: str = "") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 2, 0, 0)
    layout.setSpacing(2)
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{INK};font-size:15px;font-weight:900;border:none;background:transparent;")
    layout.addWidget(heading)
    if subtitle:
        note = QLabel(subtitle)
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;background:transparent;")
        layout.addWidget(note)
    return widget


def _action_button(text: str, callback, *, primary: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(36)
    if primary:
        button.setStyleSheet(
            f"QPushButton{{background:{BLUE};color:#FFFFFF;border:1px solid {BLUE};border-radius:9px;"
            "padding:8px 12px;font-size:9px;font-weight:850;}"
            f"QPushButton:hover{{background:{BLUE_DARK};border-color:{BLUE_DARK};}}"
        )
    else:
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:9px;"
            "padding:8px 12px;font-size:9px;font-weight:800;}"
            "QPushButton:hover{background:#F9FAFB;border-color:#98A2B3;}"
        )
    button.clicked.connect(lambda _checked=False: callback())
    return button


def _feature_card(
    icon_name: str,
    title: str,
    description: str,
    badge: str,
    action_text: str,
    callback,
    *,
    primary: bool = False,
) -> QFrame:
    card = QFrame()
    card.setMinimumHeight(184)
    card.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:14px;}}")
    box = QVBoxLayout(card)
    box.setContentsMargins(16, 15, 16, 15)
    box.setSpacing(9)

    top = QHBoxLayout()
    bubble = QLabel()
    bubble.setFixedSize(40, 40)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon(icon_name, color=BLUE, size=21).pixmap(21, 21))
    bubble.setStyleSheet(f"background:{BLUE_SOFT};border:none;border-radius:12px;")
    top.addWidget(bubble)
    top.addStretch(1)
    chip = QLabel(badge.upper())
    chip.setStyleSheet(
        "background:#F2F4F7;color:#475467;border:none;border-radius:8px;"
        "padding:5px 8px;font-size:7px;font-weight:900;"
    )
    top.addWidget(chip, 0, Qt.AlignmentFlag.AlignTop)
    box.addLayout(top)

    heading = QLabel(title)
    heading.setWordWrap(True)
    heading.setStyleSheet(f"color:{INK};font-size:12px;font-weight:900;border:none;background:transparent;")
    copy = QLabel(description)
    copy.setWordWrap(True)
    copy.setStyleSheet(f"color:{MUTED};font-size:8.5px;border:none;background:transparent;")
    box.addWidget(heading)
    box.addWidget(copy)
    box.addStretch(1)
    box.addWidget(_action_button(action_text, callback, primary=primary))
    return card


def _show_use_case(parent: QWidget, title: str, audience: str, workflow: str, outcome: str) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(title)
    box.setInformativeText(
        f"Best fit\n{audience}\n\nWorkflow\n{workflow}\n\nClient outcome\n{outcome}\n\n"
        "Use this as a discovery-call starting point. Confirm the client's systems, permissions, review steps and privacy requirements before proposing automation."
    )
    box.exec()


def _safe_contact(page: QWidget) -> None:
    callback = getattr(page, "_contact", None)
    if callable(callback):
        callback()


def _rebuild_mcp(page: QWidget) -> None:
    body = _page_shell(
        page,
        "MCP Connections",
        "Connect approved AI clients to protected PrivacyGate data through controlled MCP access. AI providers themselves are managed in Apps; this page is only for MCP connectivity, permissions and client-ready MCP solutions.",
    )

    body.addWidget(_section_title("Connect this PrivacyGate", "Use the existing local or remote MCP setup. Protected Library access remains the source boundary."))

    local_callback = getattr(page, "_mcp_setup", lambda: None)
    remote_callback = getattr(page, "_remote_mcp_setup", lambda: None)
    protected_count = 0
    library = getattr(page, "library", None)
    if library is not None:
        try:
            protected_count = len(library.list_mcp_documents(limit=200))
        except Exception:
            protected_count = 0

    connection_cards = [
        _feature_card(
            "cloud",
            "Remote MCP",
            f"Stable authenticated MCP access for compatible cloud AI clients. Protected documents currently available to MCP: {protected_count}.",
            "Remote",
            "Configure remote MCP",
            remote_callback,
            primary=True,
        ),
        _feature_card(
            "workflow",
            "Local MCP",
            "Direct desktop MCP setup for compatible local clients using the existing stdio configuration. No public tunnel is required.",
            "Local",
            "Open local MCP setup",
            local_callback,
        ),
    ]
    body.addWidget(_ResponsiveGrid(connection_cards, max_columns=2))

    boundary = QFrame()
    boundary.setStyleSheet("QFrame{background:#F0F7FF;border:1px solid #CFE0FF;border-radius:13px;}")
    row = QHBoxLayout(boundary)
    row.setContentsMargins(15, 13, 15, 13)
    shield = QLabel()
    shield.setPixmap(icon("protect", color=BLUE, size=20).pixmap(20, 20))
    row.addWidget(shield, 0, Qt.AlignmentFlag.AlignTop)
    text = QLabel(
        "MCP boundary: only protected Library items explicitly made available to AI are exposed. Originals and restore mappings remain outside the MCP surface."
    )
    text.setWordWrap(True)
    text.setStyleSheet(f"color:#344054;font-size:9px;font-weight:750;border:none;background:transparent;")
    row.addWidget(text, 1)
    body.addWidget(boundary)

    body.addWidget(_section_title("Client-ready MCP solutions", "Use these as concrete consulting use cases when speaking with a prospective client."))
    use_cases = [
        (
            "protect",
            "Private AI knowledge access",
            "Give an approved AI client controlled read-only access to protected company documents instead of copying originals into chat.",
            "Knowledge",
            "View client pitch",
            lambda: _show_use_case(
                page,
                "Private AI knowledge access",
                "Small professional teams, property managers, consultancies and document-heavy operations.",
                "Local documents → PrivacyGate protection → approved protected Library → MCP → approved AI client.",
                "Employees can use AI against useful business context while reducing unnecessary exposure of original sensitive documents.",
            ),
        ),
        (
            "document",
            "Property operations assistant",
            "Create an AI-accessible protected knowledge set for leases, procedures, vendor documents and operating references.",
            "Real estate",
            "View client pitch",
            lambda: _show_use_case(
                page,
                "Property operations assistant",
                "Property management and real-estate operations teams.",
                "Approved operating documents → protect tenant/client identifiers → MCP-accessible protected knowledge → AI Q&A.",
                "Faster answers to operational questions without making the original local document library directly available to the AI client.",
            ),
        ),
        (
            "workflow",
            "Project document assistant",
            "Provide controlled AI access to protected project references, reports and procedures for construction or project teams.",
            "Projects",
            "View client pitch",
            lambda: _show_use_case(
                page,
                "Project document assistant",
                "Construction, engineering, renovation and project-management teams.",
                "Project reference files → PrivacyGate → protected Library → MCP → approved AI assistant.",
                "Team members can query project knowledge while preserving a defined privacy boundary around source documents.",
            ),
        ),
    ]
    cards = [_feature_card(*spec) for spec in use_cases]
    body.addWidget(_ResponsiveGrid(cards, max_columns=3))

    footer = QFrame()
    footer.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:13px;}}")
    footer_row = QHBoxLayout(footer)
    footer_row.setContentsMargins(15, 13, 15, 13)
    copy = QVBoxLayout()
    title = QLabel("Need a custom MCP architecture?")
    title.setStyleSheet(f"color:{INK};font-size:11px;font-weight:900;border:none;")
    note = QLabel("Map the client's AI client, document boundary, authentication, permissions and human-review workflow before implementation.")
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:8.5px;border:none;")
    copy.addWidget(title)
    copy.addWidget(note)
    footer_row.addLayout(copy, 1)
    footer_row.addWidget(_action_button("Discuss MCP workflow", lambda: _safe_contact(page)))
    body.addWidget(footer)
    body.addStretch(1)


def _rebuild_automation(page: QWidget) -> None:
    body = _page_shell(
        page,
        "Automation Studio",
        "Turn repeatable business work into protected, reviewable automation. Use these workflows as demos, discovery-call examples and starting points for client projects.",
    )

    hero = QFrame()
    hero.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:14px;}}")
    hero_row = QHBoxLayout(hero)
    hero_row.setContentsMargins(17, 15, 17, 15)
    bubble = QLabel()
    bubble.setFixedSize(44, 44)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon("workflow", color=BLUE, size=23).pixmap(23, 23))
    bubble.setStyleSheet(f"background:{BLUE_SOFT};border:none;border-radius:13px;")
    hero_row.addWidget(bubble)
    copy = QVBoxLayout()
    title = QLabel("Build automation around a real client problem")
    title.setStyleSheet(f"color:{INK};font-size:14px;font-weight:900;border:none;")
    note = QLabel("Start with the repetitive task, define the privacy boundary and approval points, then connect only the systems the client actually uses.")
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
    copy.addWidget(title)
    copy.addWidget(note)
    hero_row.addLayout(copy, 1)
    hero_row.addWidget(_action_button("Discuss a workflow", lambda: _safe_contact(page), primary=True))
    body.addWidget(hero)

    body.addWidget(_section_title("Automation examples", "Concrete workflows you can demonstrate or adapt during a client discovery call."))
    specs = [
        (
            "contact",
            "Social content automation",
            "Approved idea → draft caption/assets → human approval → schedule Instagram and LinkedIn publishing through the client's connected tools.",
            "Marketing",
            "Open client use case",
            lambda: _show_use_case(
                page,
                "Social content automation",
                "Small businesses, real-estate teams, consultants and local brands that post repeatedly but lack a consistent content process.",
                "Content brief → AI-assisted draft → brand/privacy review → human approval → scheduler → Instagram / LinkedIn.",
                "A repeatable content engine with approval before publishing and less manual copying between tools.",
            ),
        ),
        (
            "workflow",
            "Lead intake & follow-up",
            "New form or email inquiry → classify → create CRM/task record → assign owner → prepare approved follow-up.",
            "Sales",
            "Open client use case",
            lambda: _show_use_case(
                page,
                "Lead intake & follow-up",
                "Service businesses, brokers, contractors and small sales teams.",
                "Form/email → validate and classify → CRM/ClickUp/Asana → owner assignment → human-approved follow-up.",
                "Faster lead response and fewer inquiries lost between inboxes and task systems.",
            ),
        ),
        (
            "document",
            "Email & document intake",
            "Inbound email or file → PrivacyGate protection → classify → save to approved location → create the right task or notification.",
            "Operations",
            "Open client use case",
            lambda: _show_use_case(
                page,
                "Email & document intake",
                "Property managers, project teams and professional-services firms receiving documents by email.",
                "Inbox/file → local privacy protection → classification → approved storage → task / notification.",
                "A cleaner intake queue with sensitive data handled before downstream AI or automation steps.",
            ),
        ),
        (
            "protect",
            "Property maintenance intake",
            "Tenant/request email → protect personal data → categorize issue → create maintenance task → notify the assigned person.",
            "Property",
            "Open client use case",
            lambda: _show_use_case(
                page,
                "Property maintenance intake",
                "Property managers and small building operations teams.",
                "Maintenance request → protect tenant data → classify urgency/category → task system → assignment and status notification.",
                "Less manual triage and a consistent handoff from incoming request to accountable task owner.",
            ),
        ),
        (
            "contact",
            "Meeting to tasks",
            "Approved meeting notes → protect sensitive details → extract actions → create ClickUp/Asana tasks → send a reviewable summary.",
            "PM",
            "Open client use case",
            lambda: _show_use_case(
                page,
                "Meeting to tasks",
                "Project managers, agencies and operations teams with recurring meetings.",
                "Meeting notes → privacy review → action extraction → task creation → owner/deadline review → summary.",
                "Fewer missed actions and less manual transcription from meeting notes into project tools.",
            ),
        ),
        (
            "library",
            "Owner / client reporting",
            "Operational data → gather approved updates → draft weekly report → human review → deliver through the client's chosen channel.",
            "Reporting",
            "Open client use case",
            lambda: _show_use_case(
                page,
                "Owner / client reporting",
                "Property managers, consultants and project teams producing recurring status reports.",
                "Approved source updates → consolidate → protect sensitive details → AI-assisted summary → human approval → email/report delivery.",
                "Consistent recurring reporting with less manual compilation and a clear review point before delivery.",
            ),
        ),
    ]
    cards = [_feature_card(*spec) for spec in specs]
    body.addWidget(_ResponsiveGrid(cards, max_columns=3))

    body.addWidget(_section_title("Client opportunity starter", "Three simple offers that are easy to explain before proposing a larger automation program."))
    opportunities = [
        ("Social workflow setup", "For teams posting manually every week", "Content intake + approval + scheduling"),
        ("Lead response workflow", "For businesses losing time in inbox follow-up", "Intake + qualification + CRM/task + follow-up"),
        ("Operations intake workflow", "For property/project teams with repetitive requests", "Email/file intake + privacy + routing + task creation"),
    ]
    panel = QFrame()
    panel.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:14px;}}")
    panel_box = QVBoxLayout(panel)
    panel_box.setContentsMargins(16, 12, 16, 12)
    panel_box.setSpacing(0)
    for index, (name, audience, deliverable) in enumerate(opportunities):
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 10, 0, 10)
        left = QVBoxLayout()
        heading = QLabel(name)
        heading.setStyleSheet(f"color:{INK};font-size:10px;font-weight:900;border:none;")
        audience_label = QLabel(audience)
        audience_label.setWordWrap(True)
        audience_label.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
        left.addWidget(heading)
        left.addWidget(audience_label)
        row.addLayout(left, 2)
        result = QLabel(deliverable)
        result.setWordWrap(True)
        result.setStyleSheet(f"color:#344054;font-size:8.5px;font-weight:750;border:none;")
        row.addWidget(result, 2)
        panel_box.addWidget(row_widget)
        if index < len(opportunities) - 1:
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background:{BORDER};border:none;")
            panel_box.addWidget(line)
    body.addWidget(panel)
    body.addStretch(1)


def apply_mockup_mcp_automation_studio_2026(main_window) -> None:
    if bool(getattr(main_window, "_privacygate_mockup_mcp_automation_studio_2026", False)):
        return
    main_window._privacygate_mockup_mcp_automation_studio_2026 = True

    automation = getattr(main_window, "local_automation_page", None)
    if automation is not None:
        _rebuild_automation(automation)

    mcp = getattr(main_window, "cloud_automation_page", None)
    if mcp is not None:
        _rebuild_mcp(mcp)
