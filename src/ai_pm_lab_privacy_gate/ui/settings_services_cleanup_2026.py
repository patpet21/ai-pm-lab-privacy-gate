from __future__ import annotations

import os
from dataclasses import replace

from PySide6.QtCore import QCoreApplication, QEvent, QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon


NAVY = "#062B4F"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
AMBER = "#A96B18"
RED = "#B54747"


def _card_from_control(settings: QWidget, attribute: str) -> QFrame | None:
    control = getattr(settings, attribute, None)
    current = control if isinstance(control, QWidget) else None
    while current is not None and current is not settings:
        if isinstance(current, QFrame) and current.objectName() == "SettingsPremiumCard":
            return current
        current = current.parentWidget()
    return None


def _services_body(settings) -> tuple[QWidget | None, QVBoxLayout | None]:
    pages = getattr(settings, "settings_service_pages", None)
    page = pages.get("services") if isinstance(pages, dict) else None
    if not isinstance(page, QWidget):
        return None, None
    content = page.findChild(QWidget, "Settings2026DedicatedContent")
    body = content.layout() if content is not None else None
    return content, body if isinstance(body, QVBoxLayout) else None


def _remove_from_parent_layout(widget: QWidget) -> None:
    parent = widget.parentWidget()
    layout = parent.layout() if parent is not None else None
    if layout is not None:
        layout.removeWidget(widget)


def _find_runtime_index(body: QVBoxLayout) -> int:
    for index in range(body.count()):
        widget = body.itemAt(index).widget()
        if not isinstance(widget, QWidget):
            continue
        labels = {label.text().strip() for label in widget.findChildren(QLabel)}
        if "PrivacyGate runtime services" in labels:
            return index
    return max(0, body.count() - 2)


def _status_style(text: str, *, tone: str) -> str:
    palettes = {
        "green": ("#EAF8F1", GREEN, "#CDE8D9"),
        "amber": ("#FFF6E8", AMBER, "#F0D9B3"),
        "red": ("#FFF0F0", RED, "#E8C4C4"),
        "navy": ("#EEF3F7", NAVY, "#D8E2E9"),
    }
    bg, fg, border = palettes[tone]
    return (
        f"background:{bg};color:{fg};border:1px solid {border};border-radius:9px;"
        "padding:5px 8px;font-size:8px;font-weight:900;letter-spacing:.4px;"
    )


def _open_mcp_ai_direct(main_window) -> None:
    for index, button in enumerate(getattr(main_window, "nav_buttons", [])):
        label = (button.text() or button.toolTip() or "").strip().lower()
        if "mcp" in label and "ai direct" in label:
            main_window._show_page(index)
            return

    page = getattr(main_window, "cloud_automation_page", None)
    pages = getattr(main_window, "pages", None)
    if page is not None and pages is not None:
        index = pages.indexOf(page)
        if index >= 0:
            main_window._show_page(index)


