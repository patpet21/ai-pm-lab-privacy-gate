from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate import __version__
from ai_pm_lab_privacy_gate.ui.iconography import icon

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
BORDER = "#DCE5EA"
SOFT = "#F7FAFC"
WHITE = "#FFFFFF"
GREEN = "#23824B"


def _card(name: str) -> QFrame:
    frame = QFrame(objectName=name)
    frame.setStyleSheet(
        f"QFrame#{name}{{background:#FFFFFF;border:1px solid {BORDER};border-radius:14px;}}"
    )
    return frame


def _title(text: str, size: int = 13) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color:{NAVY};font-size:{size}px;font-weight:900;border:none;background:transparent;"
    )
    return label


def _muted(text: str, size: int = 9) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        f"color:{MUTED};font-size:{size}px;border:none;background:transparent;"
    )
    return label


def _primary(button: QPushButton) -> None:
    button.setMinimumHeight(40)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:#0B7F89;color:#FFFFFF;border:1px solid #0B7F89;"
        "border-radius:9px;padding:9px 15px;font-size:10px;font-weight:850;}"
        "QPushButton:hover{background:#096D76;border-color:#096D76;}"
        "QPushButton:disabled{background:#DCE5E9;color:#8B9AA5;border-color:#DCE5E9;}"
    )


def _secondary(button: QPushButton) -> None:
    button.setMinimumHeight(40)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;"
        "border-radius:9px;padding:9px 13px;font-size:10px;font-weight:800;}"
        "QPushButton:hover{background:#F0FAFA;color:#0B7F89;border-color:#9AC9CD;}"
        "QPushButton:disabled{background:#F3F6F8;color:#9AA8B2;border-color:#DCE5EA;}"
    )


def _feature_card(icon_name: str, heading: str, detail: str) -> QFrame:
    card = _card(f"ContactFeature_{heading.replace(' ', '_')}")
    card.setMinimumHeight(120)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(15, 14, 15, 14)
    layout.setSpacing(7)

    bubble = QLabel()
    bubble.setFixedSize(38, 38)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon(icon_name, color=TEAL, size=21).pixmap(21, 21))
    bubble.setStyleSheet("background:#E8F7F7;border:none;border-radius:19px;")
    layout.addWidget(bubble)
    layout.addWidget(_title(heading, 11))
    layout.addWidget(_muted(detail, 8))
    layout.addStretch(1)
    return card


def _find_button(page: QWidget, text: str) -> QPushButton | None:
    return next(
        (button for button in page.findChildren(QPushButton) if button.text().strip() == text),
        None,
    )


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


