from __future__ import annotations

from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
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

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7180"
MUTED = "#64788A"
BORDER = "#DCE5EA"
SOFT = "#F7FAFC"
TEAL_SOFT = "#EAF7F7"


def _card() -> QFrame:
    card = QFrame(objectName="SettingsCard")
    card.setStyleSheet(
        "QFrame#SettingsCard{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:14px;}"
    )
    return card


def _section_header(title: str, subtitle: str, icon_name: str) -> QWidget:
    widget = QWidget()
    row = QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)

    icon_box = QLabel()
    icon_box.setFixedSize(42, 42)
    icon_box.setPixmap(icon(icon_name, color=TEAL, size=23).pixmap(QSize(23, 23)))
    icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_box.setStyleSheet(
        "background:#EAF7F7;border:1px solid #CBE8E8;border-radius:12px;"
    )

    text = QVBoxLayout()
    text.setSpacing(1)
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:900;border:none;background:transparent;")
    note = QLabel(subtitle)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;background:transparent;")
    text.addWidget(heading)
    text.addWidget(note)

    row.addWidget(icon_box, 0, Qt.AlignmentFlag.AlignTop)
    row.addLayout(text, 1)
    return widget


def _radio_style() -> str:
    return (
        "QRadioButton{background:#F8FAFC;color:#17384E;border:1px solid transparent;"
        "border-radius:10px;padding:11px 13px;spacing:10px;font-weight:700;}"
        "QRadioButton:hover{background:#F1F8F8;border-color:#D7E9EA;}"
        "QRadioButton:checked{background:#EAF7F7;color:#0B7180;border:1px solid #C5E5E6;font-weight:850;}"
        "QRadioButton::indicator{width:18px;height:18px;border-radius:10px;border:2px solid #91A9B8;background:white;}"
        "QRadioButton::indicator:checked{border:6px solid #0B7180;background:white;}"
    )


