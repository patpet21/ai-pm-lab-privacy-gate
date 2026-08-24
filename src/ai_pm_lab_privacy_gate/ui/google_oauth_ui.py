from __future__ import annotations

from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QFrame

from ai_pm_lab_privacy_gate.ui.connections_page import ConnectionsPage


_INSTALLED = False


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
    original_init = ConnectionsPage.__init__

    def wrapped_init(self: ConnectionsPage, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        _wire_google_oauth(self)

    ConnectionsPage.__init__ = wrapped_init
