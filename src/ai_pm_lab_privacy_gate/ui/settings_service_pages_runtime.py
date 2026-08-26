from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.settings.preferences import is_port_available
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.settings_service_pages_2026 import (
    WorkspaceFilesPage,
    apply_settings_service_pages_2026 as _apply_service_pages,
)

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
WHITE = "#FFFFFF"
GREEN = "#23824B"
RED = "#B54747"


def _safe_refresh_table(self: WorkspaceFilesPage) -> None:
    context = self._context()
    if context is None:
        return
    self.table.setRowCount(len(context.workspaces))
    for row, (key, descriptor) in enumerate(context.workspaces.items()):
        route = self.routes.route_for(key, descriptor.name)
        root = Path(route.root)
        values = (
            descriptor.name,
            "Personal" if descriptor.personal else f"Company · {descriptor.plan.label}",
            str(root),
            "Ready" if root.exists() else "Not created",
        )
        for column, value in enumerate(values):
            self.table.setItem(row, column, QTableWidgetItem(value))


def _open_apps_safely(main_window) -> None:
    index = getattr(main_window, "apps_page_index", None)
    pages = getattr(main_window, "pages", None)
    if index is None or pages is None or not 0 <= int(index) < pages.count():
        return
    pages.setCurrentIndex(int(index))
    for button in getattr(main_window, "nav_buttons", []):
        button.setChecked(False)
    if int(index) < len(getattr(main_window, "nav_buttons", [])):
        main_window.nav_buttons[int(index)].setChecked(True)


def _secondary_button(text: str, *, icon_name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(40)
    if icon_name:
        button.setIcon(icon(icon_name, color=NAVY, size=16))
    button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #D5E1E7;"
        "border-radius:11px;padding:8px 13px;font-size:10px;font-weight:850;}"
        "QPushButton:hover{background:#EFF8F8;color:#0B7F89;border-color:#91CBCD;}"
        "QPushButton:pressed{background:#E4F3F3;}"
    )
    return button


def _primary_button(text: str, *, icon_name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(42)
    if icon_name:
        button.setIcon(icon(icon_name, color=WHITE, size=16))
    button.setStyleSheet(
        "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:11px;"
        "padding:9px 15px;font-size:10px;font-weight:900;}"
        "QPushButton:hover{background:#096D76;}QPushButton:pressed{background:#075D65;}"
    )
    return button


def _decorate_service_navigation(settings) -> None:
    """Make returning to the Settings launcher visually unmistakable."""
    pages = getattr(settings, "settings_service_pages", None)
    stack = getattr(settings, "settings_service_stack", None)
    hub = getattr(settings, "settings_service_hub", None)
    if not isinstance(pages, dict) or stack is None or hub is None:
        return

    def go_home() -> None:
        stack.setCurrentWidget(hub)

    for page in pages.values():
        if not isinstance(page, QWidget):
            continue
        content = page.findChild(QWidget, "Settings2026DedicatedContent")
        if content is None or content.layout() is None or content.layout().count() == 0:
            continue
        top_item = content.layout().itemAt(0)
        top = top_item.layout() if top_item is not None else None
        if not isinstance(top, QHBoxLayout):
            continue

        back = None
        for index in range(top.count()):
            widget = top.itemAt(index).widget()
            if isinstance(widget, QPushButton) and "Settings" in widget.text():
                back = widget
                break
        if back is None:
            continue

        back.setText("←  All Settings")
        back.setMinimumHeight(42)
        back.setMinimumWidth(132)
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setToolTip("Return to the Settings control center")
        back.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#062B4F;border:1px solid #D3E0E7;"
            "border-radius:11px;padding:9px 14px;font-size:11px;font-weight:900;text-align:left;}"
            "QPushButton:hover{background:#EAF7F7;color:#0B7F89;border-color:#82C1C6;}"
            "QPushButton:pressed{background:#DFF1F1;}"
        )

        if page.property("privacygateSettingsCloseAdded"):
            continue
        close = QPushButton("×")
        close.setFixedSize(42, 42)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setToolTip("Close this service and return to All Settings")
        close.setAccessibleName("Return to All Settings")
        close.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#526A79;border:1px solid #D3E0E7;"
            "border-radius:11px;font-size:22px;font-weight:700;padding-bottom:3px;}"
            "QPushButton:hover{background:#FFF3F3;color:#B54747;border-color:#E8BDBD;}"
            "QPushButton:pressed{background:#FBE5E5;}"
        )
        close.clicked.connect(go_home)
        top.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        page.setProperty("privacygateSettingsCloseAdded", True)


def _quick_setting_card(title: str, subtitle: str, icon_name: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("SettingsGeneralQuickCard")
    card.setStyleSheet(
        "QFrame#SettingsGeneralQuickCard{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:17px;}"
    )
    box = QVBoxLayout(card)
    box.setContentsMargins(16, 15, 16, 15)
    box.setSpacing(10)

    head = QHBoxLayout()
    head.setSpacing(10)
    bubble = QLabel()
    bubble.setFixedSize(38, 38)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon(icon_name, color=TEAL, size=20).pixmap(20, 20))
    bubble.setStyleSheet("background:#EAF8F8;border:none;border-radius:12px;")
    head.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)
    copy = QVBoxLayout()
    copy.setSpacing(1)
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:900;border:none;")
    note = QLabel(subtitle)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
    copy.addWidget(heading)
    copy.addWidget(note)
    head.addLayout(copy, 1)
    box.addLayout(head)
    return card, box


