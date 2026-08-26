from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate import __version__
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.resources import resource_path

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
TEAL_BRIGHT = "#12A5A0"
MUTED = "#61798A"
WHITE = "#FFFFFF"
BORDER = "#DDE7EC"
SOFT = "#F4F7F9"
GREEN = "#23824B"
INDIGO = "#6757D8"


def _shadow(widget: QWidget, blur: int = 26, alpha: int = 26, y: int = 5) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(6, 43, 79, alpha))
    widget.setGraphicsEffect(effect)


def _clear_layout(layout, keep: set[QWidget]) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            if widget not in keep:
                widget.deleteLater()
        elif child is not None:
            _clear_layout(child, keep)


def _find_button(page: QWidget, *labels: str) -> QPushButton | None:
    wanted = {label.strip().lower() for label in labels}
    for button in page.findChildren(QPushButton):
        if button.text().strip().lower() in wanted:
            return button
    return None


def _pill(text: str, tone: str = "teal") -> QLabel:
    palettes = {
        "teal": ("#E8F7F7", TEAL, "#C7E8E8"),
        "green": ("#EAF8F1", GREEN, "#CBE8D7"),
        "indigo": ("#F1EFFF", INDIGO, "#DDD8FF"),
        "navy": ("#EEF3F7", NAVY, "#D8E2E9"),
    }
    bg, fg, border = palettes[tone]
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"background:{bg};color:{fg};border:1px solid {border};border-radius:10px;"
        "padding:6px 10px;font-size:8px;font-weight:900;letter-spacing:.5px;"
    )
    return label


def _section_heading(title: str, subtitle: str) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    bubble = QLabel()
    bubble.setFixedSize(38, 38)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon("workflow", color=TEAL, size=20).pixmap(20, 20))
    bubble.setStyleSheet("background:#E8F7F7;border:none;border-radius:12px;")
    layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)
    copy = QVBoxLayout()
    copy.setSpacing(1)
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{NAVY};font-size:16px;font-weight:950;border:none;")
    note = QLabel(subtitle)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")
    copy.addWidget(heading)
    copy.addWidget(note)
    layout.addLayout(copy, 1)
    return row


def _solution_card(icon_name: str, title: str, detail: str, badge: str) -> QFrame:
    card = QFrame(objectName="Contact2026SolutionCard")
    card.setMinimumHeight(126)
    card.setStyleSheet(
        "QFrame#Contact2026SolutionCard{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:17px;}"
        "QFrame#Contact2026SolutionCard:hover{background:#FBFEFE;border:1px solid #9CCFD2;}"
    )
    box = QVBoxLayout(card)
    box.setContentsMargins(16, 14, 16, 14)
    box.setSpacing(8)
    top = QHBoxLayout()
    ico = QLabel()
    ico.setFixedSize(40, 40)
    ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ico.setPixmap(icon(icon_name, color=TEAL, size=22).pixmap(22, 22))
    ico.setStyleSheet("background:#E9F8F8;border:none;border-radius:13px;")
    top.addWidget(ico)
    top.addStretch(1)
    top.addWidget(_pill(badge, "teal"))
    box.addLayout(top)
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:950;border:none;")
    note = QLabel(detail)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
    box.addWidget(heading)
    box.addWidget(note, 1)
    return card


def _style_primary(button: QPushButton, text: str, icon_name: str) -> None:
    button.setText(text)
    button.setIcon(icon(icon_name, color=WHITE, size=17))
    button.setIconSize(QSize(17, 17))
    button.setMinimumHeight(44)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:11px;"
        "padding:10px 17px;font-size:10px;font-weight:900;}"
        "QPushButton:hover{background:#096D76;}QPushButton:pressed{background:#075D65;}"
        "QPushButton:disabled{background:#DCE6E9;color:#91A0AA;}"
    )