def _build_browser_protection_card(main_window) -> QFrame:
    card = QFrame(objectName="SettingsBrowserProtection")
    card.setStyleSheet(
        "QFrame#SettingsBrowserProtection{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:16px;}"
    )
    box = QVBoxLayout(card)
    box.setContentsMargins(18, 15, 18, 15)
    box.setSpacing(10)

    head = QHBoxLayout()
    bubble = QLabel()
    bubble.setFixedSize(38, 38)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon("protect", color=TEAL, size=20).pixmap(20, 20))
    bubble.setStyleSheet("background:#EAF8F8;border:none;border-radius:11px;")
    head.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(2)
    title = QLabel("Browser Protection")
    title.setStyleSheet(f"color:{NAVY};font-size:14px;font-weight:900;border:none;")
    note = QLabel(
        "Protect prompts before they leave supported AI websites. The extension pairs with this device using a separate local credential."
    )
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
    copy.addWidget(title)
    copy.addWidget(note)
    head.addLayout(copy, 1)

    status = QLabel("CHECKING")
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status.setMinimumWidth(112)
    head.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
    box.addLayout(head)

    boundary = QLabel(
        "Local-only pairing • browser credential is separate from the main API bearer • prompts and restore mappings stay on this device"
    )
    boundary.setWordWrap(True)
    boundary.setStyleSheet(
        "background:#F1FAFA;color:#436677;border:1px solid #D5ECEC;border-radius:9px;"
        "padding:8px;font-size:8px;font-weight:700;"
    )
    box.addWidget(boundary)

    code_frame = QFrame()
    code_frame.setStyleSheet("QFrame{background:#F7FAFC;border:1px solid #E3EBEF;border-radius:12px;}")
    code_box = QHBoxLayout(code_frame)
    code_box.setContentsMargins(12, 10, 12, 10)
    code_copy = QVBoxLayout()
    code_copy.setSpacing(2)
    code_title = QLabel("One-time pairing code")
    code_title.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:800;border:none;")
    code_value = QLabel("—")
    code_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    code_value.setStyleSheet(f"color:{NAVY};font-size:20px;font-weight:950;letter-spacing:3px;border:none;")
    code_hint = QLabel("Create a code, then click the PrivacyGate extension icon and enter it there. Codes expire after 5 minutes.")
    code_hint.setWordWrap(True)
    code_hint.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
    code_copy.addWidget(code_title)
    code_copy.addWidget(code_value)
    code_copy.addWidget(code_hint)
    code_box.addLayout(code_copy, 1)
    box.addWidget(code_frame)

    actions = QHBoxLayout()
    actions.setSpacing(8)

    install_button = QPushButton("Install Extension")
    install_button.setIcon(icon("external", color=NAVY, size=15))
    install_button.setCursor(Qt.CursorShape.PointingHandCursor)
    install_button.setMinimumHeight(38)
    install_button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:9px;"
        "padding:8px 12px;font-size:10px;font-weight:800;}"
        "QPushButton:hover{background:#F2FAFA;border-color:#95C8CC;color:#0B7F89;}"
    )

    pair_button = QPushButton("Create pairing code")
    pair_button.setCursor(Qt.CursorShape.PointingHandCursor)
    pair_button.setMinimumHeight(38)
    pair_button.setStyleSheet(
        "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:9px;"
        "padding:8px 12px;font-size:10px;font-weight:850;}"
        "QPushButton:hover{background:#096D76;}QPushButton:disabled{background:#DDE6EA;color:#8FA0AA;}"
    )

    revoke_button = QPushButton("Revoke browser access")
    revoke_button.setCursor(Qt.CursorShape.PointingHandCursor)
    revoke_button.setMinimumHeight(38)
    revoke_button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#B54747;border:1px solid #E3CACA;border-radius:9px;"
        "padding:8px 12px;font-size:10px;font-weight:800;}"
        "QPushButton:hover{background:#FFF5F5;}QPushButton:disabled{color:#9AA8B1;border-color:#DFE5E8;}"
    )

    actions.addWidget(install_button)
    actions.addWidget(pair_button)
    actions.addWidget(revoke_button)
    actions.addStretch(1)
    box.addLayout(actions)

    manager = getattr(main_window, "local_api_manager", None)

    def install_extension() -> None:
        url = os.environ.get("PRIVACY_GATE_BROWSER_EXTENSION_URL", "").strip()
        if url:
            QDesktopServices.openUrl(QUrl(url))
            return
        QMessageBox.information(
            card,
            "Browser extension",
            "The browser-store listing is not configured in this development build yet. "
            "For the current FreeV1 test, keep using the unpacked PrivacyGate extension. "
            "The release build will open the official Edge Add-ons or Chrome Web Store page here.",
        )

    def create_pairing_code() -> None:
        if manager is None or getattr(manager.status, "state", "disabled") != "online":
            QMessageBox.warning(
                card,
                "Local Privacy Bridge is off",
                "Enable and save Local Privacy Bridge first, then create a browser pairing code.",
            )
            return
        challenge = manager.create_browser_pairing_code()
        code_value.setText(challenge.code)
        code_value.setFocus()

    def revoke_pairings() -> None:
        if manager is None:
            return
        answer = QMessageBox.question(
            card,
            "Revoke browser access",
            "Revoke all browser-extension credentials paired with this device? Browsers will need a new pairing code.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        manager.revoke_browser_pairings()
        code_value.setText("—")
        refresh_status()

    install_button.clicked.connect(install_extension)
    pair_button.clicked.connect(create_pairing_code)
    revoke_button.clicked.connect(revoke_pairings)

    def refresh_status() -> None:
        if manager is None:
            status.setText("UNAVAILABLE")
            status.setStyleSheet(_status_style("UNAVAILABLE", tone="red"))
            pair_button.setEnabled(False)
            revoke_button.setEnabled(False)
            return

        bridge_state = str(getattr(manager.status, "state", "disabled") or "disabled")
        pairing = manager.browser_pairing_status
        paired_count = int(getattr(pairing, "paired_count", 0))
        pair_button.setEnabled(bridge_state == "online")
        revoke_button.setEnabled(paired_count > 0)

        if bridge_state == "error":
            status.setText("BRIDGE ERROR")
            status.setStyleSheet(_status_style("BRIDGE ERROR", tone="red"))
        elif bridge_state != "online":
            status.setText("BRIDGE OFF")
            status.setStyleSheet(_status_style("BRIDGE OFF", tone="navy"))
        elif paired_count > 0:
            status.setText(f"PAIRED · {paired_count}")
            status.setStyleSheet(_status_style("PAIRED", tone="green"))
        else:
            status.setText("READY TO PAIR")
            status.setStyleSheet(_status_style("READY", tone="amber"))

    timer = QTimer(card)
    timer.setInterval(1200)
    timer.timeout.connect(refresh_status)
    timer.start()
    refresh_status()
    card._privacygate_browser_status_timer = timer
    card._privacygate_pairing_code_label = code_value
    return card


def _build_mcp_reference(main_window) -> QFrame:
    card = QFrame(objectName="SettingsMcpAiDirectReference")
    card.setStyleSheet(
        "QFrame#SettingsMcpAiDirectReference{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:16px;}"
    )
    box = QVBoxLayout(card)
    box.setContentsMargins(18, 15, 18, 15)
    box.setSpacing(10)

    head = QHBoxLayout()
    bubble = QLabel()
    bubble.setFixedSize(38, 38)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon("workflow", color=TEAL, size=20).pixmap(20, 20))
    bubble.setStyleSheet("background:#EAF8F8;border:none;border-radius:11px;")
    head.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(2)
    title = QLabel("MCP & AI Direct")
    title.setStyleSheet(f"color:{NAVY};font-size:14px;font-weight:900;border:none;")
    note = QLabel(
        "Your existing Remote MCP and Local MCP connections are managed in MCP AI Direct. "
        "This Settings page does not expose or change MCP connection controls."
    )
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
    copy.addWidget(title)
    copy.addWidget(note)
    head.addLayout(copy, 1)

    status = QLabel()
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status.setMinimumWidth(112)
    head.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
    box.addLayout(head)

    detail = QLabel("Protected Library boundary only • originals and restore mappings stay outside MCP")
    detail.setWordWrap(True)
    detail.setStyleSheet(
        "background:#F1FAFA;color:#436677;border:1px solid #D5ECEC;border-radius:9px;"
        "padding:8px;font-size:8px;font-weight:700;"
    )
    box.addWidget(detail)

    open_button = QPushButton("Open MCP AI Direct")
    open_button.setIcon(icon("external", color=NAVY, size=16))
    open_button.setCursor(Qt.CursorShape.PointingHandCursor)
    open_button.setMinimumHeight(38)
    open_button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:9px;"
        "padding:8px 12px;font-size:10px;font-weight:800;}"
        "QPushButton:hover{background:#F2FAFA;border-color:#95C8CC;color:#0B7F89;}"
    )
    open_button.clicked.connect(lambda: _open_mcp_ai_direct(main_window))
    box.addWidget(open_button, 0, Qt.AlignmentFlag.AlignLeft)

    def refresh_status() -> None:
        manager = getattr(main_window, "remote_mcp", None)
        remote = getattr(manager, "status", None)
        state = str(getattr(remote, "state", "stopped") or "stopped").lower()
        if state in {"online", "external"}:
            text, tone = "ONLINE", "green"
        elif state in {"starting", "reconnecting"}:
            text, tone = state.upper(), "amber"
        elif state == "error":
            text, tone = "ERROR", "red"
        else:
            text, tone = "OFFLINE", "navy"
        status.setText(text)
        status.setStyleSheet(_status_style(text, tone=tone))

    timer = QTimer(card)
    timer.setInterval(1500)
    timer.timeout.connect(refresh_status)
    timer.start()
    refresh_status()
    card._privacygate_status_timer = timer
    return card