def apply_contact_workflows_polish(main_window) -> None:
    page = getattr(main_window, "contact_page", None)
    if page is None or getattr(page, "_privacygate_contact_polished", False):
        return
    page._privacygate_contact_polished = True
    page.setObjectName("PremiumContactPage")

    ai_pm_lab = _find_button(page, "Visit AI PM LAB")
    framework = _find_button(page, "Explore PropertyDex Framework")
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
    for widget in core:
        widget.setParent(page)

    root = page.layout()
    if root is None:
        return
    _clear_layout(root, core)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    scroll = QScrollArea(page)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    content = QWidget()
    content.setObjectName("PremiumContactContent")
    body = QVBoxLayout(content)
    body.setContentsMargins(28, 22, 28, 22)
    body.setSpacing(14)
    scroll.setWidget(content)
    root.addWidget(scroll)

    header = QHBoxLayout()
    titles = QVBoxLayout()
    titles.setSpacing(3)
    titles.addWidget(_title("Contact & Workflows", 28))
    titles.addWidget(
        _muted(
            "Design optional automations around PrivacyGate without changing its local-first privacy boundary.",
            11,
        )
    )
    header.addLayout(titles, 1)
    badge = QLabel("LOCAL-FIRST  •  OPTIONAL SERVICES")
    badge.setStyleSheet(
        "background:#E8F7F7;color:#0B7F89;border:1px solid #B8E1E4;border-radius:10px;"
        "padding:7px 11px;font-size:8px;font-weight:900;"
    )
    header.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
    body.addLayout(header)

    features = QGridLayout()
    features.setHorizontalSpacing(12)
    features.setVerticalSpacing(12)
    specs = (
        ("workflow", "Workflow design", "n8n, email intake, watched folders and document routing."),
        ("cloud", "AI connections", "Protected handoff to ChatGPT, Claude, MCP and approved business tools."),
        ("document", "Real-estate operations", "Property management, brokerage and project / renovation workflows."),
    )
    for column, spec in enumerate(specs):
        features.addWidget(_feature_card(*spec), 0, column)
        features.setColumnStretch(column, 1)
    body.addLayout(features)

    main = QHBoxLayout()
    main.setSpacing(14)

    form = _card("ContactRequestCard")
    form_layout = QVBoxLayout(form)
    form_layout.setContentsMargins(18, 17, 18, 17)
    form_layout.setSpacing(10)
    form_layout.addWidget(_title("Tell us what you want to automate", 14))
    form_layout.addWidget(
        _muted(
            "Describe the current process, the documents involved, and the tools your team already uses.",
            9,
        )
    )

    fields = QHBoxLayout()
    fields.setSpacing(9)
    page.name_input.setPlaceholderText("Name or company")
    page.email_input.setPlaceholderText("Work email")
    fields.addWidget(page.name_input, 1)
    fields.addWidget(page.email_input, 1)
    form_layout.addLayout(fields)

    page.message_input.setPlaceholderText(
        "Example: Gmail receives a lease, PrivacyGate imports it locally, protects sensitive data, then sends the protected copy into an n8n workflow..."
    )
    page.message_input.setMinimumHeight(150)
    page.message_input.setMaximumHeight(240)
    form_layout.addWidget(page.message_input, 1)

    action_row = QHBoxLayout()
    action_row.setSpacing(8)
    _primary(page.send_button)
    action_row.addWidget(page.send_button)
    if ai_pm_lab is not None:
        ai_pm_lab.setText("AI PM LAB")
        _secondary(ai_pm_lab)
        action_row.addWidget(ai_pm_lab)
    if framework is not None:
        framework.setText("PropertyDex Framework")
        _secondary(framework)
        action_row.addWidget(framework)
    action_row.addStretch(1)
    form_layout.addLayout(action_row)
    main.addWidget(form, 7)

    side = QVBoxLayout()
    side.setSpacing(12)

    process = _card("ContactProcessCard")
    process_box = QVBoxLayout(process)
    process_box.setContentsMargins(16, 15, 16, 15)
    process_box.setSpacing(9)
    process_box.addWidget(_title("How a custom workflow starts", 12))
    for number, heading, detail in (
        ("1", "Map the workflow", "Identify sources, handoffs, approvals and privacy-sensitive steps."),
        ("2", "Define the privacy boundary", "Keep originals, mappings and connector credentials on the device."),
        ("3", "Automate safely", "Connect only the approved protected content to downstream tools."),
    ):
        row = QHBoxLayout()
        row.setSpacing(9)
        bubble = QLabel(number)
        bubble.setFixedSize(25, 25)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setStyleSheet(
            "background:#0B7F89;color:#FFFFFF;border:none;border-radius:12px;font-size:8px;font-weight:900;"
        )
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(_title(heading, 9))
        text.addWidget(_muted(detail, 8))
        row.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignTop)
        row.addLayout(text, 1)
        process_box.addLayout(row)
    side.addWidget(process)

    updates = _card("ContactUpdatesCard")
    updates_box = QVBoxLayout(updates)
    updates_box.setContentsMargins(16, 15, 16, 15)
    updates_box.setSpacing(7)
    update_header = QHBoxLayout()
    update_header.addWidget(_title("Updates & release", 12), 1)
    current = QLabel(f"v{__version__}")
    current.setStyleSheet(
        "background:#F0F5F7;color:#425D70;border:none;border-radius:7px;"
        "padding:4px 7px;font-size:8px;font-weight:850;"
    )
    update_header.addWidget(current)
    updates_box.addLayout(update_header)
    updates_box.addWidget(
        _muted(
            "Check the current PrivacyGate release without leaving the app. Store-managed installs continue to use the Microsoft Store update flow.",
            8,
        )
    )
    _secondary(page.update_button)
    updates_box.addWidget(page.update_button)
    side.addWidget(updates)

    boundary = _card("ContactBoundaryCard")
    boundary_box = QHBoxLayout(boundary)
    boundary_box.setContentsMargins(15, 13, 15, 13)
    shield = QLabel()
    shield.setPixmap(icon("protect", color=TEAL, size=22).pixmap(22, 22))
    boundary_box.addWidget(shield, alignment=Qt.AlignmentFlag.AlignTop)
    text = QVBoxLayout()
    text.addWidget(_title("Privacy boundary stays intact", 10))
    note = _muted(
        "A custom workflow can use PrivacyGate outputs, but original documents, restore mappings and local connector credentials remain on the employee device unless you explicitly design otherwise.",
        8,
    )
    text.addWidget(note)
    boundary_box.addLayout(text, 1)
    side.addWidget(boundary)
    side.addStretch(1)

    main.addLayout(side, 4)
    body.addLayout(main, 1)

    page.setStyleSheet(
        "QWidget#PremiumContactPage,QWidget#PremiumContactContent{background:#F7FAFC;}"
        "QLineEdit,QPlainTextEdit{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;"
        "border-radius:9px;padding:9px 10px;font-size:10px;}"
        "QLineEdit:focus,QPlainTextEdit:focus{border:1px solid #0B7F89;}"
    )


