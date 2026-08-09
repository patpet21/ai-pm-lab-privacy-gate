from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget


class ConnectionsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)
        root.addWidget(QLabel("Connections", objectName="PageTitle"))
        root.addWidget(
            QLabel("Privacy Gate works free without connections. Add automation only when your workflow needs it.", objectName="Muted")
        )
        grid = QGridLayout()
        grid.setSpacing(14)
        cards = [
            ("Manual AI", "Ready", "Copy protected content and open ChatGPT or another AI manually.", "Open ChatGPT", self._open_chatgpt),
            ("Local Automation", "Not connected", "Local API, n8n and folder-based workflows without mandatory cloud services.", "View options", self._not_ready),
            ("Cloud Automation", "Not connected", "Connect an LLM provider using the customer’s account or API key.", "Configure", self._not_ready),
            ("Email & Communication", "Not connected", "Create protected email drafts or automate approved delivery workflows.", "Configure", self._not_ready),
            ("ChatGPT & MCP", "Planned", "Let ChatGPT search and retrieve protected documents from the local library.", "Learn more", self._not_ready),
            ("Workflow Assistance", "AI PM LAB", "Request help designing n8n, MCP, email or cloud workflows.", "Contact us", self._not_ready),
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
