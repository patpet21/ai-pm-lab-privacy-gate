from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget


class ConnectionsPage(QWidget):
    def __init__(self, section: str = "local") -> None:
        super().__init__()
        self.section = section
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
                ("ChatGPT & MCP", "Planned", "Allow an approved AI client to retrieve protected documents from the local library.", "View roadmap", self._not_ready),
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

    @staticmethod
    def _contact() -> None:
        QDesktopServices.openUrl(
            QUrl("mailto:peter@propertydex.xyz?subject=AI%20PM%20LAB%20Privacy%20Gate%20automation")
        )
