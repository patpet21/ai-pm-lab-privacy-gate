from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors import ConnectedAppsService
from ai_pm_lab_privacy_gate.ui.connections_page import ConnectionsPage


_INSTALLED = False


PROVIDERS = (
    ("google_drive", "Google Drive", "Files, Docs, Sheets and folders", "Cloud document source"),
    ("clickup", "ClickUp", "Workspaces, tasks and project data", "Project management"),
    ("asana", "Asana", "Workspaces, projects and tasks", "Project management"),
    ("trello", "Trello", "Boards, lists and cards", "Project management"),
)


def _status_badge(text: str, connected: bool) -> QLabel:
    badge = QLabel(text)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if connected:
        badge.setStyleSheet(
            "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
            "border-radius:9px;padding:5px 9px;font-size:10px;font-weight:800;"
        )
    else:
        badge.setStyleSheet(
            "background:#F2F5F7;color:#6C7E8C;border:1px solid #D7E2EA;"
            "border-radius:9px;padding:5px 9px;font-size:10px;font-weight:800;"
        )
    return badge


def _provider_card(page: ConnectionsPage, service: ConnectedAppsService, provider: str, title: str, description: str, category: str) -> QFrame:
    card = QFrame(objectName="ConnectionCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(15, 14, 15, 14)
    layout.setSpacing(9)

    heading = QHBoxLayout()
    name = QLabel(title, objectName="SectionTitle")
    heading.addWidget(name)
    heading.addStretch(1)
    status = _status_badge("CONNECTED" if service.is_connected(provider) else "NOT CONNECTED", service.is_connected(provider))
    heading.addWidget(status)
    layout.addLayout(heading)

    type_label = QLabel(category)
    type_label.setStyleSheet("color:#D3A13B;font-size:10px;font-weight:800;")
    layout.addWidget(type_label)

    info = QLabel(description, objectName="Muted")
    info.setWordWrap(True)
    layout.addWidget(info)

    privacy = QLabel("Read-only source • credentials protected locally • AI access blocked until PrivacyGate protection")
    privacy.setWordWrap(True)
    privacy.setStyleSheet("color:#557184;font-size:10px;")
    layout.addWidget(privacy)
    layout.addStretch(1)

    actions = QHBoxLayout()
    connect = QPushButton("Reconnect" if service.is_connected(provider) else "Connect", objectName="Primary")
    test = QPushButton("Test", objectName="Secondary")
    browse = QPushButton("Browse", objectName="Secondary")
    disconnect = QPushButton("Disconnect", objectName="Secondary")
    browse.setEnabled(service.is_connected(provider))
    test.setEnabled(service.is_connected(provider))
    disconnect.setEnabled(service.is_connected(provider))

    actions.addWidget(connect)
    actions.addWidget(test)
    actions.addWidget(browse)
    actions.addStretch(1)
    actions.addWidget(disconnect)
    layout.addLayout(actions)

    def refresh_card() -> None:
        connected = service.is_connected(provider)
        status.setText("CONNECTED" if connected else "NOT CONNECTED")
        status.setStyleSheet(_status_badge("x", connected).styleSheet())
        connect.setText("Reconnect" if connected else "Connect")
        browse.setEnabled(connected)
        test.setEnabled(connected)
        disconnect.setEnabled(connected)

    def configure() -> None:
        dialog = QDialog(page)
        dialog.setWindowTitle(f"Connect {title}")
        dialog.resize(560, 330 if provider == "trello" else 270)
        root = QVBoxLayout(dialog)
        root.addWidget(QLabel(f"Connect {title}", objectName="PageTitle"))
        note = QLabel(
            "This first connector build uses a provider access credential for testing. "
            "It is encrypted with Windows DPAPI or stored in macOS Keychain and never written to the app configuration in plain text."
        )
        note.setWordWrap(True)
        note.setObjectName("Muted")
        root.addWidget(note)

        key_input = None
        if provider == "trello":
            root.addWidget(QLabel("Trello API key", objectName="FieldLabel"))
            key_input = QLineEdit()
            key_input.setEchoMode(QLineEdit.EchoMode.Password)
            key_input.setPlaceholderText("Paste Trello API key")
            root.addWidget(key_input)

        root.addWidget(QLabel("Access token", objectName="FieldLabel"))
        token_input = QLineEdit()
        token_input.setEchoMode(QLineEdit.EchoMode.Password)
        token_input.setPlaceholderText("Paste access token")
        root.addWidget(token_input)

        feedback = QLabel("")
        feedback.setWordWrap(True)
        feedback.setStyleSheet("color:#557184;")
        root.addWidget(feedback)

        buttons = QHBoxLayout()
        save_test = QPushButton("Save & Test", objectName="Primary")
        cancel = QPushButton("Cancel", objectName="Secondary")
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save_test)
        root.addLayout(buttons)
        cancel.clicked.connect(dialog.reject)

        def save_and_test() -> None:
            try:
                service.save_credentials(
                    provider,
                    token=token_input.text(),
                    api_key=key_input.text() if key_input is not None else "",
                )
            except Exception as exc:
                feedback.setText(str(exc))
                return
            result = service.test_connection(provider)
            if not result.ok:
                feedback.setText(result.detail)
                return
            feedback.setText(f"Connected: {result.account_label}")
            dialog.accept()
            refresh_card()

        save_test.clicked.connect(save_and_test)
        dialog.exec()

    def run_test() -> None:
        result = service.test_connection(provider)
        if result.ok:
            QMessageBox.information(page, f"{title} connected", f"{result.account_label}\n\n{result.detail}")
        else:
            QMessageBox.warning(page, f"{title} connection failed", result.detail)

    def browse_items() -> None:
        try:
            items = service.list_root_items(provider, limit=40)
        except Exception as exc:
            QMessageBox.warning(page, f"Unable to read {title}", str(exc))
            return
        dialog = QDialog(page)
        dialog.setWindowTitle(f"{title} — available sources")
        dialog.resize(760, 560)
        root = QVBoxLayout(dialog)
        root.addWidget(QLabel(f"{title} sources", objectName="PageTitle"))
        explanation = QLabel(
            "These items were read directly from your connected account. Nothing in this list has been sent to an AI. "
            "The next PrivacyGate step will import selected content into the local protection pipeline."
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("Muted")
        root.addWidget(explanation)
        listing = QListWidget()
        for item in items:
            row = QListWidgetItem(f"{item.title}\n{item.kind}  {item.subtitle}".strip())
            row.setData(Qt.ItemDataRole.UserRole, item.item_id)
            listing.addItem(row)
        if not items:
            listing.addItem("No items returned by this provider.")
        root.addWidget(listing, 1)
        footer = QHBoxLayout()
        count = QLabel(f"{len(items)} item(s)")
        close = QPushButton("Close", objectName="Secondary")
        footer.addWidget(count)
        footer.addStretch(1)
        footer.addWidget(close)
        root.addLayout(footer)
        close.clicked.connect(dialog.accept)
        dialog.exec()

    def do_disconnect() -> None:
        answer = QMessageBox.question(
            page,
            f"Disconnect {title}?",
            "The locally protected credential will be deleted. PrivacyGate Library documents are not affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            service.disconnect(provider)
            refresh_card()

    connect.clicked.connect(configure)
    test.clicked.connect(run_test)
    browse.clicked.connect(browse_items)
    disconnect.clicked.connect(do_disconnect)
    return card


def _add_connected_apps(page: ConnectionsPage) -> None:
    if page.section != "cloud" or page.library is None:
        return
    service = ConnectedAppsService(page.library.data_dir)
    root = page.layout()

    section = QFrame(objectName="Card")
    section_layout = QVBoxLayout(section)
    section_layout.setContentsMargins(16, 15, 16, 16)
    section_layout.setSpacing(11)

    header = QHBoxLayout()
    titles = QVBoxLayout()
    titles.addWidget(QLabel("Connected Apps", objectName="SectionTitle"))
    subtitle = QLabel(
        "Bring approved business data into PrivacyGate first. Original values remain local; only protected content can later be exposed to AI."
    )
    subtitle.setWordWrap(True)
    subtitle.setObjectName("Muted")
    titles.addWidget(subtitle)
    header.addLayout(titles, 1)
    pro = QLabel("PRO / BUSINESS")
    pro.setStyleSheet(
        "background:#FFF6DF;color:#8B641C;border:1px solid #E8CE8A;"
        "border-radius:9px;padding:6px 10px;font-size:10px;font-weight:900;"
    )
    header.addWidget(pro, alignment=Qt.AlignmentFlag.AlignTop)
    section_layout.addLayout(header)

    grid = QGridLayout()
    grid.setSpacing(12)
    for index, provider in enumerate(PROVIDERS):
        grid.addWidget(_provider_card(page, service, *provider), index // 2, index % 2)
    section_layout.addLayout(grid)

    roadmap = QLabel("Next providers: Microsoft OneDrive / SharePoint • Notion • Dropbox • Gmail • Slack")
    roadmap.setStyleSheet("color:#61798A;font-size:10px;padding-top:3px;")
    section_layout.addWidget(roadmap)

    # Insert after page title/subtitle and before the existing MCP cards.
    root.insertWidget(2, section)
    page._connected_apps_service = service
    page._connected_apps_section = section


def install_connected_apps_ui() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    original_init = ConnectionsPage.__init__

    def wrapped_init(self: ConnectionsPage, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        _add_connected_apps(self)

    ConnectionsPage.__init__ = wrapped_init
