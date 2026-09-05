from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate import __version__
from ai_pm_lab_privacy_gate.ui.iconography import icon

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
WHITE = "#FFFFFF"
BLUE = "#155EEF"
BLUE_SOFT = "#EEF4FF"
GREEN = "#039855"
GREEN_SOFT = "#ECFDF3"
PURPLE = "#6938EF"
PURPLE_SOFT = "#F4F3FF"
ORANGE = "#F97316"
ORANGE_SOFT = "#FFF4ED"
BORDER = "#DCE6ED"
CANVAS = "#F7FAFC"


class _MockupServiceCard(QFrame):
    clicked = Signal()

    def __init__(
        self,
        title: str,
        detail: str,
        icon_name: str,
        *,
        accent: str,
        soft: str,
        enabled: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ApprovedSettingsServiceCard")
        self.setMinimumHeight(82)
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if enabled else Qt.FocusPolicy.NoFocus)
        self.setEnabled(enabled)
        self._accent = accent
        self._soft = soft
        self._apply_style(False)

        row = QHBoxLayout(self)
        row.setContentsMargins(13, 10, 13, 10)
        row.setSpacing(11)

        bubble = QLabel()
        bubble.setFixedSize(42, 42)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setPixmap(icon(icon_name, color=accent, size=21).pixmap(21, 21))
        bubble.setStyleSheet(f"background:{soft};border:none;border-radius:12px;")
        bubble.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignVCenter)

        copy = QVBoxLayout()
        copy.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color:{NAVY};font-size:11px;font-weight:900;border:none;background:transparent;"
        )
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        detail_label = QLabel(detail)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet(
            f"color:{MUTED};font-size:8px;border:none;background:transparent;"
        )
        detail_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        copy.addWidget(title_label)
        copy.addWidget(detail_label)
        row.addLayout(copy, 1)

        arrow = QLabel("›")
        arrow.setStyleSheet(
            f"color:{accent};font-size:20px;font-weight:800;border:none;background:transparent;"
        )
        arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(arrow, 0, Qt.AlignmentFlag.AlignVCenter)

    def _apply_style(self, hover: bool) -> None:
        border = self._accent if hover and self.isEnabled() else BORDER
        width = 2 if hover and self.isEnabled() else 1
        self.setStyleSheet(
            f"QFrame#ApprovedSettingsServiceCard{{background:#FFFFFF;border:{width}px solid {border};"
            "border-radius:13px;}"
        )

    def enterEvent(self, event) -> None:  # noqa: N802
        self._apply_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._apply_style(False)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self.isEnabled() and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}:
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear_layout(child)


def _section(title: str, subtitle: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("ApprovedSettingsSection")
    frame.setStyleSheet(
        "QFrame#ApprovedSettingsSection{background:#FFFFFF;border:1px solid #DCE6ED;border-radius:15px;}"
    )
    box = QVBoxLayout(frame)
    box.setContentsMargins(15, 11, 15, 13)
    box.setSpacing(8)
    heading = QLabel(title)
    heading.setStyleSheet(
        f"color:{NAVY};font-size:14px;font-weight:950;border:none;background:transparent;"
    )
    note = QLabel(subtitle)
    note.setWordWrap(True)
    note.setStyleSheet(
        f"color:{MUTED};font-size:8.5px;border:none;background:transparent;"
    )
    box.addWidget(heading)
    box.addWidget(note)
    return frame, box


def _label_value(label: str, value: str, *, value_style: str = "") -> QWidget:
    row = QWidget()
    row.setStyleSheet("background:transparent;")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    left = QLabel(label)
    left.setStyleSheet(f"color:{INK};font-size:9px;border:none;background:transparent;")
    right = QLabel(value)
    right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    right.setStyleSheet(
        value_style
        or f"color:{NAVY};font-size:9px;font-weight:850;border:none;background:transparent;"
    )
    layout.addWidget(left, 1)
    layout.addWidget(right)
    return row


def _right_button(text: str, *, primary: bool = False, enabled: bool = True) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(35)
    button.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
    button.setEnabled(enabled)
    if primary:
        button.setStyleSheet(
            "QPushButton{background:#0794A3;color:#FFFFFF;border:none;border-radius:10px;"
            "padding:8px 12px;font-size:9px;font-weight:900;}"
            "QPushButton:hover{background:#087D89;}"
            "QPushButton:disabled{background:#E9EEF2;color:#98A7B2;}"
        )
    else:
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #D8E3EA;border-radius:10px;"
            "padding:8px 12px;font-size:9px;font-weight:850;text-align:left;}"
            "QPushButton:hover{background:#F5FAFB;border-color:#9ECFD2;color:#0B7F89;}"
            "QPushButton:disabled{background:#F7F9FA;color:#A6B0B8;border-color:#E4E9ED;}"
        )
    return button


