from __future__ import annotations

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.mcp.config import client_config_json, mcp_launch_spec
from ai_pm_lab_privacy_gate.infrastructure.mcp.modes import ConnectionMode
from ai_pm_lab_privacy_gate.infrastructure.mcp.provisioning_client import ProvisioningHttpClient
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
    def _info_button(parent: QWidget, title: str, explanation: str) -> QToolButton:
        button = QToolButton(parent)
        button.setObjectName("InfoButton")
        button.setText("i")
        button.setToolTip(explanation)
        button.setAccessibleName(f"Information about {title}")
        button.clicked.connect(
            lambda _checked=False: QMessageBox.information(parent, title, explanation)
        )
        return button

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
        dialog.resize(920, 740)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Connect Privacy Gate to AI", objectName="PageTitle"))

        explanation = QLabel(
            "Remote access is optional. Temporary DEV mode creates a session URL for testing. Stable PROD "
            "mode uses this installation's Named Tunnel and automatic browser authorization. In both modes, the MCP "
            "process reads only the physically separate Protected Library; originals and restore mappings "
            "are not present there.",
            objectName="Muted",
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        identity_label = QLabel(
            f"Connection ID: {identity.short_id}  •  Device: {identity.display_name}  •  "
            f"Protected documents available: {len(self.library.list_mcp_documents(limit=200)) if self.library else 0}"
        )
        layout.addWidget(identity_label)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Connection mode"))
        mode_row.addWidget(
            self._info_button(
                dialog,
                "Connection mode",
                "PROD provides one stable address for this installation. DEV creates a temporary "
                "testing address that changes when it restarts.",
            )
        )
        mode_selector = QComboBox()
        mode_selector.addItem("DEV — temporary Quick Tunnel", ConnectionMode.DEV_QUICK.value)
        production_configuration = self.remote_mcp.provisioning_store.load()
        production_label = (
            "PROD — stable Named Tunnel"
            if production_configuration
            else "PROD — stable Named Tunnel (not provisioned)"
        )
        mode_selector.addItem(production_label, ConnectionMode.PROD_NAMED.value)
        selected_mode = self.remote_mcp.identity_store.connection_mode()
        selected_index = mode_selector.findData(selected_mode.value)
        mode_selector.setCurrentIndex(max(0, selected_index))
        mode_row.addWidget(mode_selector, 1)
        layout.addLayout(mode_row)

        provisioning_client = ProvisioningHttpClient(self.remote_mcp.identity_store)
        provisioning_actions = QHBoxLayout()
        provision_button = QPushButton("Activate stable connection", objectName="Secondary")
        check_activation_button = QPushButton("Check activation", objectName="Secondary")
        provisioning_actions.addWidget(provision_button)
        provision_info = self._info_button(
            dialog,
            "Activate stable connection",
            "One-time setup that assigns this installation its permanent propertydex.xyz MCP address. "
            "It is not required again after activation.",
        )
        provisioning_actions.addWidget(provision_info)
        provisioning_actions.addWidget(check_activation_button)
        check_activation_info = self._info_button(
            dialog,
            "Check activation",
            "After approving the device in your browser, this retrieves and securely stores its "
            "device-specific tunnel credential.",
        )
        provisioning_actions.addWidget(check_activation_info)
        provisioning_actions.addStretch(1)
        layout.addLayout(provisioning_actions)
        provision_button.setVisible(production_configuration is None)
        check_activation_button.setVisible(production_configuration is None)
        provision_info.setVisible(production_configuration is None)
        check_activation_info.setVisible(production_configuration is None)

        self._remote_status_label = QLabel("OFFLINE", objectName="ConnectionBadge")
        status_row = QHBoxLayout()
        status_row.addWidget(self._remote_status_label, 1)
        status_row.addWidget(
            self._info_button(
                dialog,
                "Connection status",
                "Online means an authorized AI client can reach protected Library content while this "
                "computer and Privacy Gate are running. Offline does not change or delete the stable URL.",
            )
        )
        layout.addLayout(status_row)
        self._remote_url = QLineEdit()
        self._remote_url.setReadOnly(True)
        self._remote_url.setPlaceholderText("Activate PROD or start DEV to create an MCP URL")
        self._remote_url.setToolTip("Select the address or use Copy. The PROD address remains the same after restarts and updates.")
        url_copy_button = QPushButton("Copy", objectName="Secondary")
        url_copy_button.setToolTip("Copy the complete MCP address to the clipboard")
        copy_feedback = QLabel("", objectName="CopyFeedback")
        url_row = QHBoxLayout()
        url_row.addWidget(self._remote_url, 1)
        url_row.addWidget(url_copy_button)
        url_row.addWidget(copy_feedback)
        layout.addLayout(url_row)

        steps = QLabel(
            "DEV: start a temporary link and paste it into a test client.\n"
            "PROD: copy the stable URL into ChatGPT or Claude and select OAuth. Your browser opens the "
            "Privacy Gate authorization page automatically—no code needs to be entered. The stable hostname "
            "and device identity survive app updates."
        )
        steps.setWordWrap(True)
        layout.addWidget(steps)

        actions = QHBoxLayout()
        start_button = QPushButton("Bring MCP online", objectName="Primary")
        stop_button = QPushButton("Take MCP offline", objectName="Secondary")
        copy_button = QPushButton("Copy MCP link", objectName="Secondary")
        rotate_button = QPushButton("Reset connection security", objectName="Danger")
        revoke_button = QPushButton("Disconnect this device", objectName="Danger")
        actions.addWidget(start_button)
        actions.addWidget(
            self._info_button(
                dialog,
                "Bring MCP online",
                "Starts the local read-only MCP service and its secure outbound tunnel. No router ports are opened.",
            )
        )
        actions.addWidget(stop_button)
        actions.addWidget(
            self._info_button(
                dialog,
                "Take MCP offline",
                "Stops remote access without changing the stable address, deleting documents or revoking pairings.",
            )
        )
        actions.addWidget(copy_button)
        actions.addWidget(
            self._info_button(
                dialog,
                "Copy MCP link",
                "Copies the complete MCP address used when configuring ChatGPT, Claude or another compatible client.",
            )
        )
        actions.addStretch(1)
        layout.addLayout(actions)

        advanced_actions = QHBoxLayout()
        advanced_actions.addStretch(1)
        advanced_actions.addWidget(rotate_button)
        advanced_actions.addWidget(
            self._info_button(
                dialog,
                "Reset connection security",
                "Replaces the private tunnel credential while keeping the same stable address. Use only if compromise is suspected.",
            )
        )
        advanced_actions.addWidget(revoke_button)
        advanced_actions.addWidget(
            self._info_button(
                dialog,
                "Disconnect this device",
                "Revokes this installation's stable hostname and remote credentials. Local protection and Library data remain untouched.",
            )
        )
        layout.addLayout(advanced_actions)

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
            "DEV addresses are temporary. PROD uses a stable first-level propertydex.xyz hostname and never "
            "falls back to DEV automatically. Only TLS-protected, already-de-identified Library content may "
            "cross the tunnel.",
            objectName="Muted",
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        def start_connection() -> None:
            mode = ConnectionMode(str(mode_selector.currentData()))
            if mode is ConnectionMode.PROD_NAMED and production_configuration is None:
                QMessageBox.information(
                    dialog,
                    "Stable connection not provisioned",
                    "This installation is ready for production provisioning, but it does not yet have a "
                    "Named Tunnel credential. DEV Quick Tunnel remains available for testing.",
                )
                return
            self.remote_mcp.identity_store.set_connection(enabled=True, mode=mode)
            self.remote_mcp.start(mode)

        def begin_provisioning() -> None:
            try:
                enrollment = provisioning_client.start_enrollment()
            except Exception as error:
                QMessageBox.critical(dialog, "Activation unavailable", str(error))
                return
            QDesktopServices.openUrl(QUrl(enrollment.activation_url))
            QMessageBox.information(
                dialog,
                "Activation opened",
                "Approve this installation in the browser, then return here and select Check activation.",
            )

        def check_activation() -> None:
            nonlocal production_configuration
            try:
                state = provisioning_client.poll_enrollment()
            except Exception as error:
                QMessageBox.critical(dialog, "Activation check failed", str(error))
                return
            if state != "ready":
                QMessageBox.information(dialog, "Activation status", f"Current state: {state}")
                return
            production_configuration = self.remote_mcp.provisioning_store.load()
            mode_selector.setItemText(1, "PROD — stable Named Tunnel")
            mode_selector.setCurrentIndex(1)
            provision_button.hide()
            check_activation_button.hide()
            provision_info.hide()
            check_activation_info.hide()
            self.remote_mcp.identity_store.set_connection(
                enabled=False, mode=ConnectionMode.PROD_NAMED
            )
            QMessageBox.information(
                dialog,
                "Stable connection ready",
                f"Hostname: {production_configuration.hostname if production_configuration else ''}\n"
                "The tunnel credential is stored in this operating system's secure credential storage.",
            )

        def stop_connection() -> None:
            self.remote_mcp.identity_store.set_remote_enabled(False)
            self.remote_mcp.stop()

        def rotate_connection() -> None:
            nonlocal production_configuration
            mode = ConnectionMode(str(mode_selector.currentData()))
            if mode is ConnectionMode.PROD_NAMED:
                answer = QMessageBox.question(
                    dialog,
                    "Rotate stable credential",
                    "The current tunnel credential will stop working and the protected connection will "
                    "restart with a new credential. The stable hostname will remain the same. Continue?",
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                self.remote_mcp.stop()
                try:
                    production_configuration = provisioning_client.rotate_production_credential()
                except Exception as error:
                    QMessageBox.critical(dialog, "Rotation failed", str(error))
                    return
                QMessageBox.information(
                    dialog,
                    "Credential rotated",
                    "The replacement credential is stored in the Windows user vault. Start the stable "
                    "connection again when ready.",
                )
                return
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
                self.remote_mcp.start(ConnectionMode.DEV_QUICK)

        def revoke_production_device() -> None:
            nonlocal production_configuration
            if production_configuration is None:
                QMessageBox.information(dialog, "No stable device", "This installation is not provisioned.")
                return
            answer = QMessageBox.question(
                dialog,
                "Remove stable device",
                "This revokes the public hostname, tunnel credential and pending AI pairings for this PC. "
                "Local protection, restoration and Library documents remain untouched. Continue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            confirmation, accepted = QInputDialog.getText(
                dialog,
                "Confirm device disconnection",
                f"Type {identity.short_id} to confirm permanent disconnection:",
            )
            if not accepted or confirmation.strip().upper() != identity.short_id:
                QMessageBox.information(
                    dialog,
                    "Disconnection cancelled",
                    "The confirmation ID did not match. No connection or credential was changed.",
                )
                return
            self.remote_mcp.stop()
            try:
                provisioning_client.revoke_production_device()
            except Exception as error:
                QMessageBox.critical(dialog, "Removal failed", str(error))
                return
            production_configuration = None
            mode_selector.setItemText(1, "PROD — stable Named Tunnel (not provisioned)")
            mode_selector.setCurrentIndex(0)
            self.remote_mcp.identity_store.set_connection(enabled=False, mode=ConnectionMode.DEV_QUICK)
            provision_button.show()
            check_activation_button.show()
            provision_info.show()
            check_activation_info.show()
            revoke_button.hide()
            rotate_button.hide()
            QMessageBox.information(
                dialog,
                "Stable device removed",
                "Cloud resources and credentials were revoked. Your local Library was not deleted.",
            )

        def copy_mcp_url() -> None:
            url = self._remote_url.text().strip()
            if not url or not url.startswith("https://"):
                return
            QApplication.clipboard().setText(url)
            copy_feedback.setText("Copied ✓")
            url_copy_button.setText("Copied ✓")
            copy_button.setText("Copied ✓")

            def reset_copy_feedback() -> None:
                copy_feedback.clear()
                url_copy_button.setText("Copy")
                copy_button.setText("Copy MCP link")

            QTimer.singleShot(1800, reset_copy_feedback)

        def refresh_status() -> None:
            status = self.remote_mcp.status
            labels = {
                "stopped": "OFFLINE",
                "starting": "CREATING SECURE LINK…",
                "online": "ONLINE — STABLE ADDRESS — PROTECTED DOCUMENTS ONLY",
                "error": "CONNECTION ERROR",
            }
            self._remote_status_label.setText(labels.get(status.state, status.state.upper()))
            stable_url = production_configuration.mcp_url if production_configuration else ""
            display_url = status.public_url or stable_url
            self._remote_url.setText(display_url)
            self._remote_url.setCursorPosition(0)
            if status.error:
                copy_feedback.setText(status.error)
            copy_button.setEnabled(bool(display_url))
            url_copy_button.setEnabled(bool(display_url))
            stop_button.setEnabled(status.state in {"starting", "online", "error"})
            start_button.setEnabled(status.state not in {"starting", "online"})
            mode_selector.setEnabled(status.state not in {"starting", "online"})

        start_button.clicked.connect(start_connection)
        provision_button.clicked.connect(begin_provisioning)
        check_activation_button.clicked.connect(check_activation)
        stop_button.clicked.connect(stop_connection)
        copy_button.clicked.connect(copy_mcp_url)
        url_copy_button.clicked.connect(copy_mcp_url)
        rotate_button.clicked.connect(rotate_connection)
        revoke_button.clicked.connect(revoke_production_device)
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
