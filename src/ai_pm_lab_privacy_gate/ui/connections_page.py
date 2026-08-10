from __future__ import annotations

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
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
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.mcp.config import client_config_json, mcp_launch_spec
from ai_pm_lab_privacy_gate.infrastructure.mcp.remote import RemoteMcpManager
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository


class ConnectionsPage(QWidget):
    def __init__(
        self,
        section: str = "local",
        library: LibraryRepository | None = None,
        remote_mcp: RemoteMcpManager | None = None,
    ) -> None:
        super().__init__()
        self.section = section
        self.library = library
        self.remote_mcp = remote_mcp
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)
        title = "Local Automation" if section == "local" else "Cloud, MCP & Email"
        subtitle = (
            "Free-ready architecture for n8n and a future opt-in localhost API. Nothing is running yet."
            if section == "local"
            else "Optional customer-owned or managed integrations. Privacy Gate remains useful without them."
        )
        root.addWidget(QLabel(title, objectName="PageTitle"))
        root.addWidget(QLabel(subtitle, objectName="Muted"))
        grid = QGridLayout()
        grid.setSpacing(14)
        if section == "local":
            cards = [
                ("Manual workflow", "Ready", "Copy protected content, use any AI chat, then restore the response locally.", "Open ChatGPT", self._open_chatgpt),
                ("n8n Local Automation", "Planned", "Send text to Privacy Gate on localhost, receive protected text, then continue in an n8n workflow.", "View roadmap", self._not_ready),
                ("Privacy Gate Local API", "Prepared", "The project already reserves local API contracts for an opt-in service bound to this PC.", "View roadmap", self._not_ready),
                ("Watched folders", "Planned", "Protect approved files placed in a local folder without a mandatory cloud service.", "View roadmap", self._not_ready),
            ]
        else:
            cards = [
                (
                    "ChatGPT & Claude",
                    "Remote MCP beta",
                    "Create a private HTTPS link to protected documents in this local Library. The app must remain open.",
                    "Open AI connection",
                    self._remote_mcp_setup,
                ),
                (
                    "Local MCP",
                    "Advanced",
                    "Direct desktop connection for compatible local clients. No public link or tunnel is used.",
                    "Local desktop setup",
                    self._mcp_setup,
                ),
                ("Email Automation", "Planned", "Create protected email drafts or approved delivery workflows.", "View roadmap", self._not_ready),
                ("Workflow Assistance", "AI PM LAB", "Get help designing n8n, MCP, email, or cloud workflows for your business.", "Contact AI PM LAB", self._contact),
            ]
        for index, card in enumerate(cards):
            grid.addWidget(self._card(*card), index // 2, index % 2)
        root.addLayout(grid)
        root.addStretch(1)

    def _card(self, title: str, status: str, description: str, button_text: str, callback):
        card = QFrame(objectName="ConnectionCard")
        layout = QVBoxLayout(card)
        heading = QHBoxLayout()
        heading.addWidget(QLabel(title, objectName="SectionTitle"))
        heading.addStretch(1)
        heading.addWidget(QLabel(status, objectName="ConnectionBadge"))
        layout.addLayout(heading)
        description_label = QLabel(description, objectName="Muted")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        layout.addStretch(1)
        button = QPushButton(button_text, objectName="Secondary")
        button.clicked.connect(callback)
        layout.addWidget(button)
        return card

    @staticmethod
    def _open_chatgpt() -> None:
        QDesktopServices.openUrl(QUrl("https://chatgpt.com/"))

    def _not_ready(self) -> None:
        QMessageBox.information(
            self,
            "Connection not configured",
            "This integration is visible in the product roadmap but is not enabled in this local build. "
            "Manual copy, download, library and restore remain available without a cloud connection.",
        )

    def _mcp_setup(self) -> None:
        command, _args = mcp_launch_spec()
        shared_count = len(self.library.list_mcp_documents(limit=200)) if self.library else 0
        dialog = QDialog(self)
        dialog.setWindowTitle("Local MCP setup")
        dialog.resize(720, 520)
        layout = QVBoxLayout(dialog)
        heading = QLabel("AI PM LAB Privacy Gate MCP", objectName="PageTitle")
        layout.addWidget(heading)
        explanation = QLabel(
            f"Server: {command}\nShared protected documents: {shared_count}\n\n"
            "The server starts only when a compatible desktop client launches it. It is local, "
            "read-only and exposes only protected documents marked ‘Available to AI’ in the Library.\n\n"
            "Paste this configuration into a desktop client that supports local stdio MCP. "
            "A cloud-only client requires a separate authenticated remote bridge.",
            objectName="Muted",
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        config = QPlainTextEdit()
        config.setReadOnly(True)
        config.setPlainText(client_config_json())
        layout.addWidget(config, 1)
        buttons = QHBoxLayout()
        copy_button = QPushButton("Copy configuration", objectName="Primary")
        close_button = QPushButton("Close", objectName="Secondary")
        copy_button.clicked.connect(lambda: QApplication.clipboard().setText(config.toPlainText()))
        close_button.clicked.connect(dialog.accept)
        buttons.addWidget(copy_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        dialog.exec()

    def _remote_mcp_setup(self) -> None:
        if self.remote_mcp is None:
            QMessageBox.critical(self, "Remote MCP unavailable", "The remote MCP manager is unavailable.")
            return
        identity = self.remote_mcp.identity_store.load_or_create()
        dialog = QDialog(self)
        dialog.setWindowTitle("ChatGPT & Claude connection")
        dialog.resize(780, 540)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Connect Privacy Gate to AI", objectName="PageTitle"))

        explanation = QLabel(
            "Privacy Gate creates an outbound-only encrypted HTTPS link. ChatGPT or Claude can read only "
            "protected Library copies marked Available to AI. Original files and restore mappings are never "
            "included. Keep Privacy Gate open while using the connection.",
            objectName="Muted",
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        identity_label = QLabel(
            f"Connection ID: {identity.short_id}  •  Device: {identity.display_name}  •  "
            f"Protected documents available: {len(self.library.list_mcp_documents(limit=200)) if self.library else 0}"
        )
        layout.addWidget(identity_label)

        self._remote_status_label = QLabel("OFFLINE", objectName="ConnectionBadge")
        layout.addWidget(self._remote_status_label)
        self._remote_url = QLineEdit()
        self._remote_url.setReadOnly(True)
        self._remote_url.setPlaceholderText("Start the secure link to generate the MCP URL")
        layout.addWidget(self._remote_url)

        steps = QLabel(
            "1. Start the secure link.\n"
            "2. Copy the complete URL shown above.\n"
            "3. In ChatGPT Developer mode or Claude Custom Connectors, add a remote MCP server and paste it.\n"
            "4. Approve tool access in the AI client. You can block individual documents from the Library."
        )
        steps.setWordWrap(True)
        layout.addWidget(steps)

        actions = QHBoxLayout()
        start_button = QPushButton("Start secure link", objectName="Primary")
        stop_button = QPushButton("Stop", objectName="Secondary")
        copy_button = QPushButton("Copy MCP link", objectName="Secondary")
        rotate_button = QPushButton("Regenerate private code", objectName="Danger")
        actions.addWidget(start_button)
        actions.addWidget(stop_button)
        actions.addWidget(copy_button)
        actions.addStretch(1)
        actions.addWidget(rotate_button)
        layout.addLayout(actions)

        destinations = QHBoxLayout()
        chatgpt_button = QPushButton("Open ChatGPT", objectName="Secondary")
        claude_button = QPushButton("Open Claude", objectName="Secondary")
        close_button = QPushButton("Close", objectName="Secondary")
        destinations.addWidget(chatgpt_button)
        destinations.addWidget(claude_button)
        destinations.addStretch(1)
        destinations.addWidget(close_button)
        layout.addLayout(destinations)

        note = QLabel(
            "Free beta note: the encrypted tunnel address is session-based and may change after Privacy Gate "
            "fully stops. The private connection code and Library survive application updates. Do not publish "
            "or share the complete MCP URL.",
            objectName="Muted",
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        def start_connection() -> None:
            self.remote_mcp.identity_store.set_remote_enabled(True)
            self.remote_mcp.start()

        def stop_connection() -> None:
            self.remote_mcp.identity_store.set_remote_enabled(False)
            self.remote_mcp.stop()

        def rotate_connection() -> None:
            answer = QMessageBox.question(
                dialog,
                "Regenerate private connection code",
                "Existing ChatGPT and Claude connections will stop working and must be added again. Continue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            was_enabled = self.remote_mcp.identity_store.is_remote_enabled()
            self.remote_mcp.stop()
            self.remote_mcp.identity_store.rotate_access_secret()
            if was_enabled:
                self.remote_mcp.start()

        def refresh_status() -> None:
            status = self.remote_mcp.status
            labels = {
                "stopped": "OFFLINE",
                "starting": "CREATING SECURE LINK…",
                "online": "ONLINE — PROTECTED DOCUMENTS ONLY",
                "error": "CONNECTION ERROR",
            }
            self._remote_status_label.setText(labels.get(status.state, status.state.upper()))
            self._remote_url.setText(status.public_url)
            if status.error:
                self._remote_url.setText(status.error)
            copy_button.setEnabled(bool(status.public_url))
            stop_button.setEnabled(status.state in {"starting", "online", "error"})
            start_button.setEnabled(status.state not in {"starting", "online"})

        start_button.clicked.connect(start_connection)
        stop_button.clicked.connect(stop_connection)
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.remote_mcp.status.public_url)
        )
        rotate_button.clicked.connect(rotate_connection)
        chatgpt_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://chatgpt.com/")))
        claude_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://claude.ai/")))
        close_button.clicked.connect(dialog.accept)

        timer = QTimer(dialog)
        timer.timeout.connect(refresh_status)
        timer.start(350)
        refresh_status()
        dialog.exec()

    @staticmethod
    def _contact() -> None:
        QDesktopServices.openUrl(
            QUrl("mailto:peter@propertydex.xyz?subject=AI%20PM%20LAB%20Privacy%20Gate%20automation")
        )
