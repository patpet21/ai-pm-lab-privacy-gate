from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractButton, QTabWidget, QWidget

from ai_pm_lab_privacy_gate.ui.iconography import icon, _icon_for_text
from ai_pm_lab_privacy_gate.ui.brand_palette import NAVY_SOFT, PETROL, WHITE


def _stateful_icon(name: str, size: int = 18) -> QIcon:
    """Navy/teal when idle, white when selected or active."""
    normal = icon(name, color=NAVY_SOFT, size=size).pixmap(size, size)
    selected = icon(name, color=WHITE, size=size).pixmap(size, size)
    result = QIcon()
    result.addPixmap(normal, QIcon.Mode.Normal, QIcon.State.Off)
    result.addPixmap(selected, QIcon.Mode.Normal, QIcon.State.On)
    result.addPixmap(selected, QIcon.Mode.Active, QIcon.State.On)
    result.addPixmap(selected, QIcon.Mode.Selected, QIcon.State.Off)
    result.addPixmap(selected, QIcon.Mode.Selected, QIcon.State.On)
    return result


def _solid_icon(name: str, color: str, size: int = 18) -> QIcon:
    return icon(name, color=color, size=size)


def _button_icon_color(button: QAbstractButton) -> str:
    name = button.objectName().lower()
    text = " ".join(button.text().lower().split())
    if name == "navbutton":
        return WHITE
    if name in {"primary", "gold"}:
        return WHITE
    if any(
        phrase in text
        for phrase in (
            "protect document",
            "restore locally",
            "restore your file",
            "scan locally",
            "scan for sensitive data",
            "save + copy",
            "save + download",
            "send request",
        )
    ):
        return WHITE
    return NAVY_SOFT


def apply_brand_icons(root: QWidget) -> None:
    """Apply only icon/color treatment; no geometry or behavior changes."""
    for button in root.findChildren(QAbstractButton):
        key = _icon_for_text(button.text())
        if not key:
            continue
        if button.isCheckable():
            button.setIcon(_stateful_icon(key, 18))
        else:
            button.setIcon(_solid_icon(key, _button_icon_color(button), 18))
        button.setIconSize(QSize(18, 18))

    nav = {
        "Protect": "protect",
        "Library": "library",
        "Restore": "restore",
        "Local Automation / n8n": "workflow",
        "Cloud / MCP / Email": "cloud",
        "Settings": "settings",
        "Contact / Workflows": "contact",
        "History": "history",
        "Templates": "template",
        "Local Library": "library",
        "Reports": "report",
    }
    for button in root.findChildren(QAbstractButton):
        key = nav.get(button.text())
        if key:
            button.setIcon(_solid_icon(key, WHITE, 20))
            button.setIconSize(QSize(20, 20))

    for tabs in root.findChildren(QTabWidget):
        for index in range(tabs.count()):
            key = _icon_for_text(tabs.tabText(index))
            if key:
                normal = icon(key, color=PETROL, size=17).pixmap(17, 17)
                selected = icon(key, color=WHITE, size=17).pixmap(17, 17)
                tab_icon = QIcon()
                tab_icon.addPixmap(normal, QIcon.Mode.Normal, QIcon.State.Off)
                tab_icon.addPixmap(selected, QIcon.Mode.Selected, QIcon.State.Off)
                tab_icon.addPixmap(selected, QIcon.Mode.Active, QIcon.State.Off)
                tabs.setTabIcon(index, tab_icon)
