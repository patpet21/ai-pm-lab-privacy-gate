from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

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
        if state == "online":
            text, bg, fg, border = "ONLINE", "#EAF8F1", GREEN, "#CDE8D9"
        elif state in {"starting", "reconnecting"}:
            text, bg, fg, border = state.upper(), "#FFF6E8", AMBER, "#F0D9B3"
        elif state == "error":
            text, bg, fg, border = "ERROR", "#FFF0F0", RED, "#E8C4C4"
        else:
            text, bg, fg, border = "OFFLINE", "#EEF3F7", NAVY, "#D8E2E9"
        status.setText(text)
        status.setStyleSheet(
            f"background:{bg};color:{fg};border:1px solid {border};border-radius:9px;"
            "padding:5px 8px;font-size:8px;font-weight:900;letter-spacing:.4px;"
        )

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
                "Configure Local Privacy Bridge for browser and local automation protection. "
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


def apply_settings_services_cleanup_2026(main_window) -> None:
    """Give Bridge and MCP one authoritative UI home each.

    Local Privacy Bridge reuses the original SettingsPage card and preference model.
    The duplicate editable MCP settings surface is hidden; the real MCP remains in
    MCP AI Direct. This function also cancels the DeferredDelete posted by older
    Settings composition layers for the Bridge card.
    """
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
    settings._privacygate_services_cleanup_2026 = True
