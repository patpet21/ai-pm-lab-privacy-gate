from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.mcp.config import client_config_json, mcp_launch_spec
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository


class ConnectionsPage(QWidget):
    def __init__(self, section: str = "local", library: LibraryRepository | None = None) -> None:
        super().__init__()
        self.section = section
        self.library = library
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
                ("Cloud AI", "Optional", "Connect an LLM with the customer’s own account or API key.", "Not configured", self._not_ready),
                (
                    "Local MCP",
                    "Ready",
                    "Read-only access to protected documents you explicitly share. No original PII or restore mappings.",
                    "MCP setup",
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
            "read-only and exposes only documents marked ‘Share with MCP’ in the Library.\n\n"
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

    @staticmethod
    def _contact() -> None:
        QDesktopServices.openUrl(
            QUrl("mailto:peter@propertydex.xyz?subject=AI%20PM%20LAB%20Privacy%20Gate%20automation")
        )