def _status_row(text: str, status: str, *, color: str) -> QWidget:
    row = QWidget()
    row.setStyleSheet("background:transparent;")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(7)
    label = QLabel(text)
    label.setStyleSheet(f"color:{INK};font-size:9px;border:none;background:transparent;")
    dot = QLabel("●")
    dot.setStyleSheet(f"color:{color};font-size:9px;border:none;background:transparent;")
    value = QLabel(status)
    value.setStyleSheet(f"color:{INK};font-size:9px;border:none;background:transparent;")
    layout.addWidget(label, 1)
    layout.addWidget(dot)
    layout.addWidget(value)
    return row


def _open_service(settings, key: str) -> None:
    pages = getattr(settings, "settings_service_pages", None)
    stack = getattr(settings, "settings_service_stack", None)
    if not isinstance(pages, dict) or stack is None:
        return
    page = pages.get(key)
    if page is not None:
        stack.setCurrentWidget(page)
        if key == "workspaces":
            panel = getattr(settings, "_privacygate_workspace_settings_panel", None)
            if panel is not None and hasattr(panel, "refresh"):
                QTimer.singleShot(80, panel.refresh)
        if key == "files" and hasattr(page, "refresh_workspaces"):
            QTimer.singleShot(80, page.refresh_workspaces)


def _approved_card(settings, title: str, detail: str, icon_name: str, key: str | None, accent: str, soft: str):
    enabled = bool(key and isinstance(getattr(settings, "settings_service_pages", None), dict) and key in settings.settings_service_pages)
    card = _MockupServiceCard(
        title,
        detail,
        icon_name,
        accent=accent,
        soft=soft,
        enabled=enabled,
    )
    if enabled and key is not None:
        card.clicked.connect(lambda: _open_service(settings, key))
    elif not enabled:
        card.setToolTip(f"{title} controls are not available as a dedicated module in this build")
    return card


def _build_everyday_controls(settings) -> QFrame:
    section, box = _section("Everyday controls", "Quick settings you use most, available directly here.")

    row = QHBoxLayout()
    row.setSpacing(12)

    controls = QFrame()
    controls.setObjectName("ApprovedEverydayControls")
    controls.setStyleSheet(
        "QFrame#ApprovedEverydayControls{background:#FFFFFF;border:1px solid #E1E8ED;border-radius:13px;}"
    )
    controls_box = QVBoxLayout(controls)
    controls_box.setContentsMargins(13, 11, 13, 11)
    controls_box.setSpacing(8)

    head = QHBoxLayout()
    ico = QLabel()
    ico.setFixedSize(28, 28)
    ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ico.setPixmap(icon("settings", color=NAVY, size=15).pixmap(15, 15))
    ico.setStyleSheet("background:#EEF4F8;border:none;border-radius:9px;")
    head.addWidget(ico, 0, Qt.AlignmentFlag.AlignTop)
    copy = QVBoxLayout()
    copy.setSpacing(1)
    title = QLabel("Desktop behavior")
    title.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:900;border:none;")
    note = QLabel("Choose what PrivacyGate does when you close the app.")
    note.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
    copy.addWidget(title)
    copy.addWidget(note)
    head.addLayout(copy, 1)
    controls_box.addLayout(head)

    actions = QHBoxLayout()
    actions.setSpacing(10)
    combo = QComboBox()
    combo.setMinimumHeight(34)
    combo.addItem("Ask me every time", "ask")
    combo.addItem("Keep running in background", "background")
    combo.addItem("Quit PrivacyGate", "quit")
    combo.setStyleSheet(
        "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #D5E0E7;border-radius:9px;"
        "padding:7px 10px;font-size:8.5px;}QComboBox::drop-down{border:none;width:24px;}"
    )
    actions.addWidget(combo, 1)
    open_device = _right_button("Open Device controls  ↗", primary=True)
    open_device.clicked.connect(lambda: _open_service(settings, "device"))
    actions.addWidget(open_device)
    controls_box.addLayout(actions)
    row.addWidget(controls, 1)

    save_col = QVBoxLayout()
    save_col.setSpacing(5)
    save = _right_button("Save quick settings", primary=False)
    save.setMinimumWidth(150)
    saved = QLabel("Saved locally on this device.")
    saved.setAlignment(Qt.AlignmentFlag.AlignCenter)
    saved.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
    save_col.addStretch(1)
    save_col.addWidget(save)
    save_col.addWidget(saved)
    save_col.addStretch(1)
    row.addLayout(save_col)
    box.addLayout(row)

    def sync() -> None:
        prefs = getattr(settings, "prefs", None)
        if prefs is None:
            return
        index = combo.findData(getattr(prefs, "close_behavior", "ask"))
        combo.setCurrentIndex(max(0, index))

    def persist() -> None:
        value = str(combo.currentData() or "ask")
        radios = getattr(settings, "close_radios", {})
        radio = radios.get(value) if isinstance(radios, dict) else None
        if radio is not None:
            radio.setChecked(True)
        save_fn = getattr(settings, "_save", None)
        if callable(save_fn):
            save_fn()
        saved.setText("Saved locally on this device.")

    save.clicked.connect(persist)
    signal = getattr(settings, "preferences_changed", None)
    if signal is not None:
        try:
            signal.connect(sync)
        except (RuntimeError, TypeError):
            pass
    sync()
    settings.approved_settings_close_behavior_combo = combo
    return section


