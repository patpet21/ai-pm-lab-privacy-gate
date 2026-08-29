from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.settings.preferences import (
    AppPreferences,
    PreferencesStore,
    is_port_available,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon

if TYPE_CHECKING:
    from ai_pm_lab_privacy_gate.infrastructure.local_api.manager import LocalApiManager

NAVY = "#062B4F"
TEAL = "#0B7F89"
MUTED = "#61798A"
BORDER = "#DCE5EA"
BG = "#F7FAFC"
WHITE = "#FFFFFF"


class SettingsPage(QWidget):
    preferences_changed = Signal()

    def __init__(self, data_dir, local_api_manager: LocalApiManager | None = None) -> None:
        super().__init__()
        self.store = PreferencesStore(data_dir)
        self.prefs = self.store.load()
        self.local_api_manager = local_api_manager
        self.setObjectName("PremiumSettingsPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title = QLabel("Settings")
        title.setStyleSheet(f"color:{NAVY};font-size:28px;font-weight:900;")
        subtitle = QLabel("Account, desktop behavior and local PrivacyGate services.")
        subtitle.setStyleSheet(f"color:{MUTED};font-size:12px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        root.addLayout(header)

        # PlanAccountPanel is inserted here by organization_polish at index 1.

        body = QHBoxLayout()
        body.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(16)
        left.addWidget(self._build_close_card())
        left.addWidget(self._build_local_api_card())
        left.addWidget(self._build_privacy_card())
        left.addStretch(1)
        body.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(16)
        right.addWidget(self._build_mcp_card())
        right.addWidget(self._build_updates_card())
        right.addStretch(1)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        save = QPushButton("Save settings")
        save.setIcon(icon("save", color=WHITE, size=18))
        save.setObjectName("SettingsPrimary")
        save.setMinimumHeight(42)
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setStyleSheet(
            "QPushButton#SettingsPrimary{background:#0B7F89;color:white;border:none;border-radius:10px;"
            "padding:10px 18px;font-size:11px;font-weight:800;}"
            "QPushButton#SettingsPrimary:hover{background:#096D76;}"
        )
        save.clicked.connect(self._save)
        actions.addWidget(save)
        root.addLayout(actions)

        self.setStyleSheet(
            "QWidget#PremiumSettingsPage{background:#F7FAFC;}"
            "QWidget#PremiumSettingsPage QLabel{background:transparent;border:none;}"
            "QRadioButton,QCheckBox{color:#17384E;font-size:10px;font-weight:700;padding:7px 4px;spacing:9px;}"
            "QRadioButton::indicator{width:18px;height:18px;border-radius:9px;border:2px solid #91A9B9;background:white;}"
            "QRadioButton::indicator:checked{border:6px solid #0B7F89;background:white;}"
            "QLineEdit{background:white;color:#17384E;border:1px solid #C9D7E0;border-radius:9px;padding:9px 10px;}"
        )
        self.refresh_local_api_status()

    def _card(self) -> QFrame:
        frame = QFrame(objectName="SettingsPremiumCard")
        frame.setStyleSheet(
            "QFrame#SettingsPremiumCard{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:16px;}"
        )
        return frame

    def _card_header(self, title: str, subtitle: str, icon_name: str) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(11)
        bubble = QLabel()
        bubble.setFixedSize(42, 42)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setPixmap(icon(icon_name, color=TEAL, size=23).pixmap(23, 23))
        bubble.setStyleSheet("background:#E8F7F7;border-radius:21px;")
        layout.addWidget(bubble)
        text = QVBoxLayout()
        text.setSpacing(2)
        heading = QLabel(title)
        heading.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:850;")
        note = QLabel(subtitle)
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};font-size:9px;")
        text.addWidget(heading)
        text.addWidget(note)
        layout.addLayout(text, 1)
        return header

    def _build_close_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(
            self._card_header(
                "Desktop behavior",
                "Choose what happens when the PrivacyGate window closes.",
                "settings",
            )
        )
        line = QFrame(); line.setFixedHeight(1); line.setStyleSheet("background:#EEF2F4;border:none;")
        layout.addWidget(line)

        self.close_group = QButtonGroup(self)
        self.close_radios: dict[str, QRadioButton] = {}
        for value, label, detail in (
            ("ask", "Ask me every time", "Choose background or quit whenever you close the app."),
            ("background", "Keep running in background", "Useful when MCP or the Local Privacy Bridge should stay available."),
            ("quit", "Quit PrivacyGate", "Stop the desktop app and its local services."),
        ):
            row = QFrame()
            row.setStyleSheet("QFrame{background:#FBFDFE;border:1px solid #EEF2F4;border-radius:10px;}")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            radio = QRadioButton(label)
            radio.setChecked(self.prefs.close_behavior == value)
            detail_label = QLabel(detail)
            detail_label.setStyleSheet(f"color:{MUTED};font-size:8px;margin-left:28px;")
            self.close_group.addButton(radio)
            self.close_radios[value] = radio
            row_layout.addWidget(radio)
            row_layout.addWidget(detail_label)
            layout.addWidget(row)
        return card

    def _build_local_api_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)
        layout.addWidget(
            self._card_header(
                "Local Privacy Bridge",
                "Local text protection for approved browser and automation integrations.",
                "protect",
            )
        )
        self.local_api_enabled = QCheckBox("Enable Local Privacy Bridge")
        self.local_api_enabled.setChecked(self.prefs.local_api_enabled)
        layout.addWidget(self.local_api_enabled)

        row = QHBoxLayout()
        row.setSpacing(8)
        port_label = QLabel("Bridge port")
        port_label.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:700;")
        self.local_api_port_input = QLineEdit(str(self.prefs.local_api_port))
        self.local_api_port_input.setPlaceholderText("8765")
        self.local_api_port_input.setMaximumWidth(120)
        row.addWidget(port_label)
        row.addWidget(self.local_api_port_input)
        row.addStretch(1)
        layout.addLayout(row)

        note = QLabel(
            "Off by default. When enabled, the bridge listens only on this device (127.0.0.1). "
            "Reversible browser-session mappings stay in memory and are cleared when PrivacyGate quits."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};font-size:8px;")
        layout.addWidget(note)
        self.local_api_status = QLabel("")
        self.local_api_status.setWordWrap(True)
        layout.addWidget(self.local_api_status)
        self.local_api_enabled.toggled.connect(self._sync_local_api_controls)
        self._sync_local_api_controls()
        return card

    def _build_mcp_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(
            self._card_header(
                "Local MCP service",
                "Automatic mode is recommended. Manual mode is only for integrations that require a fixed port.",
                "workflow",
            )
        )
        line = QFrame(); line.setFixedHeight(1); line.setStyleSheet("background:#EEF2F4;border:none;")
        layout.addWidget(line)

        self.auto_port = QRadioButton("Automatic (recommended)")
        self.manual_port = QRadioButton("Manual")
        self.auto_port.setChecked(self.prefs.port_mode == "automatic")
        self.manual_port.setChecked(self.prefs.port_mode == "manual")
        self.port_group = QButtonGroup(self)
        self.port_group.addButton(self.auto_port)
        self.port_group.addButton(self.manual_port)
        layout.addWidget(self.auto_port)
        layout.addWidget(self.manual_port)

        port_row = QHBoxLayout()
        port_row.setSpacing(8)
        label = QLabel("Port")
        label.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:700;")
        self.port_input = QLineEdit(str(self.prefs.manual_port))
        self.port_input.setPlaceholderText("8766")
        self.port_input.setMaximumWidth(150)
        self.check_button = QPushButton("Check availability")
        self.check_button.setIcon(icon("check", color=NAVY, size=17))
        self.check_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_button.setStyleSheet(
            "QPushButton{background:white;color:#17384E;border:1px solid #C9D7E0;border-radius:9px;"
            "padding:8px 12px;font-weight:750;}QPushButton:hover{background:#F2FAFA;border-color:#95C8CC;}"
        )
        self.check_button.clicked.connect(self._check_port)
        port_row.addWidget(label)
        port_row.addWidget(self.port_input)
        port_row.addWidget(self.check_button)
        port_row.addStretch(1)
        layout.addLayout(port_row)
        self.port_status = QLabel("")
        self.port_status.setWordWrap(True)
        self.port_status.setStyleSheet(f"color:{MUTED};font-size:9px;")
        layout.addWidget(self.port_status)
        self.auto_port.toggled.connect(self._sync_port_controls)
        self._sync_port_controls()
        return card

    def _build_privacy_card(self) -> QFrame:
        card = self._card()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        shield = QLabel()
        shield.setPixmap(icon("protect", color=TEAL, size=24).pixmap(24, 24))
        layout.addWidget(shield, alignment=Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        title = QLabel("Local-first privacy boundary")
        title.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:850;")
        note = QLabel(
            "Your original documents, protected files, restore mappings and connector tokens remain on this device. "
            "Organization control stores policy and account metadata only."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};font-size:9px;")
        text.addWidget(title)
        text.addWidget(note)
        layout.addLayout(text, 1)
        return card

    def _build_updates_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.addWidget(
            self._card_header(
                "Updates & release channel",
                "PrivacyGate checks for app updates through the current release workflow.",
                "download",
            )
        )
        note = QLabel("Update controls remain available from Contact / Workflows. Automatic update behavior can be expanded in a future release.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};font-size:9px;")
        layout.addWidget(note)
        return card

    def _sync_port_controls(self) -> None:
        enabled = self.manual_port.isChecked()
        self.port_input.setEnabled(enabled)
        self.check_button.setEnabled(enabled)
        if not enabled:
            self.port_status.setText("PrivacyGate will select a free local port automatically at service startup.")

    def _sync_local_api_controls(self) -> None:
        self.local_api_port_input.setEnabled(self.local_api_enabled.isChecked())

    def _port_value(self) -> int | None:
        try:
            value = int(self.port_input.text().strip())
        except ValueError:
            return None
        return value if 1024 <= value <= 65535 else None

    def _local_api_port_value(self) -> int | None:
        try:
            value = int(self.local_api_port_input.text().strip())
        except ValueError:
            return None
        return value if 1024 <= value <= 65535 else None

    def _check_port(self) -> None:
        port = self._port_value()
        if port is None:
            self.port_status.setText("Enter a port between 1024 and 65535.")
            return
        if is_port_available(port):
            self.port_status.setText(f"Port {port} is available ✓")
            self.port_status.setStyleSheet("color:#23824B;font-size:9px;font-weight:750;")
        else:
            self.port_status.setText(f"Port {port} is already in use.")
            self.port_status.setStyleSheet("color:#B54747;font-size:9px;font-weight:750;")

    def refresh_local_api_status(self) -> None:
        if self.local_api_manager is None:
            if self.local_api_enabled.isChecked():
                text = "Saved locally. The bridge starts with PrivacyGate after this setting is applied."
                color = MUTED
            else:
                text = "Status: Off"
                color = MUTED
        else:
            status = self.local_api_manager.status
            if status.state == "online":
                text = f"Status: Running locally on 127.0.0.1:{status.port} ✓"
                color = "#23824B"
            elif status.state == "error":
                text = f"Status: Could not start on this device — {status.error}"
                color = "#B54747"
            else:
                text = "Status: Off"
                color = MUTED
        self.local_api_status.setText(text)
        self.local_api_status.setStyleSheet(f"color:{color};font-size:8px;font-weight:750;")

    def _save(self) -> None:
        close_behavior = next(value for value, radio in self.close_radios.items() if radio.isChecked())
        port_mode = "automatic" if self.auto_port.isChecked() else "manual"
        port = self._port_value()
        if port_mode == "manual":
            if port is None:
                QMessageBox.warning(self, "Invalid port", "Enter a port between 1024 and 65535.")
                return
            if not is_port_available(port):
                QMessageBox.warning(self, "Port unavailable", f"Port {port} is already in use. Choose another port.")
                return
        else:
            port = self.prefs.manual_port

        local_api_enabled = self.local_api_enabled.isChecked()
        local_api_port = self._local_api_port_value()
        if local_api_enabled and local_api_port is None:
            QMessageBox.warning(
                self,
                "Invalid bridge port",
                "Enter a Local Privacy Bridge port between 1024 and 65535.",
            )
            return
        if local_api_port is None:
            local_api_port = self.prefs.local_api_port
        if local_api_enabled and port_mode == "manual" and int(port) == int(local_api_port):
            QMessageBox.warning(
                self,
                "Port conflict",
                "Local MCP and Local Privacy Bridge must use different ports.",
            )
            return

        self.prefs = AppPreferences(
            close_behavior=close_behavior,
            port_mode=port_mode,
            manual_port=int(port),
            local_api_enabled=local_api_enabled,
            local_api_port=int(local_api_port),
        )
        self.store.save(self.prefs)
        self.preferences_changed.emit()
        self.refresh_local_api_status()
        QMessageBox.information(
            self,
            "Settings saved",
            "Settings saved locally. Local Privacy Bridge changes apply immediately; MCP port changes take effect the next time the MCP service starts.",
        )
