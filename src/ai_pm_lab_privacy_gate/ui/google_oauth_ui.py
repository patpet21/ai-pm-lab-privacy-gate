from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage
from ai_pm_lab_privacy_gate.ui.connections_page import ConnectionsPage


_INSTALLED = False
_APPS_NOTICE_INSTALLED = False


def _google_connection_notice(parent, provider: str, title: str) -> bool:
    """Explain Google beta/verification status before opening OAuth.

    This is intentionally informational rather than a replacement for Google's
    own consent screen. It helps users understand why an unverified-app warning
    can appear during the current beta and exactly what PrivacyGate will request.
    """
    if provider not in {"google_drive", "gmail"}:
        return True

    is_drive = provider == "google_drive"
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"Connect {title}")
    dialog.setModal(True)
    dialog.setMinimumWidth(650)
    dialog.resize(690, 560 if is_drive else 535)
    dialog.setStyleSheet("QDialog{background:#F7F9FA;color:#17384E;}")

    root = QVBoxLayout(dialog)
    root.setContentsMargins(26, 24, 26, 22)
    root.setSpacing(13)

    top = QHBoxLayout()
    badge = QLabel("BETA · GOOGLE VERIFICATION IN PROGRESS")
    badge.setStyleSheet(
        "background:#FFF6DF;color:#8B641C;border:1px solid #E8CE8A;"
        "border-radius:9px;padding:6px 9px;font-size:9px;font-weight:900;"
    )
    top.addWidget(badge)
    top.addStretch(1)
    root.addLayout(top)

    heading = QLabel(f"Before you connect {title}")
    heading.setStyleSheet("color:#062B4F;font-size:22px;font-weight:950;")
    root.addWidget(heading)

    intro = QLabel(
        "PrivacyGate is currently completing Google's OAuth verification process. "
        "During this beta, Google may display a ‘Google hasn't verified this app’ warning before the normal consent screen."
    )
    intro.setWordWrap(True)
    intro.setStyleSheet("color:#526C7D;font-size:11px;line-height:1.45;")
    root.addWidget(intro)

    warning = QFrame()
    warning.setStyleSheet(
        "QFrame{background:#FFF7F5;border:1px solid #E8C9C4;border-radius:12px;}"
    )
    warning_layout = QHBoxLayout(warning)
    warning_layout.setContentsMargins(14, 12, 14, 12)
    warning_layout.setSpacing(12)
    warning_icon = QLabel("⚠")
    warning_icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
    warning_icon.setFixedWidth(32)
    warning_icon.setStyleSheet("color:#D84A3A;font-size:25px;font-weight:900;border:0;")
    warning_layout.addWidget(warning_icon)
    warning_text = QLabel(
        "If you intentionally started this connection and trust this PrivacyGate beta build, "
        "choose Advanced on Google's warning page and continue to AI PM LAB Privacy Gate. "
        "You can cancel the connection at any time."
    )
    warning_text.setWordWrap(True)
    warning_text.setStyleSheet("color:#633A36;font-size:10px;font-weight:650;border:0;")
    warning_layout.addWidget(warning_text, 1)
    root.addWidget(warning)

    access_title = QLabel("What PrivacyGate requests")
    access_title.setStyleSheet("color:#062B4F;font-size:12px;font-weight:900;")
    root.addWidget(access_title)

    if is_drive:
        points = (
            "Read-only access to existing Google Drive files so you can browse and search them inside PrivacyGate before choosing a document.",
            "The file you choose is imported as a local working copy for Scan and Protect.",
            "PrivacyGate does not create, modify, move or delete your original Google Drive files.",
            "Document content is not uploaded to a PrivacyGate document server for this workflow.",
        )
    else:
        points = (
            "Gmail read-only access so you can search existing messages and select the email you want to protect.",
            "PrivacyGate must read the selected email body, not only metadata, so sensitive content can be scanned locally.",
            "PrivacyGate does not send, modify or delete Gmail messages.",
            "Selected email content is brought into the local PrivacyGate protection workflow.",
        )

    for text in points:
        line = QLabel(f"✓  {text}")
        line.setWordWrap(True)
        line.setStyleSheet("color:#17384E;font-size:10px;font-weight:650;padding:2px 0;")
        root.addWidget(line)

    privacy_note = QLabel(
        "PrivacyGate never asks you to paste your Google password or a personal access token. "
        "Authentication is handled directly by Google OAuth."
    )
    privacy_note.setWordWrap(True)
    privacy_note.setStyleSheet(
        "background:#FFFFFF;color:#61798A;border:1px solid #DCE5EA;"
        "border-radius:9px;padding:10px 12px;font-size:9px;"
    )
    root.addWidget(privacy_note)

    actions = QHBoxLayout()
    actions.addStretch(1)
    cancel = QPushButton("Cancel")
    cancel.setMinimumHeight(38)
    cancel.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C5D4DE;"
        "border-radius:8px;padding:7px 16px;font-weight:750;}"
        "QPushButton:hover{background:#EDF7F7;border-color:#9BCDD1;}"
    )
    proceed = QPushButton("Continue to Google")
    proceed.setMinimumHeight(38)
    proceed.setDefault(True)
    proceed.setStyleSheet(
        "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
        "border-radius:8px;padding:7px 17px;font-weight:850;}"
        "QPushButton:hover{background:#095F6B;border-color:#095F6B;}"
    )
    actions.addWidget(cancel)
    actions.addWidget(proceed)
    root.addLayout(actions)

    cancel.clicked.connect(dialog.reject)
    proceed.clicked.connect(dialog.accept)
    return dialog.exec() == QDialog.DialogCode.Accepted