def apply_approved_settings_mockup_2026(main_window) -> None:
    settings = getattr(main_window, "settings_page", None)
    if settings is None or bool(getattr(settings, "_privacygate_approved_settings_mockup_2026", False)):
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

    _clear_layout(body)
    body.setContentsMargins(20, 18, 20, 18)
    body.setSpacing(12)
    content.setStyleSheet(
        "QWidget#Settings2026HubContent{background:#F8FAFC;}"
        "QWidget#Settings2026HubContent QLabel{background:transparent;}"
    )

    # Header exactly follows the approved light Settings mockup.
    header = QHBoxLayout()
    header.setSpacing(14)
    settings_icon = QLabel()
    settings_icon.setFixedSize(52, 52)
    settings_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    settings_icon.setPixmap(icon("settings", color=NAVY, size=29).pixmap(29, 29))
    settings_icon.setStyleSheet("background:#EEF6FF;border:1px solid #D5E5F5;border-radius:15px;")
    header.addWidget(settings_icon, 0, Qt.AlignmentFlag.AlignTop)

    header_copy = QVBoxLayout()
    header_copy.setSpacing(2)
    title = QLabel("Settings")
    title.setStyleSheet(f"color:{NAVY};font-size:24px;font-weight:950;border:none;")
    subtitle = QLabel("Manage your PrivacyGate experience. Each section opens its own focused page with real controls.")
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:9.5px;border:none;")
    header_copy.addWidget(title)
    header_copy.addWidget(subtitle)
    header.addLayout(header_copy, 1)

    device_badge = QFrame()
    device_badge.setObjectName("ApprovedSettingsDeviceBadge")
    device_badge.setMinimumWidth(286)
    device_badge.setStyleSheet(
        "QFrame#ApprovedSettingsDeviceBadge{background:#FFFFFF;border:1px solid #DCE6ED;border-radius:13px;}"
    )
    badge_row = QHBoxLayout(device_badge)
    badge_row.setContentsMargins(13, 9, 13, 9)
    badge_row.setSpacing(9)
    desktop_icon = QLabel()
    desktop_icon.setFixedSize(32, 32)
    desktop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    desktop_icon.setPixmap(icon("settings", color=NAVY, size=19).pixmap(19, 19))
    badge_row.addWidget(desktop_icon)
    badge_copy = QVBoxLayout()
    badge_copy.setSpacing(1)
    badge_title = QLabel("LOCAL DEVICE")
    badge_title.setStyleSheet(f"color:{NAVY};font-size:8px;font-weight:900;border:none;")
    badge_status = QLabel("●  Privacy First Mode")
    badge_status.setStyleSheet(f"color:{GREEN};font-size:8px;border:none;")
    badge_copy.addWidget(badge_title)
    badge_copy.addWidget(badge_status)
    badge_row.addLayout(badge_copy, 1)
    version_col = QVBoxLayout()
    version_col.setSpacing(2)
    version = QLabel(f"v{__version__}")
    version.setAlignment(Qt.AlignmentFlag.AlignRight)
    version.setStyleSheet(f"color:{NAVY};font-size:9px;border:none;")
    state = QLabel("Up to date")
    state.setAlignment(Qt.AlignmentFlag.AlignCenter)
    state.setStyleSheet(
        "background:#EAF8F1;color:#23824B;border:none;border-radius:8px;padding:3px 7px;"
        "font-size:7.5px;font-weight:850;"
    )
    version_col.addWidget(version)
    version_col.addWidget(state)
    badge_row.addLayout(version_col)
    header.addWidget(device_badge, 0, Qt.AlignmentFlag.AlignTop)
    body.addLayout(header)

    content_row = QHBoxLayout()
    content_row.setSpacing(13)
    left = QVBoxLayout()
    left.setSpacing(12)

    core, core_box = _section("Core Services", "Essential settings for your account, workspaces and local device.")
    core_grid = QGridLayout()
    core_grid.setHorizontalSpacing(10)
    core_grid.setVerticalSpacing(10)
    for index, card in enumerate(
        (
            _approved_card(settings, "Account", "Profile, plan and entitlement settings.", "contact", "account", BLUE, BLUE_SOFT),
            _approved_card(settings, "Workspaces", "Personal and company contexts, workspace management.", "workflow", "workspaces", GREEN, GREEN_SOFT),
            _approved_card(settings, "Device", "Desktop behavior and local privacy controls.", "settings", "device", PURPLE, PURPLE_SOFT),
        )
    ):
        core_grid.addWidget(card, 0, index)
        core_grid.setColumnStretch(index, 1)
    core_box.addLayout(core_grid)
    left.addWidget(core)

    data, data_box = _section("Data & Privacy", "Configure how data is handled, protected and stored on your device.")
    data_grid = QGridLayout()
    data_grid.setHorizontalSpacing(10)
    data_grid.setVerticalSpacing(10)
    for index, card in enumerate(
        (
            _approved_card(settings, "Services", "Browser protection, automation and connections.", "protect", "services", GREEN, GREEN_SOFT),
            _approved_card(settings, "Files", "Per-workspace local file routing and storage.", "library", "files", BLUE, BLUE_SOFT),
            _approved_card(settings, "Updates", "Check for updates, release channel and maintenance controls.", "download", "updates", ORANGE, ORANGE_SOFT),
        )
    ):
        data_grid.addWidget(card, 0, index)
        data_grid.setColumnStretch(index, 1)
    data_box.addLayout(data_grid)
    left.addWidget(data)

    advanced, advanced_box = _section("Advanced", "Power user settings and additional tools.")
    advanced_card = _approved_card(
        settings,
        "Advanced",
        "Batch processing, OCR, watched folders, preflight rules and encrypted backup.",
        "settings",
        None,
        PURPLE,
        PURPLE_SOFT,
    )
    advanced_box.addWidget(advanced_card)
    left.addWidget(advanced)

    left.addWidget(_build_everyday_controls(settings))
    left.addStretch(1)
    content_row.addLayout(left, 1)

    right = QFrame()
    right.setObjectName("ApprovedSettingsRightRail")
    right.setMinimumWidth(286)
    right.setMaximumWidth(310)
    right.setStyleSheet(
        "QFrame#ApprovedSettingsRightRail{background:#FFFFFF;border:1px solid #DCE6ED;border-radius:15px;}"
    )
    right_box = QVBoxLayout(right)
    right_box.setContentsMargins(16, 14, 16, 14)
    right_box.setSpacing(10)

    app_title = QLabel("Application Information")
    app_title.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:950;border:none;")
    right_box.addWidget(app_title)
    right_box.addWidget(_label_value("Current version", __version__))
    right_box.addWidget(
        _label_value(
            "Release channel",
            "Stable",
            value_style="background:#EAF8F1;color:#23824B;border:none;border-radius:8px;padding:3px 7px;font-size:8px;font-weight:850;",
        )
    )
    right_box.addWidget(_label_value("Last checked", "Use Check for updates"))

    check = _right_button("↓  Check for updates now", primary=True)
    release = _right_button("↗  Open release support")
    contact = getattr(main_window, "contact_page", None)
    check_fn = getattr(contact, "check_updates", None) if contact is not None else None
    if callable(check_fn):
        check.clicked.connect(lambda: check_fn(silent=False))
    else:
        check.setEnabled(False)
    if contact is not None:
        release.clicked.connect(lambda: main_window._show_page(main_window.pages.indexOf(contact)))
    else:
        release.setEnabled(False)
    right_box.addWidget(check)
    right_box.addWidget(release)

    divider = QFrame()
    divider.setFixedHeight(1)
    divider.setStyleSheet("background:#E2E8ED;border:none;")
    right_box.addWidget(divider)

    status_title = QLabel("System Status")
    status_title.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:950;border:none;")
    right_box.addWidget(status_title)
    local_api = getattr(settings, "local_api_enabled", None)
    local_on = bool(local_api is None or not hasattr(local_api, "isChecked") or local_api.isChecked())
    right_box.addWidget(_status_row("Local services", "Running" if local_on else "Off", color=GREEN if local_on else MUTED))
    right_box.addWidget(_status_row("Privacy engine", "Ready", color=GREEN))
    right_box.addWidget(_status_row("File routing", "Ready", color=GREEN))
    auto_port = getattr(settings, "auto_port", None)
    mcp_ready = bool(auto_port is not None)
    right_box.addWidget(_status_row("MCP controls", "Ready" if mcp_ready else "Not configured", color=GREEN if mcp_ready else "#98A2B3"))

    divider2 = QFrame()
    divider2.setFixedHeight(1)
    divider2.setStyleSheet("background:#E2E8ED;border:none;")
    right_box.addWidget(divider2)

    quick_title = QLabel("Quick Actions")
    quick_title.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:950;border:none;")
    right_box.addWidget(quick_title)
    logs = _right_button("▢  Open logs folder", enabled=False)
    export = _right_button("⇧  Export settings", enabled=False)
    reset = _right_button("↻  Reset to defaults", enabled=False)
    logs.setToolTip("No dedicated logs-folder action exists in this build")
    export.setToolTip("Settings export is not implemented in this build")
    reset.setToolTip("Reset-to-defaults is not implemented in this build")
    right_box.addWidget(logs)
    right_box.addWidget(export)
    right_box.addWidget(reset)
    right_box.addStretch(1)
    content_row.addWidget(right, 0, Qt.AlignmentFlag.AlignTop)
    body.addLayout(content_row)

    footer = QFrame()
    footer.setObjectName("ApprovedSettingsArchitecture")
    footer.setStyleSheet(
        "QFrame#ApprovedSettingsArchitecture{background:#FFFFFF;border:1px solid #DCE6ED;border-radius:14px;}"
    )
    footer_row = QHBoxLayout(footer)
    footer_row.setContentsMargins(14, 10, 14, 10)
    footer_row.setSpacing(11)
    footer_icon = QLabel()
    footer_icon.setFixedSize(36, 36)
    footer_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    footer_icon.setPixmap(icon("workflow", color=BLUE, size=20).pixmap(20, 20))
    footer_icon.setStyleSheet("background:#EEF4FF;border:none;border-radius:10px;")
    footer_row.addWidget(footer_icon)
    footer_copy = QVBoxLayout()
    footer_copy.setSpacing(1)
    footer_title = QLabel("Settings architecture")
    footer_title.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:900;border:none;")
    footer_note = QLabel(
        "Settings is organized into focused modules. Each module opens its own page so new controls can grow without turning the main screen into one long form."
    )
    footer_note.setWordWrap(True)
    footer_note.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
    footer_copy.addWidget(footer_title)
    footer_copy.addWidget(footer_note)
    footer_row.addLayout(footer_copy, 1)
    badge = QLabel("PERSONAL + MULTI-WORKSPACE READY")
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(
        "background:#ECFEFF;color:#087D89;border:1px solid #A5E5E9;border-radius:9px;"
        "padding:5px 9px;font-size:7px;font-weight:900;"
    )
    footer_row.addWidget(badge)
    body.addWidget(footer)

    settings._privacygate_approved_settings_mockup_2026 = True
    stack.setCurrentWidget(hub)


def apply_settings_service_hub_2026(main_window) -> None:
    """Schedule the approved Settings mockup after the dedicated service stack exists.

    The service pages created later in MainWindow initialization remain the source
    of truth. This layer only rebuilds the launcher once those pages are available.
    """
    settings = getattr(main_window, "settings_page", None)
    if settings is None or bool(getattr(settings, "_privacygate_service_hub_2026", False)):
        return
    settings._privacygate_service_hub_2026 = True
    QTimer.singleShot(0, lambda: apply_approved_settings_mockup_2026(main_window))