_DIALOG_STYLE = """
QDialog, QMessageBox {
    background: #F7FAFC;
    color: #17384E;
}
QDialog QLabel, QMessageBox QLabel {
    color: #17384E;
    background: transparent;
}
QMessageBox QPushButton#PrivacyGateDialogSecondary,
QMessageBox QPushButton#PrivacyGateDialogPrimary,
QMessageBox QPushButton#PrivacyGateDialogDanger {
    min-height: 34px;
    padding: 7px 13px;
    border-radius: 8px;
    border: 1px solid #C9D7E0;
    background: #FFFFFF;
    color: #17384E;
    font-weight: 700;
}
QMessageBox QPushButton#PrivacyGateDialogSecondary:hover {
    background: #EAF7F7;
    color: #0B7F89;
    border-color: #9AC9CD;
}
QDialog QLineEdit, QDialog QPlainTextEdit, QDialog QTextEdit, QDialog QComboBox {
    background: #FFFFFF;
    color: #17384E;
    border: 1px solid #C9D7E0;
    border-radius: 8px;
    padding: 7px 9px;
}
QDialog QLineEdit:focus, QDialog QPlainTextEdit:focus, QDialog QTextEdit:focus, QDialog QComboBox:focus {
    border: 1px solid #0B7F89;
}
QMessageBox QPushButton#PrivacyGateDialogPrimary {
    background: #0B7F89;
    color: #FFFFFF;
    border-color: #0B7F89;
}
QMessageBox QPushButton#PrivacyGateDialogPrimary:hover {
    background: #096D76;
    border-color: #096D76;
}
QMessageBox QPushButton#PrivacyGateDialogDanger {
    background: #FFFFFF;
    color: #A23A3A;
    border-color: #E7B8B8;
}
QMessageBox QPushButton#PrivacyGateDialogDanger:hover {
    background: #FDECEC;
    color: #8E2F2F;
    border-color: #D99393;
}
"""


class _DialogPolishFilter(QObject):
    def eventFilter(self, watched, event):  # noqa: N802 - Qt API
        if event.type() == QEvent.Type.Show and isinstance(watched, QDialog):
            if not bool(watched.property("privacygateDialogPolished")):
                watched.setProperty("privacygateDialogPolished", True)
                watched.setStyleSheet(watched.styleSheet() + _DIALOG_STYLE)
                if isinstance(watched, QMessageBox):
                    watched.setMinimumWidth(460)
                    destructive = {
                        QMessageBox.StandardButton.Discard,
                        QMessageBox.StandardButton.Abort,
                    }
                    affirmative = {
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.StandardButton.Yes,
                        QMessageBox.StandardButton.Save,
                        QMessageBox.StandardButton.Apply,
                    }
                    for button in watched.buttons():
                        standard = watched.standardButton(button)
                        if standard in destructive:
                            button.setObjectName("PrivacyGateDialogDanger")
                        elif standard in affirmative or button is watched.defaultButton():
                            button.setObjectName("PrivacyGateDialogPrimary")
                        else:
                            button.setObjectName("PrivacyGateDialogSecondary")
        return super().eventFilter(watched, event)


def apply_popup_visual_polish(main_window) -> None:
    app = QApplication.instance()
    if app is None or getattr(app, "_privacygate_dialog_polish_filter", None) is not None:
        return
    event_filter = _DialogPolishFilter(app)
    app.installEventFilter(event_filter)
    app._privacygate_dialog_polish_filter = event_filter