def _hide_quick_mcp(settings) -> None:
    hub = getattr(settings, "settings_service_hub", None)
    if not isinstance(hub, QWidget):
        return
    for frame in hub.findChildren(QFrame, "SettingsGeneralQuickCard"):
        labels = {label.text().strip() for label in frame.findChildren(QLabel)}
        if "Local MCP service" in labels:
            frame.hide()
    for label in hub.findChildren(QLabel):
        if "MCP changes apply" in label.text():
            label.setText("Saved locally on this device.")


def _polish_services_copy(settings) -> None:
    pages = getattr(settings, "settings_service_pages", None)
    page = pages.get("services") if isinstance(pages, dict) else None
    if not isinstance(page, QWidget):
        return

    for label in page.findChildren(QLabel):
        text = label.text().strip()
        if text.startswith("Configure the local MCP endpoint"):
            label.setText(
                "Configure Local Privacy Bridge and Browser Protection for local-first AI privacy. "
                "MCP connections remain in MCP AI Direct."
            )

    for button in page.findChildren(QPushButton):
        text = button.text().strip()
        if text == "Cloud / MCP / Email":
            button.setText("MCP AI Direct")
        elif text == "Save service settings":
            button.setText("Save Privacy Bridge")

    hub = getattr(settings, "settings_service_hub", None)
    if isinstance(hub, QWidget):
        for frame in hub.findChildren(QFrame, "Settings2026HubCard"):
            labels = frame.findChildren(QLabel)
            if not any(label.text().strip() == "Services" for label in labels):
                continue
            for label in labels:
                if label.text().strip() == "MCP, automation and connections.":
                    label.setText("Browser protection, automation and connections.")