def _combo() -> QComboBox:
    combo = QComboBox()
    combo.setMinimumHeight(40)
    combo.setStyleSheet(
        "QComboBox{background:#F8FBFC;color:#17384E;border:1px solid #C9D7E0;border-radius:10px;"
        "padding:8px 11px;font-size:10px;font-weight:800;}"
        "QComboBox:hover{background:#FFFFFF;border-color:#91CBCD;}"
        "QComboBox:focus{background:#FFFFFF;border-color:#0B7F89;}"
        "QComboBox::drop-down{border:none;width:26px;}"
        "QComboBox QAbstractItemView{background:#FFFFFF;color:#17384E;border:1px solid #D7E2E8;"
        "selection-background-color:#E8F7F7;selection-color:#062B4F;padding:5px;outline:0;}"
    )
    return combo


def _install_general_quick_settings(main_window, settings) -> None:
    """Restore the useful everyday controls on the general Settings page.

    The dedicated Device/Services pages still own the full controls. These are a
    synchronized quick-control surface that writes through the original SettingsPage
    widgets and _save() implementation, so there is only one persisted preference model.
    """
    if bool(getattr(settings, "_privacygate_general_quick_settings", False)):
        return
    hub = getattr(settings, "settings_service_hub", None)
    stack = getattr(settings, "settings_service_stack", None)
    pages = getattr(settings, "settings_service_pages", None)
    if hub is None or stack is None or not isinstance(pages, dict):
        return

    scroll = hub.findChild(QScrollArea)
    content = scroll.widget() if scroll is not None else None
    body = content.layout() if content is not None else None
    if not isinstance(body, QVBoxLayout):
        return

    section = QFrame()
    section.setObjectName("SettingsGeneralControls")
    section.setStyleSheet(
        "QFrame#SettingsGeneralControls{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        "stop:0 #F9FBFC,stop:1 #F1F8F8);border:1px solid #DDE7EC;border-radius:19px;}"
    )
    section_box = QVBoxLayout(section)
    section_box.setContentsMargins(17, 16, 17, 17)
    section_box.setSpacing(12)

    title_row = QHBoxLayout()
    copy = QVBoxLayout()
    copy.setSpacing(2)
    eyebrow = QLabel("QUICK SETTINGS")
    eyebrow.setStyleSheet(
        "color:#0B7F89;font-size:8px;font-weight:900;letter-spacing:1px;border:none;"
    )
    title = QLabel("Everyday controls")
    title.setStyleSheet("color:#062B4F;font-size:17px;font-weight:950;border:none;")
    subtitle = QLabel(
        "Change the settings you use most without opening another page. The dedicated service pages remain available for the full controls."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet("color:#61798A;font-size:10px;border:none;")
    copy.addWidget(eyebrow)
    copy.addWidget(title)
    copy.addWidget(subtitle)
    title_row.addLayout(copy, 1)
    section_box.addLayout(title_row)

    cards = QHBoxLayout()
    cards.setSpacing(12)

    desktop_card, desktop_box = _quick_setting_card(
        "Desktop behavior",
        "Choose what PrivacyGate does when you close the app.",
        "settings",
    )
    close_combo = _combo()
    close_combo.addItem("Ask me every time", "ask")
    close_combo.addItem("Keep running in background", "background")
    close_combo.addItem("Quit PrivacyGate", "quit")
    desktop_box.addWidget(close_combo)
    open_device = _secondary_button("Open Device controls", icon_name="external")
    open_device.clicked.connect(lambda: stack.setCurrentWidget(pages["device"]))
    desktop_box.addWidget(open_device, 0, Qt.AlignmentFlag.AlignLeft)
    cards.addWidget(desktop_card, 1)

    service_card, service_box = _quick_setting_card(
        "Local MCP service",
        "Automatic is recommended. Choose Manual only when an integration needs a fixed local port.",
        "workflow",
    )
    mode_combo = _combo()
    mode_combo.addItem("Automatic (recommended)", "automatic")
    mode_combo.addItem("Manual port", "manual")
    service_box.addWidget(mode_combo)

    port_row = QHBoxLayout()
    port_row.setSpacing(8)
    port_input = QLineEdit()
    port_input.setPlaceholderText("8766")
    port_input.setMinimumHeight(40)
    port_input.setMaximumWidth(150)
    port_input.setStyleSheet(
        "QLineEdit{background:#F8FBFC;color:#17384E;border:1px solid #C9D7E0;border-radius:10px;"
        "padding:8px 10px;font-size:10px;font-weight:800;}"
        "QLineEdit:focus{background:#FFFFFF;border-color:#0B7F89;}"
        "QLineEdit:disabled{background:#EEF2F4;color:#91A0AA;}"
    )
    check = _secondary_button("Check port", icon_name="check")
    port_row.addWidget(port_input)
    port_row.addWidget(check)
    port_row.addStretch(1)
    service_box.addLayout(port_row)
    port_status = QLabel("")
    port_status.setWordWrap(True)
    port_status.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
    service_box.addWidget(port_status)
    open_services = _secondary_button("Open Services controls", icon_name="external")
    open_services.clicked.connect(lambda: stack.setCurrentWidget(pages["services"]))
    service_box.addWidget(open_services, 0, Qt.AlignmentFlag.AlignLeft)
    cards.addWidget(service_card, 1)
    section_box.addLayout(cards)

    save_row = QHBoxLayout()
    save_note = QLabel("Saved locally on this device. MCP changes apply the next time the local service starts.")
    save_note.setWordWrap(True)
    save_note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
    save_row.addWidget(save_note, 1)
    save_button = _primary_button("Save quick settings", icon_name="save")
    save_row.addWidget(save_button)
    section_box.addLayout(save_row)

    # Put the everyday controls immediately below the service launcher, before the
    # architecture/footer card. The page remains a useful Settings screen even if
    # the user never opens a dedicated service.
    insert_index = max(0, body.count() - 2)
    body.insertWidget(insert_index, section)

    def sync_from_settings() -> None:
        prefs = getattr(settings, "prefs", None)
        if prefs is None:
            return
        close_index = close_combo.findData(prefs.close_behavior)
        close_combo.setCurrentIndex(max(0, close_index))
        mode_index = mode_combo.findData(prefs.port_mode)
        mode_combo.setCurrentIndex(max(0, mode_index))
        port_input.setText(str(prefs.manual_port))
        manual = prefs.port_mode == "manual"
        port_input.setEnabled(manual)
        check.setEnabled(manual)
        port_status.setText(
            "Manual port is active." if manual else "PrivacyGate will choose a free local port automatically."
        )
        port_status.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")

    def sync_port_mode() -> None:
        manual = str(mode_combo.currentData() or "automatic") == "manual"
        port_input.setEnabled(manual)
        check.setEnabled(manual)
        if not manual:
            port_status.setText("PrivacyGate will choose a free local port automatically.")
            port_status.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")

    def check_port() -> None:
        try:
            value = int(port_input.text().strip())
        except ValueError:
            value = 0
        if not 1024 <= value <= 65535:
            port_status.setText("Enter a port between 1024 and 65535.")
            port_status.setStyleSheet(f"color:{RED};font-size:9px;font-weight:800;border:none;")
            return
        if is_port_available(value):
            port_status.setText(f"Port {value} is available ✓")
            port_status.setStyleSheet(f"color:{GREEN};font-size:9px;font-weight:850;border:none;")
        else:
            port_status.setText(f"Port {value} is already in use.")
            port_status.setStyleSheet(f"color:{RED};font-size:9px;font-weight:850;border:none;")

    def save_quick() -> None:
        close_value = str(close_combo.currentData() or "ask")
        close_radios = getattr(settings, "close_radios", {})
        radio = close_radios.get(close_value) if isinstance(close_radios, dict) else None
        if radio is not None:
            radio.setChecked(True)

        mode = str(mode_combo.currentData() or "automatic")
        if mode == "automatic":
            settings.auto_port.setChecked(True)
        else:
            settings.manual_port.setChecked(True)
        settings.port_input.setText(port_input.text().strip())
        settings._save()

    mode_combo.currentIndexChanged.connect(lambda _index: sync_port_mode())
    check.clicked.connect(check_port)
    save_button.clicked.connect(save_quick)
    if getattr(settings, "preferences_changed", None) is not None:
        settings.preferences_changed.connect(sync_from_settings)
    sync_from_settings()

    settings.general_close_behavior_combo = close_combo
    settings.general_port_mode_combo = mode_combo
    settings.general_port_input = port_input
    settings._privacygate_general_quick_settings = True


def _compact_hub_cards(settings) -> None:
    hub = getattr(settings, "settings_service_hub", None)
    if hub is None:
        return
    for card in hub.findChildren(QFrame, "Settings2026HubCard"):
        card.setMinimumHeight(92)
        card.setMaximumHeight(116)


def apply_settings_service_pages_2026_runtime(main_window) -> None:
    """Apply the dedicated service shell with Windows-safe navigation and general controls."""
    WorkspaceFilesPage._refresh_table = _safe_refresh_table
    _apply_service_pages(main_window)

    settings = getattr(main_window, "settings_page", None)
    pages = getattr(settings, "settings_service_pages", {}) if settings is not None else {}
    workspace_page = pages.get("workspaces") if isinstance(pages, dict) else None
    if workspace_page is not None:
        for button in workspace_page.findChildren(QPushButton):
            if button.text().strip() != "Apps & AI":
                continue
            try:
                button.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass
            button.clicked.connect(lambda: _open_apps_safely(main_window))
            break

    if settings is None:
        return
    _decorate_service_navigation(settings)
    _compact_hub_cards(settings)
    _install_general_quick_settings(main_window, settings)
