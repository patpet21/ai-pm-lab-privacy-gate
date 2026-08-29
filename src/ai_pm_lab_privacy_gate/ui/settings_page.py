from __future__ import annotations

from dataclasses import replace
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
GREEN = "#23824B"
RED = "#B54747"


class SettingsPage(QWidget):
    preferences_changed = Signal()
    local_api_preferences_changed = Signal()

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

        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        header_row.addWidget(
            self._card_header(
                "Local Privacy Bridge",
                "Protect text locally for browser and approved automation integrations before it leaves this device.",
                "protect",
            ),
            1,
        )
        self.local_api_state_badge = QLabel("OFF")
        self.local_api_state_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.local_api_state_badge.setStyleSheet(
            "background:#EEF3F7;color:#062B4F;border:1px solid #D8E2E9;border-radius:9px;"
            "padding:5px 9px;font-size:8px;font-weight:900;letter-spacing:.4px;"
        )
        header_row.addWidget(self.local_api_state_badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)

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
        self.local_api_check_button = QPushButton("Check port")
        self.local_api_check_button.setIcon(icon("check", color=NAVY, size=16))
        self.local_api_check_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.local_api_check_button.setStyleSheet(
            "QPushButton{background:white;color:#17384E;border:1px solid #C9D7E0;border-radius:9px;"
            "padding:8px 12px;font-weight:750;}QPushButton:hover{background:#F2FAFA;border-color:#95C8CC;}"
        )
        self.local_api_check_button.clicked.connect(self._check_local_api_port)
        row.addWidget(port_label)
        row.addWidget(self.local_api_port_input)
        row.addWidget(self.local_api_check_button)
        row.addStretch(1)
        layout.addLayout(row)

        self.local_api_port_status = QLabel("")
        self.local_api_port_status.setWordWrap(True)
        self.local_api_port_status.setStyleSheet(f"color:{MUTED};font-size:8px;")
        layout.addWidget(self.local_api_port_status)

        self.local_api_status = QLabel("")
        self.local_api_status.setWordWrap(True)
        layout.addWidget(self.local_api_status)

        note = QLabel(
            "Local-only boundary: 127.0.0.1 • browser-session mappings stay in memory • "
            "mappings are cleared when PrivacyGate quits."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "background:#F1FAFA;color:#31576A;border:1px solid #D5ECEC;border-radius:10px;"
            "padding:8px 9px;font-size:8px;font-weight:700;"
        )
        layout.addWidget(note)
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
        enabled = self.local_api_enabled.isChecked()
        self.local_api_port_input.setEnabled(enabled)
        self.local_api_check_button.setEnabled(enabled)
        if not enabled:
            self.local_api_port_status.clear()

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

    def _check_local_api_port(self) -> None:
        port = self._local_api_port_value()
        if port is None:
            self.local_api_port_status.setText("Enter a port between 1024 and 65535.")
            self.local_api_port_status.setStyleSheet(f"color:{RED};font-size:8px;font-weight:750;")
            return
        status = self.local_api_manager.status if self.local_api_manager is not None else None
        if status is not None and status.state == "online" and int(status.port or -1) == int(port):
            self.local_api_port_status.setText(f"Port {port} is currently used by your Local Privacy Bridge ✓")
            self.local_api_port_status.setStyleSheet(f"color:{GREEN};font-size:8px;font-weight:750;")
            return
        if is_port_available(port):
            self.local_api_port_status.setText(f"Port {port} is available ✓")
            self.local_api_port_status.setStyleSheet(f"color:{GREEN};font-size:8px;font-weight:750;")
        else:
            self.local_api_port_status.setText(f"Port {port} is already in use.")
            self.local_api_port_status.setStyleSheet(f"color:{RED};font-size:8px;font-weight:750;")

    def _set_local_api_badge(self, text: str, *, tone: str = "navy") -> None:
        palette = {
            "navy": ("#EEF3F7", NAVY, "#D8E2E9"),
            "green": ("#EAF8F1", GREEN, "#CDE8D9"),
            "red": ("#FDEEEE", RED, "#F0CCCC"),
        }
        background, foreground, border = palette.get(tone, palette["navy"])
        self.local_api_state_badge.setText(text)
        self.local_api_state_badge.setStyleSheet(
            f"background:{background};color:{foreground};border:1px solid {border};border-radius:9px;"
            "padding:5px 9px;font-size:8px;font-weight:900;letter-spacing:.4px;"
        )

    def refresh_local_api_status(self) -> None:
        if self.local_api_manager is None:
            if self.local_api_enabled.isChecked():
                text = "Saved locally. The bridge starts with PrivacyGate after this setting is applied."
                color = MUTED
                self._set_local_api_badge("SAVED")
            else:
                text = "Status: Off"
                color = MUTED
                self._set_local_api_badge("OFF")
        else:
            status = self.local_api_manager.status
            if status.state == "online":
                text = f"Status: Running locally on 127.0.0.1:{status.port} ✓"
                color = GREEN
                self._set_local_api_badge("RUNNING", tone="green")
            elif status.state == "error":
                text = f"Status: Could not start on this device — {status.error}"
                color = RED
                self._set_local_api_badge("ERROR", tone="red")
            else:
                text = "Status: Off"
                color = MUTED
                self._set_local_api_badge("OFF")
        self.local_api_status.setText(text)
        self.local_api_status.setStyleSheet(f"color:{color};font-size:8px;font-weight:750;")

    def _save(self) -> None:
        """Persist only the preference groups that actually changed.

        The redesigned Settings UI has separate Device, Services and Quick Settings
        save actions. They intentionally share this one persistence path, but an
        unrelated save must never validate, restart or mention another service.
        """
        current = self.store.load()

        close_behavior = next(value for value, radio in self.close_radios.items() if radio.isChecked())
        device_changed = close_behavior != current.close_behavior

        port_mode = "automatic" if self.auto_port.isChecked() else "manual"
        raw_port = self.port_input.text().strip()
        port = self._port_value()
        if port_mode == "automatic":
            port = current.manual_port
            mcp_changed = port_mode != current.port_mode
        else:
            invalid_manual_changed = port is None and raw_port != str(current.manual_port)
            valid_manual_changed = port is not None and int(port) != int(current.manual_port)
            mcp_changed = port_mode != current.port_mode or invalid_manual_changed or valid_manual_changed

        local_api_enabled = self.local_api_enabled.isChecked()
        raw_local_api_port = self.local_api_port_input.text().strip()
        parsed_local_api_port = self._local_api_port_value()
        local_api_port = (
            int(parsed_local_api_port)
            if parsed_local_api_port is not None
            else int(current.local_api_port)
        )
        bridge_enabled_changed = local_api_enabled != current.local_api_enabled
        bridge_port_text_changed = raw_local_api_port != str(current.local_api_port)
        bridge_port_changed = (
            parsed_local_api_port is not None
            and int(parsed_local_api_port) != int(current.local_api_port)
        )
        bridge_changed = (
            bridge_enabled_changed
            or bridge_port_changed
            or (local_api_enabled and bridge_port_text_changed)
        )

        # Validate only the service whose controls changed. This prevents a Device
        # save from showing MCP/Bridge port warnings and prevents Quick Settings from
        # validating untouched Local Privacy Bridge controls.
        if mcp_changed and port_mode == "manual":
            if port is None:
                QMessageBox.warning(self, "Invalid MCP port", "Enter an MCP port between 1024 and 65535.")
                return
            if local_api_enabled and int(port) == int(local_api_port):
                QMessageBox.warning(
                    self,
                    "Port conflict",
                    "Local MCP and Local Privacy Bridge must use different ports.",
                )
                return
            if not is_port_available(int(port)):
                QMessageBox.warning(
                    self,
                    "MCP port unavailable",
                    f"Port {port} is already in use. Choose another MCP port.",
                )
                return

        if bridge_changed:
            if local_api_enabled and parsed_local_api_port is None:
                QMessageBox.warning(
                    self,
                    "Invalid bridge port",
                    "Enter a Local Privacy Bridge port between 1024 and 65535.",
                )
                return
            effective_mcp_port = int(port) if port_mode == "manual" and port is not None else int(current.manual_port)
            if local_api_enabled and port_mode == "manual" and effective_mcp_port == int(local_api_port):
                QMessageBox.warning(
                    self,
                    "Port conflict",
                    "Local MCP and Local Privacy Bridge must use different ports.",
                )
                return

        if not device_changed and not mcp_changed and not bridge_changed:
            QMessageBox.information(self, "No changes", "There are no unsaved settings changes.")
            return

        updated: AppPreferences = current
        if device_changed:
            updated = replace(updated, close_behavior=close_behavior)
        if mcp_changed:
            updated = replace(
                updated,
                port_mode=port_mode,
                manual_port=int(port) if port is not None else int(current.manual_port),
            )
        if bridge_changed:
            updated = replace(
                updated,
                local_api_enabled=local_api_enabled,
                local_api_port=int(local_api_port),
            )

        self.prefs = updated
        self.store.save(updated)
        self.preferences_changed.emit()
        if bridge_changed:
            self.local_api_preferences_changed.emit()
            self.refresh_local_api_status()

        service_changed = mcp_changed or bridge_changed
        if device_changed and not service_changed:
            title = "Device settings saved"
            message = "Desktop behavior saved locally on this device."
        elif service_changed and not device_changed:
            title = "Service settings saved"
            if bridge_changed and mcp_changed:
                message = (
                    "Service settings saved locally. Local Privacy Bridge changes apply immediately; "
                    "MCP port changes take effect the next time the MCP service starts."
                )
            elif bridge_changed:
                message = "Local Privacy Bridge settings saved locally and applied immediately."
            else:
                message = "Local MCP settings saved locally. Port changes take effect the next time the MCP service starts."
        else:
            title = "Quick settings saved"
            message = "Desktop and MCP quick settings saved locally. MCP changes take effect the next time the MCP service starts."
        QMessageBox.information(self, title, message)