def _install_bridge_only_save(settings) -> None:
    """Make the Services save action persist only Local Privacy Bridge fields."""
    pages = getattr(settings, "settings_service_pages", None)
    page = pages.get("services") if isinstance(pages, dict) else None
    if not isinstance(page, QWidget):
        return

    save_button = None
    for button in page.findChildren(QPushButton):
        if button.text().strip() == "Save Privacy Bridge":
            save_button = button
            break
    if save_button is None:
        return

    try:
        save_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass

    def save_bridge() -> None:
        current = settings.store.load()
        enabled = bool(settings.local_api_enabled.isChecked())
        parsed_port = settings._local_api_port_value()

        if enabled and parsed_port is None:
            QMessageBox.warning(
                settings,
                "Invalid bridge port",
                "Enter a Local Privacy Bridge port between 1024 and 65535.",
            )
            return

        port = int(parsed_port) if parsed_port is not None else int(current.local_api_port)
        changed = enabled != current.local_api_enabled or port != current.local_api_port
        if not changed:
            QMessageBox.information(settings, "No changes", "There are no unsaved Privacy Bridge changes.")
            return

        updated = replace(current, local_api_enabled=enabled, local_api_port=port)
        settings.store.save(updated)
        settings.prefs = updated
        settings.preferences_changed.emit()
        settings.local_api_preferences_changed.emit()
        settings.refresh_local_api_status()
        QMessageBox.information(
            settings,
            "Privacy Bridge saved",
            "Local Privacy Bridge settings saved locally and applied immediately.",
        )

    save_button.clicked.connect(save_bridge)
    settings._privacygate_bridge_only_save = save_bridge


def apply_settings_services_cleanup_2026(main_window) -> None:
    """Give Bridge, Browser Protection and MCP one authoritative UI home each."""
    settings = getattr(main_window, "settings_page", None)
    if settings is None or bool(getattr(settings, "_privacygate_services_cleanup_2026", False)):
        return

    content, body = _services_body(settings)
    if content is None or body is None:
        return

    bridge = getattr(settings, "local_privacy_bridge_service_card", None)
    if not isinstance(bridge, QFrame):
        bridge = _card_from_control(settings, "local_api_enabled")
    if isinstance(bridge, QFrame):
        QCoreApplication.removePostedEvents(bridge, QEvent.Type.DeferredDelete)
        _remove_from_parent_layout(bridge)
        bridge.setParent(content)
        body.insertWidget(_find_runtime_index(body), bridge)
        bridge.show()
        settings.local_privacy_bridge_service_card = bridge

    existing_browser = content.findChild(QFrame, "SettingsBrowserProtection")
    if existing_browser is None:
        browser_card = _build_browser_protection_card(main_window)
        body.insertWidget(_find_runtime_index(body), browser_card)
        settings.browser_protection_service_card = browser_card

    mcp = getattr(settings, "local_mcp_service_card", None)
    if not isinstance(mcp, QFrame):
        mcp = _card_from_control(settings, "auto_port")
    if isinstance(mcp, QFrame):
        _remove_from_parent_layout(mcp)
        mcp.setParent(settings)
        mcp.hide()
        settings._privacygate_hidden_mcp_settings_card = mcp

    existing_reference = content.findChild(QFrame, "SettingsMcpAiDirectReference")
    if existing_reference is None:
        reference = _build_mcp_reference(main_window)
        body.insertWidget(_find_runtime_index(body), reference)

    _hide_quick_mcp(settings)
    _polish_services_copy(settings)
    _install_bridge_only_save(settings)
    settings._privacygate_services_cleanup_2026 = True