def _install_apps_google_connection_notice() -> None:
    """Cover Apps Connect/Reconnect and multi-account Add account flows."""
    global _APPS_NOTICE_INSTALLED
    if _APPS_NOTICE_INSTALLED:
        return
    _APPS_NOTICE_INSTALLED = True

    previous_connect = AppsHubPage._connect

    def connect_with_notice(
        self: AppsHubPage,
        provider: str,
        title: str,
        supported: bool,
        integration_path: str,
    ) -> None:
        if supported and provider in {"google_drive", "gmail"}:
            if not _google_connection_notice(self, provider, title):
                return
        previous_connect(self, provider, title, supported, integration_path)

    AppsHubPage._connect = connect_with_notice


def _wire_google_oauth(page: ConnectionsPage) -> None:
    if page.section != "cloud" or not hasattr(page, "_connected_apps_section"):
        return
    service = getattr(page, "_connected_apps_service", None)
    if service is None:
        return

    google_card = None
    for card in page._connected_apps_section.findChildren(QFrame, "ConnectionCard"):
        if any(label.text() == "Google Drive" for label in card.findChildren(QLabel)):
            google_card = card
            break
    if google_card is None:
        return

    buttons = google_card.findChildren(QPushButton)
    connect = next((b for b in buttons if b.text() in {"Connect", "Reconnect"}), None)
    test = next((b for b in buttons if b.text() == "Test"), None)
    browse = next((b for b in buttons if b.text() == "Browse"), None)
    disconnect = next((b for b in buttons if b.text() == "Disconnect"), None)
    status = next((l for l in google_card.findChildren(QLabel) if l.text() in {"CONNECTED", "NOT CONNECTED"}), None)
    if connect is None:
        return

    try:
        connect.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass

    def update_state() -> None:
        connected = service.is_connected("google_drive")
        connect.setText("Reconnect" if connected else "Connect")
        for button in (test, browse, disconnect):
            if button is not None:
                button.setEnabled(connected)
        if status is not None:
            status.setText("CONNECTED" if connected else "NOT CONNECTED")
            status.setStyleSheet(
                ("background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;" if connected else
                 "background:#F2F5F7;color:#6C7E8C;border:1px solid #D7E2EA;")
                + "border-radius:9px;padding:5px 9px;font-size:10px;font-weight:800;"
            )

    def connect_google() -> None:
        if not _google_connection_notice(page, "google_drive", "Google Drive"):
            return
        try:
            service.connect_google_oauth()
            result = service.test_connection("google_drive")
            update_state()
            if result.ok:
                QMessageBox.information(
                    page,
                    "Google Drive connected",
                    f"{result.account_label}\n\nGoogle Drive is now connected to PrivacyGate. "
                    "The authorization is stored securely on this device and will be refreshed automatically.",
                )
            else:
                QMessageBox.warning(page, "Google Drive connection", result.detail)
        except Exception as exc:
            QMessageBox.warning(
                page,
                "Google Drive connection failed",
                str(exc),
            )
            update_state()

    connect.clicked.connect(connect_google)
    connect.setToolTip("Sign in with Google in your browser. No access token needs to be pasted.")
    update_state()


def install_google_oauth_ui() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    _install_apps_google_connection_notice()
    original_init = ConnectionsPage.__init__

    def wrapped_init(self: ConnectionsPage, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        _wire_google_oauth(self)

    ConnectionsPage.__init__ = wrapped_init
