from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ai_pm_lab_privacy_gate.ui.gmail_addon_import import open_gmail_addon_import
from ai_pm_lab_privacy_gate.ui.gmail_addon_readonly_import import open_gmail_readonly_import
from ai_pm_lab_privacy_gate.ui.iconography import icon


NAVY = "#062B4F"
MUTED = "#607789"


def _mode_card(
    title: str,
    badge: str,
    description: str,
    detail: str,
    primary: bool,
) -> tuple[QFrame, QPushButton]:
    card = QFrame(objectName="GmailModeCard")
    card.setStyleSheet(
        "QFrame#GmailModeCard{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:12px;}"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(8)

    head = QHBoxLayout()
    name = QLabel(title)
    name.setStyleSheet(f"color:{NAVY};font-size:14px;font-weight:950;")
    tag = QLabel(badge)
    tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if primary:
        tag.setStyleSheet(
            "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
            "border-radius:8px;padding:4px 8px;font-size:7px;font-weight:950;"
        )
    else:
        tag.setStyleSheet(
            "background:#FFF8E8;color:#6D5320;border:1px solid #F0DCA8;"
            "border-radius:8px;padding:4px 8px;font-size:7px;font-weight:950;"
        )
    head.addWidget(name)
    head.addStretch(1)
    head.addWidget(tag)
    layout.addLayout(head)

    copy = QLabel(description)
    copy.setWordWrap(True)
    copy.setStyleSheet(f"color:{MUTED};font-size:9px;font-weight:650;")
    layout.addWidget(copy)

    technical = QLabel(detail)
    technical.setWordWrap(True)
    technical.setStyleSheet("color:#718697;font-size:8px;")
    layout.addWidget(technical)

    button = QPushButton("Use this mode")
    button.setMinimumHeight(40)
    if primary:
        button.setIcon(icon("protect", color="#FFFFFF", size=16))
        button.setStyleSheet(
            "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
            "border-radius:9px;padding:8px 14px;font-weight:850;}"
            "QPushButton:hover{background:#095F6B;border-color:#095F6B;}"
        )
    else:
        button.setIcon(icon("mail", color="#17384E", size=16))
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #B7C8D4;"
            "border-radius:9px;padding:8px 14px;font-weight:850;}"
            "QPushButton:hover{background:#F5F9FB;border-color:#8EABB9;}"
        )
    layout.addWidget(button)
    return card, button


def open_gmail_mode_picker(main_window) -> None:
    """Let the user choose between both supported Gmail add-on access models."""
    dialog = QDialog(main_window)
    dialog.setObjectName("GmailModePicker")
    dialog.setWindowTitle("Gmail access mode")
    dialog.resize(720, 470)
    dialog.setMinimumSize(660, 430)
    dialog.setStyleSheet("QDialog#GmailModePicker{background:#F8FBFC;}")

    root = QVBoxLayout(dialog)
    root.setContentsMargins(22, 20, 22, 18)
    root.setSpacing(12)

    title = QLabel("Choose how PrivacyGate works with Gmail")
    title.setStyleSheet(f"color:{NAVY};font-size:21px;font-weight:950;")
    subtitle = QLabel(
        "Both modes avoid mailbox-wide gmail.readonly access. Standard keeps the narrowest permission; Enhanced gives a richer Gmail sidebar preview."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:9px;font-weight:550;")
    root.addWidget(title)
    root.addWidget(subtitle)

    standard_card, standard = _mode_card(
        "Standard privacy mode",
        "RECOMMENDED",
        "Open an email in Gmail and explicitly press “Send to PrivacyGate”. PrivacyGate receives only that selected message.",
        "Google scope: gmail.addons.current.message.action · Non-sensitive current-message action flow.",
        True,
    )
    enhanced_card, enhanced = _mode_card(
        "Enhanced Gmail preview",
        "RICHER PREVIEW",
        "The PrivacyGate Gmail sidebar can display the subject, sender and body of the currently open email before you send it into Protect.",
        "Google scope: gmail.addons.current.message.readonly · Sensitive current-message permission, without mailbox-wide gmail.readonly.",
        False,
    )
    root.addWidget(standard_card)
    root.addWidget(enhanced_card)

    note = QLabel(
        "Each mode keeps its own pairing and deployment configuration, so testing Enhanced does not replace or break Standard."
    )
    note.setWordWrap(True)
    note.setStyleSheet("color:#718697;font-size:8px;font-weight:650;")
    root.addWidget(note)

    close = QPushButton("Cancel")
    close.setMinimumHeight(36)
    close.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C4D3DE;"
        "border-radius:9px;padding:7px 13px;font-weight:750;}"
    )
    root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def choose_standard() -> None:
        dialog.accept()
        open_gmail_addon_import(main_window)

    def choose_enhanced() -> None:
        dialog.accept()
        open_gmail_readonly_import(main_window)

    standard.clicked.connect(choose_standard)
    enhanced.clicked.connect(choose_enhanced)
    close.clicked.connect(dialog.reject)
    dialog.exec()