class SettingsPage(QWidget):
    preferences_changed = Signal()

    def __init__(self, data_dir) -> None:
        super().__init__()
        self.setObjectName("PremiumSettingsPage")
        self.store = PreferencesStore(data_dir)
        self.prefs = self.store.load()

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 22)
        root.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Settings")
        title.setObjectName("PremiumSettingsTitle")
        title.setStyleSheet(f"color:{NAVY};font-size:28px;font-weight:950;border:none;background:transparent;")
        subtitle = QLabel("Manage your PrivacyGate account, desktop behavior and local services.")
        subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;background:transparent;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        local_badge = QLabel("LOCAL-FIRST")
        local_badge.setStyleSheet(
            "background:#EAF7F7;color:#0B7180;border:1px solid #C5E5E6;"
            "border-radius:10px;padding:6px 11px;font-size:8px;font-weight:900;"
        )
        header.addWidget(local_badge, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.plan_mount = QVBoxLayout()
        self.plan_mount.setContentsMargins(0, 0, 0, 0)
        self.plan_mount.setSpacing(0)
        root.addLayout(self.plan_mount)

        content = QGridLayout()
        content.setHorizontalSpacing(14)
        content.setVerticalSpacing(14)
        content.setColumnStretch(0, 1)
        content.setColumnStretch(1, 1)

        close_card = _card()
        close_layout = QVBoxLayout(close_card)
        close_layout.setContentsMargins(18, 17, 18, 17)
        close_layout.setSpacing(10)
        close_layout.addWidget(
            _section_header(
                "Desktop behavior",
                "Choose what PrivacyGate should do when you close the desktop window.",
                "power",
            )
        )
        self.close_group = QButtonGroup(self)
        self.close_radios: dict[str, QRadioButton] = {}
        for value, label, detail in (
            ("ask", "Ask me every time", "PrivacyGate will ask before closing or staying in background."),
            ("background", "Keep running in background", "Keep MCP and permitted background connections available."),
            ("quit", "Quit PrivacyGate", "Close the app and take local MCP connections offline."),
        ):
            item = QFrame()
            item.setStyleSheet("QFrame{border:none;background:transparent;}")
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(1)
            radio = QRadioButton(label)
            radio.setStyleSheet(_radio_style())
            radio.setChecked(self.prefs.close_behavior == value)
            self.close_group.addButton(radio)
            self.close_radios[value] = radio
            detail_label = QLabel(detail)
            detail_label.setWordWrap(True)
            detail_label.setStyleSheet(f"color:{MUTED};font-size:8px;margin-left:14px;border:none;background:transparent;")
            item_layout.addWidget(radio)
            item_layout.addWidget(detail_label)
            close_layout.addWidget(item)
        content.addWidget(close_card, 0, 0)

        port_card = _card()
        port_layout = QVBoxLayout(port_card)
        port_layout.setContentsMargins(18, 17, 18, 17)
        port_layout.setSpacing(10)
        port_layout.addWidget(
            _section_header(
                "Local MCP service",
                "Automatic mode is recommended. Manual mode is only needed for integrations that require a fixed local port.",
                "workflow",
            )
        )

        self.auto_port = QRadioButton("Automatic  ·  Recommended")
        self.manual_port = QRadioButton("Manual port")
        self.auto_port.setStyleSheet(_radio_style())
        self.manual_port.setStyleSheet(_radio_style())
        self.auto_port.setChecked(self.prefs.port_mode == "automatic")
        self.manual_port.setChecked(self.prefs.port_mode == "manual")
        self.port_group = QButtonGroup(self)
        self.port_group.addButton(self.auto_port)
        self.port_group.addButton(self.manual_port)
        port_layout.addWidget(self.auto_port)
        port_layout.addWidget(self.manual_port)

        port_panel = QFrame(objectName="PortPanel")
        port_panel.setStyleSheet(
            "QFrame#PortPanel{background:#F8FAFC;border:1px solid #E1E8EC;border-radius:10px;}"
        )
        port_panel_layout = QVBoxLayout(port_panel)
        port_panel_layout.setContentsMargins(13, 11, 13, 11)
        port_panel_layout.setSpacing(8)
        port_row = QHBoxLayout()
        port_label = QLabel("Port")
        port_label.setStyleSheet(f"color:{INK};font-weight:800;border:none;background:transparent;")
        self.port_input = QLineEdit(str(self.prefs.manual_port))
        self.port_input.setPlaceholderText("8766")
        self.port_input.setMaximumWidth(125)
        self.port_input.setStyleSheet(
            "QLineEdit{background:white;color:#17384E;border:1px solid #C7D5DE;border-radius:8px;padding:8px 10px;}"
            "QLineEdit:focus{border:1px solid #0B7180;}"
        )
        self.check_button = QPushButton("Check availability", objectName="Secondary")
        self.check_button.setIcon(icon("check", color=INK, size=17))
        self.check_button.setIconSize(QSize(17, 17))
        self.check_button.clicked.connect(self._check_port)
        port_row.addWidget(port_label)
        port_row.addWidget(self.port_input)
        port_row.addWidget(self.check_button)
        port_row.addStretch(1)
        port_panel_layout.addLayout(port_row)
        self.port_status = QLabel()
        self.port_status.setWordWrap(True)
        self.port_status.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;background:transparent;")
        port_panel_layout.addWidget(self.port_status)
        port_layout.addWidget(port_panel)
        self.auto_port.toggled.connect(self._sync_port_controls)
        self._sync_port_controls()
        content.addWidget(port_card, 0, 1)

        privacy_card = _card()
        privacy_layout = QVBoxLayout(privacy_card)
        privacy_layout.setContentsMargins(18, 16, 18, 16)
        privacy_layout.setSpacing(8)
        privacy_layout.addWidget(
            _section_header(
                "Local privacy boundary",
                "PrivacyGate keeps sensitive working data on this device.",
                "protect",
            )
        )
        privacy_copy = QLabel(
            "Documents, protected previews, restore mappings and connector credentials stay local. "
            "Account and organization services store only the minimum control-plane information needed for plans, roles, devices and policies."
        )
        privacy_copy.setWordWrap(True)
        privacy_copy.setStyleSheet(
            f"background:#F5FBF9;color:{INK};border:1px solid #D2EADF;border-radius:10px;padding:11px;font-size:9px;"
        )
        privacy_layout.addWidget(privacy_copy)
        content.addWidget(privacy_card, 1, 0, 1, 2)

        root.addLayout(content)

        buttons = QHBoxLayout()
        save = QPushButton("Save settings", objectName="Primary")
        save.setIcon(icon("save", color="#FFFFFF", size=18))
        save.setIconSize(QSize(18, 18))
        save.setMinimumHeight(38)
        save.clicked.connect(self._save)
        buttons.addStretch(1)
        buttons.addWidget(save)
        root.addLayout(buttons)
        root.addStretch(1)

    def mount_plan_panel(self, panel: QWidget) -> None:
        while self.plan_mount.count():
            item = self.plan_mount.takeAt(0)
            old = item.widget()
            if old is not None and old is not panel:
                old.setParent(None)
        self.plan_mount.addWidget(panel)

    def _sync_port_controls(self) -> None:
        enabled = self.manual_port.isChecked()
        self.port_input.setEnabled(enabled)
        self.check_button.setEnabled(enabled)
        if not enabled:
            self.port_status.setText("PrivacyGate will select a free local port automatically when the MCP service starts.")
        elif not self.port_status.text():
            self.port_status.setText("Use a fixed port only when another integration requires it.")

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
            self.port_status.setStyleSheet("color:#23824B;font-size:8px;border:none;background:transparent;font-weight:800;")
        else:
            self.port_status.setText(f"Port {port} is already in use.")
            self.port_status.setStyleSheet("color:#A23A3A;font-size:8px;border:none;background:transparent;font-weight:800;")

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
