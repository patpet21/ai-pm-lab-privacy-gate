from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
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


class SettingsPage(QWidget):
    preferences_changed = Signal()

    def __init__(self, data_dir) -> None:
        super().__init__()
        self.store = PreferencesStore(data_dir)
        self.prefs = self.store.load()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        root.addWidget(QLabel("Settings", objectName="PageTitle"))

        close_card = QFrame(objectName="Card")
        close_layout = QVBoxLayout(close_card)
        close_layout.addWidget(QLabel("When I close PrivacyGate", objectName="SectionTitle"))
        close_note = QLabel(
            "Choose what the X button should do. Your protected Library and mappings are stored locally and are not deleted when PrivacyGate closes.",
            objectName="Muted",
        )
        close_note.setWordWrap(True)
        close_layout.addWidget(close_note)
        self.close_group = QButtonGroup(self)
        self.close_radios = {}
        for value, label in (
            ("ask", "Ask me every time"),
            ("background", "Keep running in background"),
            ("quit", "Quit PrivacyGate"),
        ):
            radio = QRadioButton(label)
            radio.setChecked(self.prefs.close_behavior == value)
            self.close_group.addButton(radio)
            self.close_radios[value] = radio
            close_layout.addWidget(radio)
        root.addWidget(close_card)

        port_card = QFrame(objectName="Card")
        port_layout = QVBoxLayout(port_card)
        port_layout.addWidget(QLabel("Local MCP service", objectName="SectionTitle"))
        port_note = QLabel(
            "Automatic mode is recommended. PrivacyGate will choose an available local port. Use Manual only when another integration requires a fixed port.",
            objectName="Muted",
        )
        port_note.setWordWrap(True)
        port_layout.addWidget(port_note)
        self.auto_port = QRadioButton("Automatic (recommended)")
        self.manual_port = QRadioButton("Manual")
        self.auto_port.setChecked(self.prefs.port_mode == "automatic")
        self.manual_port.setChecked(self.prefs.port_mode == "manual")
        self.port_group = QButtonGroup(self)
        self.port_group.addButton(self.auto_port)
        self.port_group.addButton(self.manual_port)
        port_layout.addWidget(self.auto_port)
        port_layout.addWidget(self.manual_port)

        port_row = QHBoxLayout()
        self.port_input = QLineEdit(str(self.prefs.manual_port))
        self.port_input.setPlaceholderText("8766")
        self.port_input.setMaximumWidth(160)
        self.check_button = QPushButton("Check availability", objectName="Secondary")
        self.check_button.clicked.connect(self._check_port)
        port_row.addWidget(QLabel("Port"))
        port_row.addWidget(self.port_input)
        port_row.addWidget(self.check_button)
        port_row.addStretch(1)
        port_layout.addLayout(port_row)
        self.port_status = QLabel("", objectName="Muted")
        port_layout.addWidget(self.port_status)
        self.auto_port.toggled.connect(self._sync_port_controls)
        self._sync_port_controls()
        root.addWidget(port_card)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save = QPushButton("Save settings", objectName="Primary")
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        root.addLayout(buttons)
        root.addStretch(1)

    def _sync_port_controls(self) -> None:
        enabled = self.manual_port.isChecked()
        self.port_input.setEnabled(enabled)
        self.check_button.setEnabled(enabled)
        if not enabled:
            self.port_status.setText("PrivacyGate will select a free port automatically at service startup.")

    def _port_value(self) -> int | None:
        try:
            value = int(self.port_input.text().strip())
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
        else:
            self.port_status.setText(f"Port {port} is already in use.")

    def _save(self) -> None:
        close_behavior = next(
            value for value, radio in self.close_radios.items() if radio.isChecked()
        )
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
        self.prefs = AppPreferences(
            close_behavior=close_behavior,
            port_mode=port_mode,
            manual_port=int(port),
        )
        self.store.save(self.prefs)
        self.preferences_changed.emit()
        QMessageBox.information(
            self,
            "Settings saved",
            "Settings saved locally. MCP port changes take effect the next time the MCP service starts.",
        )
