from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.settings.preferences import is_port_available
from ai_pm_lab_privacy_gate.ui.iconography import icon

NAVY = "#062B4F"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
RED = "#B54747"


def _status_badge(text: str, tone: str) -> QLabel:
    palettes = {
        "green": ("#EAF8F1", GREEN, "#CDE8D9"),
        "red": ("#FDEEEE", RED, "#F0CCCC"),
        "navy": ("#EEF3F7", NAVY, "#D8E2E9"),
    }
    background, foreground, border = palettes.get(tone, palettes["navy"])
    badge = QLabel(text)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(
        f"background:{background};color:{foreground};border:1px solid {border};"
        "border-radius:9px;padding:5px 9px;font-size:8px;font-weight:900;letter-spacing:.4px;"
    )
    return badge


def _set_status_badge(badge: QLabel, text: str, tone: str) -> None:
    sample = _status_badge(text, tone)
    badge.setText(text)
    badge.setStyleSheet(sample.styleSheet())
    sample.deleteLater()


def _contains_heading(widget: QWidget, heading: str) -> bool:
    for label in widget.findChildren(QLabel):
        if label.text().strip() == heading:
            return True
    return False


def install_local_privacy_bridge_settings(main_window) -> bool:
    """Expose the existing Local Privacy Bridge on the redesigned Services page.

    The 2026 Settings redesign replaces the original long-form layout. The bridge
    backend and preference fields already exist; this adapter gives those same
    fields live controls inside the dedicated Services page and deliberately
    reuses ``SettingsPage._save`` as the single persistence path.
    """

    settings = getattr(main_window, "settings_page", None)
    if settings is None:
        return False
    if bool(getattr(settings, "_privacygate_local_bridge_service_2026", False)):
        return True

    pages = getattr(settings, "settings_service_pages", {})
    services_page = pages.get("services") if isinstance(pages, dict) else None
    if not isinstance(services_page, QWidget):
        return False

    content = services_page.findChild(QWidget, "Settings2026DedicatedContent")
    body = content.layout() if content is not None else None
    if not isinstance(body, QVBoxLayout):
        return False

    prefs = settings.store.load()

    card = QFrame(objectName="LocalPrivacyBridgeService2026")
    card.setStyleSheet(
        "QFrame#LocalPrivacyBridgeService2026{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:18px;}"
    )
    card_box = QVBoxLayout(card)
    card_box.setContentsMargins(18, 17, 18, 17)
    card_box.setSpacing(12)

    header = QHBoxLayout()
    header.setSpacing(10)
    bubble = QLabel()
    bubble.setFixedSize(40, 40)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon("protect", color=TEAL, size=21).pixmap(21, 21))
    bubble.setStyleSheet("background:#EAF8F8;border:none;border-radius:12px;")
    header.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(2)
    title = QLabel("Local Privacy Bridge")
    title.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:900;border:none;")
    subtitle = QLabel(
        "Protect text locally for browser and approved automation integrations before it leaves this device."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")
    copy.addWidget(title)
    copy.addWidget(subtitle)
    header.addLayout(copy, 1)
    badge = _status_badge("OFF", "navy")
    header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
    card_box.addLayout(header)

    controls = QFrame()
    controls.setStyleSheet("QFrame{background:#F8FBFC;border:1px solid #E3EBEF;border-radius:12px;}")
    controls_box = QVBoxLayout(controls)
    controls_box.setContentsMargins(13, 11, 13, 11)
    controls_box.setSpacing(10)

    enabled = QCheckBox("Enable Local Privacy Bridge")
    enabled.setChecked(bool(prefs.local_api_enabled))
    enabled.setStyleSheet(
        "QCheckBox{color:#17384E;font-size:10px;font-weight:850;spacing:9px;border:none;}"
        "QCheckBox::indicator{width:18px;height:18px;border-radius:5px;border:2px solid #91A9B9;background:white;}"
        "QCheckBox::indicator:checked{background:#0B7F89;border:2px solid #0B7F89;}"
    )
    controls_box.addWidget(enabled)

    port_row = QHBoxLayout()
    port_row.setSpacing(8)
    port_label = QLabel("Bridge port")
    port_label.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:800;border:none;")
    port_input = QLineEdit(str(prefs.local_api_port))
    port_input.setPlaceholderText("8765")
    port_input.setMaximumWidth(130)
    port_input.setMinimumHeight(38)
    port_input.setStyleSheet(
        "QLineEdit{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:10px;"
        "padding:8px 10px;font-size:10px;font-weight:700;}QLineEdit:disabled{background:#EEF3F5;color:#8294A0;}"
    )
    check_port = QPushButton("Check port")
    check_port.setCursor(Qt.CursorShape.PointingHandCursor)
    check_port.setMinimumHeight(38)
    check_port.setIcon(icon("check", color=NAVY, size=15))
    check_port.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #D3DFE6;border-radius:10px;"
        "padding:8px 12px;font-size:9px;font-weight:800;}"
        "QPushButton:hover{background:#F1F8F8;border-color:#9ACDCF;color:#0B7F89;}"
    )
    port_row.addWidget(port_label)
    port_row.addWidget(port_input)
    port_row.addWidget(check_port)
    port_row.addStretch(1)
    controls_box.addLayout(port_row)

    port_status = QLabel("")
    port_status.setWordWrap(True)
    port_status.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
    controls_box.addWidget(port_status)
    card_box.addWidget(controls)

    status_label = QLabel("")
    status_label.setWordWrap(True)
    status_label.setStyleSheet(f"color:{MUTED};font-size:9px;font-weight:750;border:none;")
    card_box.addWidget(status_label)

    boundary = QLabel(
        "Local-only boundary: 127.0.0.1 • browser-session mappings stay in memory • mappings are cleared when PrivacyGate quits."
    )
    boundary.setWordWrap(True)
    boundary.setStyleSheet(
        "background:#F1FAFA;color:#31576A;border:1px solid #D5ECEC;border-radius:10px;"
        "padding:9px 10px;font-size:8px;font-weight:700;"
    )
    card_box.addWidget(boundary)

    # The original card is removed by the 2026 redesign. Point the existing
    # SettingsPage save/status methods at these live controls so there is still
    # exactly one preferences implementation and one LocalApiManager.
    settings.local_api_enabled = enabled
    settings.local_api_port_input = port_input
    settings.local_api_status = status_label

    manager = getattr(main_window, "local_api_manager", None)

    def parsed_port() -> int | None:
        try:
            value = int(port_input.text().strip())
        except ValueError:
            return None
        return value if 1024 <= value <= 65535 else None

    def refresh_status() -> None:
        current = getattr(manager, "status", None)
        state = getattr(current, "state", "disabled")
        active_port = getattr(current, "port", None)
        error = str(getattr(current, "error", "") or "")

        if state == "online":
            _set_status_badge(badge, "RUNNING", "green")
            suffix = ""
            if not enabled.isChecked():
                suffix = " Save service settings to stop it."
            status_label.setText(f"Status: Running locally on 127.0.0.1:{active_port} ✓{suffix}")
            status_label.setStyleSheet(f"color:{GREEN};font-size:9px;font-weight:800;border:none;")
        elif state == "error":
            _set_status_badge(badge, "ERROR", "red")
            status_label.setText(f"Status: Could not start on this device — {error}")
            status_label.setStyleSheet(f"color:{RED};font-size:9px;font-weight:800;border:none;")
        else:
            _set_status_badge(badge, "OFF", "navy")
            if enabled.isChecked():
                status_label.setText("Status: Off — save service settings to start the bridge.")
            else:
                status_label.setText("Status: Off")
            status_label.setStyleSheet(f"color:{MUTED};font-size:9px;font-weight:750;border:none;")

        port_input.setEnabled(enabled.isChecked())
        check_port.setEnabled(enabled.isChecked())

    def check_port_availability() -> None:
        port = parsed_port()
        if port is None:
            port_status.setText("Enter a port between 1024 and 65535.")
            port_status.setStyleSheet(f"color:{RED};font-size:8px;font-weight:750;border:none;")
            return
        current = getattr(manager, "status", None)
        if getattr(current, "state", "") == "online" and int(getattr(current, "port", -1) or -1) == port:
            port_status.setText(f"Port {port} is currently used by your Local Privacy Bridge ✓")
            port_status.setStyleSheet(f"color:{GREEN};font-size:8px;font-weight:750;border:none;")
            return
        if is_port_available(port):
            port_status.setText(f"Port {port} is available ✓")
            port_status.setStyleSheet(f"color:{GREEN};font-size:8px;font-weight:750;border:none;")
        else:
            port_status.setText(f"Port {port} is already in use.")
            port_status.setStyleSheet(f"color:{RED};font-size:8px;font-weight:750;border:none;")

    def toggle_changed(_checked: bool) -> None:
        refresh_status()
        if not enabled.isChecked():
            port_status.clear()

    enabled.toggled.connect(toggle_changed)
    check_port.clicked.connect(check_port_availability)
    settings.preferences_changed.connect(lambda: QTimer.singleShot(0, refresh_status))

    insertion_index = body.count() - 1
    for index in range(body.count()):
        item = body.itemAt(index)
        widget = item.widget()
        if isinstance(widget, QWidget) and _contains_heading(widget, "PrivacyGate runtime services"):
            insertion_index = index
            break
    body.insertWidget(max(0, insertion_index), card)

    settings.local_privacy_bridge_service_card = card
    settings.refresh_local_privacy_bridge_service = refresh_status
    settings._privacygate_local_bridge_service_2026 = True
    refresh_status()
    return True