def _style_secondary(button: QPushButton, text: str, icon_name: str) -> None:
    button.setText(text)
    button.setIcon(icon(icon_name, color=NAVY, size=16))
    button.setIconSize(QSize(16, 16))
    button.setMinimumHeight(42)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #D1DEE5;border-radius:11px;"
        "padding:9px 14px;font-size:10px;font-weight:850;}"
        "QPushButton:hover{background:#F1F9F9;color:#0B7F89;border-color:#9ACDCF;}"
        "QPushButton:disabled{background:#F3F6F8;color:#9AA8B2;border-color:#DCE5EA;}"
    )


def apply_contact_executive_2026(main_window) -> None:
    """Recompose Contact / Workflows into the same 2026 control-center language.

    Existing form fields, submission signals, external links and update logic are
    reused unchanged. This pass changes layout and presentation only.
    """
    page = getattr(main_window, "contact_page", None)
    if page is None or bool(getattr(page, "_privacygate_contact_executive_2026", False)):
        return

    ai_pm_lab = _find_button(page, "AI PM LAB", "Visit AI PM LAB")
    framework = _find_button(page, "PropertyDex Framework", "Explore PropertyDex Framework")
    core = {
        widget
        for widget in (
            getattr(page, "name_input", None),
            getattr(page, "email_input", None),
            getattr(page, "message_input", None),
            getattr(page, "send_button", None),
            getattr(page, "update_button", None),
            ai_pm_lab,
            framework,
        )
        if isinstance(widget, QWidget)
    }
    root = page.layout()
    if root is None or not core:
        return

    for widget in core:
        widget.setParent(page)
    _clear_layout(root, core)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    scroll = QScrollArea(page)
    scroll.setObjectName("Contact2026Scroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    content = QWidget()
    content.setObjectName("Contact2026Content")
    body = QVBoxLayout(content)
    body.setContentsMargins(30, 24, 30, 28)
    body.setSpacing(18)
    scroll.setWidget(content)
    root.addWidget(scroll)

    hero = QFrame(objectName="Contact2026Hero")
    hero.setMinimumHeight(142)
    hero.setStyleSheet(
        "QFrame#Contact2026Hero{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        "stop:0 #062B4F,stop:.62 #084C68,stop:1 #0B7F89);border:none;border-radius:21px;}"
    )
    hero_row = QHBoxLayout(hero)
    hero_row.setContentsMargins(22, 20, 22, 20)
    hero_row.setSpacing(16)

    brand = QLabel()
    brand.setFixedSize(58, 58)
    brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo_path = resource_path("resources", "branding", "privacy-gate-icon.png")
    if logo_path.exists():
        pixmap = QPixmap(str(logo_path))
        brand.setPixmap(
            pixmap.scaled(
                44,
                44,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    else:
        brand.setPixmap(icon("contact", color="#A9ECE8", size=28).pixmap(28, 28))
    brand.setStyleSheet("background:rgba(255,255,255,26);border:1px solid rgba(255,255,255,45);border-radius:17px;")
    hero_row.addWidget(brand, 0, Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(3)
    eyebrow = QLabel("PRIVACYGATE · AI PM LAB")
    eyebrow.setStyleSheet("color:#9FE5E2;font-size:8px;font-weight:900;letter-spacing:1.2px;border:none;")
    title = QLabel("Contact & Custom Workflows")
    title.setStyleSheet("color:#FFFFFF;font-size:27px;font-weight:950;border:none;")
    subtitle = QLabel(
        "Build privacy-aware automations around real documents, connected apps and team workflows — while keeping PrivacyGate's local-first boundary explicit."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet("color:#D9EEF1;font-size:11px;border:none;")
    copy.addWidget(eyebrow)
    copy.addWidget(title)
    copy.addWidget(subtitle)
    hero_row.addLayout(copy, 1)

    status = QVBoxLayout()
    status.setSpacing(7)
    status.addWidget(_pill("OPTIONAL SERVICES", "teal"))
    status.addWidget(_pill("LOCAL-FIRST", "navy"))
    hero_row.addLayout(status)
    _shadow(hero, 30, 34, 7)
    body.addWidget(hero)

    body.addWidget(
        _section_heading(
            "What we can build around PrivacyGate",
            "Three common engagement areas, all designed to preserve the app's existing privacy model.",
        )
    )
    solutions = QGridLayout()
    solutions.setHorizontalSpacing(12)
    solutions.setVerticalSpacing(12)
    specs = (
        ("workflow", "Workflow automation", "n8n, email intake, watched folders, approvals and document routing.", "AUTOMATION"),
        ("cloud", "AI & app connections", "Protected handoff to ChatGPT, Claude, MCP and approved business tools.", "INTEGRATIONS"),
        ("document", "Real-estate operations", "Property management, brokerage, transaction and renovation workflows.", "OPERATIONS"),
    )
    for column, spec in enumerate(specs):
        solutions.addWidget(_solution_card(*spec), 0, column)
        solutions.setColumnStretch(column, 1)
    body.addLayout(solutions)

    workspace = QHBoxLayout()
    workspace.setSpacing(16)

    form = QFrame(objectName="Contact2026RequestCard")
    form.setStyleSheet("QFrame#Contact2026RequestCard{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:19px;}")
    form_box = QVBoxLayout(form)
    form_box.setContentsMargins(20, 18, 20, 18)
    form_box.setSpacing(11)

    form_head = QHBoxLayout()
    form_copy = QVBoxLayout()
    form_copy.setSpacing(2)
    form_title = QLabel("Tell us what you want to automate")
    form_title.setStyleSheet(f"color:{NAVY};font-size:17px;font-weight:950;border:none;")
    form_note = QLabel("Give us the current process, documents involved and tools already in use.")
    form_note.setWordWrap(True)
    form_note.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")
    form_copy.addWidget(form_title)
    form_copy.addWidget(form_note)
    form_head.addLayout(form_copy, 1)
    form_head.addWidget(_pill("WORKFLOW INTAKE", "indigo"), 0, Qt.AlignmentFlag.AlignTop)
    form_box.addLayout(form_head)

    fields = QHBoxLayout()
    fields.setSpacing(10)
    page.name_input.setPlaceholderText("Name or company")
    page.email_input.setPlaceholderText("Work email")
    page.name_input.setMinimumHeight(44)
    page.email_input.setMinimumHeight(44)
    fields.addWidget(page.name_input, 1)
    fields.addWidget(page.email_input, 1)
    form_box.addLayout(fields)

    page.message_input.setPlaceholderText(
        "Example: Gmail receives a lease → PrivacyGate imports and protects it locally → an approved protected copy enters an n8n workflow → a manager reviews the result."
    )
    page.message_input.setMinimumHeight(150)
    page.message_input.setMaximumHeight(190)
    form_box.addWidget(page.message_input)

    _style_primary(page.send_button, "Send workflow request", "contact")
    if ai_pm_lab is not None:
        _style_secondary(ai_pm_lab, "AI PM LAB", "external")
    if framework is not None:
        _style_secondary(framework, "PropertyDex Framework", "external")
    actions = QHBoxLayout()
    actions.setSpacing(8)
    actions.addWidget(page.send_button)
    if ai_pm_lab is not None:
        actions.addWidget(ai_pm_lab)
    if framework is not None:
        actions.addWidget(framework)
    actions.addStretch(1)
    form_box.addLayout(actions)
    _shadow(form, 22, 18, 4)
    workspace.addWidget(form, 7)

    right = QVBoxLayout()
    right.setSpacing(12)

    process = QFrame(objectName="Contact2026ProcessCard")
    process.setStyleSheet("QFrame#Contact2026ProcessCard{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:17px;}")
    process_box = QVBoxLayout(process)
    process_box.setContentsMargins(16, 15, 16, 15)
    process_box.setSpacing(10)
    process_title = QLabel("How a custom workflow starts")
    process_title.setStyleSheet(f"color:{NAVY};font-size:14px;font-weight:950;border:none;")
    process_box.addWidget(process_title)
    for number, heading, detail in (
        ("01", "Map the workflow", "Sources, handoffs, approvals and sensitive-data steps."),
        ("02", "Define the boundary", "Decide what stays local and what protected output may leave the device."),
        ("03", "Connect approved tools", "Automate only the destinations and accounts the workflow actually needs."),
    ):
        row = QHBoxLayout()
        row.setSpacing(10)
        badge = QLabel(number)
        badge.setFixedSize(30, 30)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("background:#0B7F89;color:#FFFFFF;border:none;border-radius:10px;font-size:8px;font-weight:900;")
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(1)
        head = QLabel(heading)
        head.setStyleSheet(f"color:{INK};font-size:10px;font-weight:900;border:none;")
        desc = QLabel(detail)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
        text.addWidget(head)
        text.addWidget(desc)
        row.addLayout(text, 1)
        process_box.addLayout(row)
    right.addWidget(process)

    updates = QFrame(objectName="Contact2026UpdateCard")
    updates.setStyleSheet("QFrame#Contact2026UpdateCard{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:17px;}")
    updates_box = QVBoxLayout(updates)
    updates_box.setContentsMargins(16, 14, 16, 14)
    updates_box.setSpacing(8)
    update_head = QHBoxLayout()
    update_title = QLabel("PrivacyGate update center")
    update_title.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:950;border:none;")
    update_head.addWidget(update_title, 1)
    update_head.addWidget(_pill(f"v{__version__}", "green"))
    updates_box.addLayout(update_head)
    update_note = QLabel("Check the installed release. Microsoft Store builds continue through the Store-managed update flow.")
    update_note.setWordWrap(True)
    update_note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
    updates_box.addWidget(update_note)
    _style_secondary(page.update_button, "Check for updates", "download")
    updates_box.addWidget(page.update_button)
    right.addWidget(updates)

    privacy = QFrame(objectName="Contact2026PrivacyCard")
    privacy.setStyleSheet("QFrame#Contact2026PrivacyCard{background:#F0FAFA;border:1px solid #CFEAEA;border-radius:17px;}")
    privacy_box = QHBoxLayout(privacy)
    privacy_box.setContentsMargins(15, 13, 15, 13)
    privacy_box.setSpacing(10)
    shield = QLabel()
    shield.setPixmap(icon("protect", color=TEAL, size=24).pixmap(24, 24))
    privacy_box.addWidget(shield, 0, Qt.AlignmentFlag.AlignTop)
    privacy_copy = QVBoxLayout()
    privacy_copy.setSpacing(2)
    privacy_title = QLabel("Privacy boundary stays intact")
    privacy_title.setStyleSheet(f"color:{NAVY};font-size:11px;font-weight:950;border:none;")
    privacy_note = QLabel(
        "Original documents, restore mappings and connector credentials remain local unless a workflow is explicitly designed otherwise."
    )
    privacy_note.setWordWrap(True)
    privacy_note.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
    privacy_copy.addWidget(privacy_title)
    privacy_copy.addWidget(privacy_note)
    privacy_box.addLayout(privacy_copy, 1)
    right.addWidget(privacy)
    right.addStretch(1)
    workspace.addLayout(right, 4)
    body.addLayout(workspace)
    body.addStretch(1)

    content.setStyleSheet(
        "QWidget#Contact2026Content{background:#F4F7F9;}"
        "QWidget#Contact2026Content QLabel{background:transparent;}"
        "QScrollArea#Contact2026Scroll{background:#F4F7F9;border:none;}"
        "QLineEdit,QPlainTextEdit{background:#FBFDFE;color:#17384E;border:1px solid #C9D7E0;"
        "border-radius:11px;padding:10px 11px;font-size:10px;}"
        "QLineEdit:focus,QPlainTextEdit:focus{background:#FFFFFF;border:1px solid #0B7F89;}"
    )
    page._privacygate_contact_executive_2026 = True
