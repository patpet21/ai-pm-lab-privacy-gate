from __future__ import annotations

"""Approved visual treatment for the upper Protect controls.

This module deliberately owns presentation only. Existing Upload, connected-source,
Paste, Scan/Protect, workspace-policy, Gmail/Drive and preview controllers remain
the source of behavior.
"""

import re

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QLayout, QPushButton, QWidget

from ai_pm_lab_privacy_gate.ui.iconography import icon


NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B858A"
TEAL_DARK = "#096E75"
MUTED = "#61798A"
BORDER = "#D4E1E9"
SOFT = "#F8FBFC"

# Protect-only typography pilot. The rest of the application intentionally keeps
# its existing sizing until this visual scale is approved. Most inherited text is
# already 10pt (~13 px); the readability problem comes from local Protect styles
# that intentionally compressed helper/control copy down to 7-12 px.
_FONT_SIZE_RE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.IGNORECASE)


def _pilot_font_size(value: float) -> float:
    """Map legacy micro type to a compact but readable Protect scale."""
    if value <= 8:
        return 11
    if value <= 9:
        return 12
    if value <= 11:
        return 13
    if value <= 13:
        return 14
    return value


def _scaled_style_sheet(style: str) -> str:
    def replace(match: re.Match[str]) -> str:
        current = float(match.group(1))
        upgraded = _pilot_font_size(current)
        rendered = str(int(upgraded)) if upgraded.is_integer() else f"{upgraded:g}"
        return f"font-size:{rendered}px"

    return _FONT_SIZE_RE.sub(replace, style)


def _apply_typography_pilot(page) -> None:
    """Increase only Protect's explicit micro-fonts without changing layout logic.

    The pass is intentionally stylesheet-preserving: colors, spacing, borders,
    weights and widget behavior stay untouched. A cached applied stylesheet makes
    repeated calls idempotent while still allowing a later compatibility layer to
    restyle a widget and be upgraded on the next pass.
    """
    widgets = (page, *page.findChildren(QWidget))
    for widget in widgets:
        style = widget.styleSheet()
        if not style:
            continue
        last_applied = getattr(widget, "_privacygate_protect_typography_style", None)
        if style == last_applied:
            continue
        upgraded = _scaled_style_sheet(style)
        if upgraded != style:
            widget.setStyleSheet(upgraded)
        widget._privacygate_protect_typography_style = upgraded


def _stateful_icon(name: str, size: int = 19) -> QIcon:
    normal = icon(name, color=NAVY, size=size).pixmap(size, size)
    selected = icon(name, color="#FFFFFF", size=size).pixmap(size, size)
    value = QIcon()
    value.addPixmap(normal, QIcon.Mode.Normal, QIcon.State.Off)
    value.addPixmap(selected, QIcon.Mode.Normal, QIcon.State.On)
    value.addPixmap(selected, QIcon.Mode.Active, QIcon.State.On)
    value.addPixmap(selected, QIcon.Mode.Selected, QIcon.State.On)
    return value


def _find_layout(layout: QLayout | None, widget) -> QLayout | None:
    if layout is None:
        return None
    if layout.indexOf(widget) >= 0:
        return layout
    for index in range(layout.count()):
        child = layout.itemAt(index).layout()
        found = _find_layout(child, widget)
        if found is not None:
            return found
    return None


def _style_combo(combo: QComboBox) -> None:
    combo.setMinimumHeight(43)
    combo.setStyleSheet(
        "QComboBox{background:#FFFFFF;color:#102F49;border:1px solid #C9D9E4;"
        "border-radius:9px;padding:7px 10px;font-size:11px;font-weight:650;}"
        "QComboBox:hover{border-color:#95C5CA;background:#FCFFFF;}"
        "QComboBox:focus{border-color:#55AEB5;}"
        "QComboBox QAbstractItemView{background:#FFFFFF;color:#17384E;"
        "border:1px solid #C9D9E4;selection-background-color:#E7F5F5;"
        "selection-color:#062B4F;padding:4px;}"
    )


def _style_workspace_context(page) -> None:
    bar = getattr(page, "_managed_workspace_context_bar", None)
    if bar is None:
        return

    bar.setStyleSheet(
        "QFrame#ManagedProtectContextBar{background:#FBFEFE;border:1px solid #D3E5E7;"
        "border-radius:12px;}"
    )
    root = bar.layout()
    if root is not None:
        root.setContentsMargins(14, 11, 14, 11)
        root.setSpacing(8)

    for label in bar.findChildren(QLabel):
        text = label.text().strip()
        if text == "WORKSPACE CONTEXT":
            label.setStyleSheet(
                f"color:{TEAL_DARK};font-size:10px;font-weight:950;"
                "border:none;background:transparent;"
            )
        elif text.startswith("Personal or company context"):
            label.setStyleSheet(
                f"color:{MUTED};font-size:8px;font-weight:550;"
                "border:none;background:transparent;"
            )
        elif text == "Connected source":
            label.setText("Connected content source")
            label.setStyleSheet(
                f"color:{NAVY};font-size:8px;font-weight:900;"
                "border:none;background:transparent;"
            )
            if getattr(bar, "_privacygate_source_helper", None) is None:
                helper = QLabel(
                    "Source of the content you browse/import (e.g., Gmail, Drive)", bar
                )
                helper.setStyleSheet(
                    f"color:{MUTED};font-size:7px;font-weight:550;"
                    "border:none;background:transparent;"
                )
                helper.setToolTip(
                    "Choose which connected app PrivacyGate should browse for content to import locally."
                )
                source_layout = _find_layout(root, label)
                if source_layout is not None:
                    source_layout.insertWidget(1, helper)
                    bar._privacygate_source_helper = helper
        elif text in {"Workspace", "Account"}:
            label.setStyleSheet(
                f"color:{NAVY};font-size:8px;font-weight:900;"
                "border:none;background:transparent;"
            )

    for combo in (bar.workspace_combo, bar.source_combo, bar.account_combo):
        _style_combo(combo)

    bar.source_combo.setToolTip(
        "Connected content source — choose Gmail, Google Drive, or another connected provider to browse/import from."
    )
    bar.account_combo.setToolTip(
        "Connected account used for the selected content source."
    )

    bar.manage.setMinimumHeight(40)
    bar.manage.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D9E4;"
        "border-radius:9px;padding:8px 13px;font-size:9px;font-weight:850;}"
        "QPushButton:hover{background:#F3FAFA;border-color:#9CCFD3;color:#0B7180;}"
    )

    bar.policy.setMinimumHeight(43)
    bar.policy.setStyleSheet(
        "background:#FFFFFF;color:#17384E;border:1px solid #D8E4EB;border-radius:9px;"
        "padding:8px 10px;font-size:7px;font-weight:750;"
    )

    bar.browse.setMinimumHeight(44)
    bar.browse.setMinimumWidth(225)
    bar.browse.setStyleSheet(
        f"QPushButton{{background:{TEAL};color:#FFFFFF;border:1px solid {TEAL};"
        "border-radius:9px;padding:9px 14px;font-size:9px;font-weight:900;}"
        f"QPushButton:hover{{background:{TEAL_DARK};border-color:{TEAL_DARK};}}"
        "QPushButton:disabled{background:#C9D7DD;color:#F2F6F7;border-color:#C9D7DD;}"
    )


def _secondary_style() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#102F49;border:1px solid #C9D9E4;"
        "border-radius:9px;padding:8px 15px;font-size:10px;font-weight:850;}"
        "QPushButton:hover{background:#F2FAFA;border-color:#91C8CC;color:#0B7180;}"
        "QPushButton:pressed{background:#E8F5F5;}"
    )


def _style_quick_actions(page) -> None:
    bar = getattr(page, "_protect_source_quick_bar", None)
    if bar is None:
        return

    bar.setStyleSheet(
        "QFrame#ProtectSourceQuickBar{background:#FFFFFF;border:1px solid #D7E2EA;"
        "border-radius:11px;}"
    )
    layout = bar.layout()
    if layout is not None:
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(10)

    upload = getattr(page, "_protect_source_upload", None)
    connected = getattr(page, "_protect_source_connected", None)
    paste = getattr(page, "_protect_source_paste", None)
    scan = getattr(page, "_protect_source_scan", None)
    protect = getattr(page, "_protect_source_protect", None)

    for button in (upload, connected, paste):
        if button is None:
            continue
        button.setMinimumHeight(42)
        button.setStyleSheet(_secondary_style())
        button.setCursor(Qt.CursorShape.PointingHandCursor)

    if upload is not None:
        upload.setMinimumWidth(120)
        upload.setIcon(icon("upload", color=TEAL, size=19))
        upload.setIconSize(QSize(19, 19))
        upload.setToolTip(
            "Upload a local PDF, Word, Excel, PowerPoint or TXT file. The original stays on this device."
        )

    if connected is not None:
        connected.setMinimumWidth(190)
        connected.setIcon(icon("cloud", color=NAVY, size=19))
        connected.setIconSize(QSize(19, 19))
        connected.setToolTip(
            "Browse content from connected apps such as Gmail or Google Drive. The number shows how many providers are connected."
        )

    if paste is not None:
        paste.setMinimumWidth(130)
        paste.setIcon(icon("paste", color=NAVY, size=19))
        paste.setIconSize(QSize(19, 19))
        paste.setToolTip("Paste text directly into this local Protect session.")

    if protect is not None:
        # One workflow, one primary action. Keep the compatibility button alive
        # because old controllers may still reference it, but never paint it.
        protect.hide()
        protect.setMaximumWidth(0)

    if scan is not None:
        scan.setText("Scan & Protect")
        scan.setMinimumHeight(45)
        scan.setMinimumWidth(220)
        scan.setIcon(icon("protect", color="#FFFFFF", size=20))
        scan.setIconSize(QSize(20, 20))
        scan.setCursor(Qt.CursorShape.PointingHandCursor)
        scan.setToolTip(
            "Scan every selected source locally, create the protected copy, then run the local Privacy Check."
        )
        scan.setStyleSheet(
            f"QPushButton{{background:{TEAL};color:#FFFFFF;border:1px solid {TEAL};"
            "border-radius:9px;padding:9px 18px;font-size:11px;font-weight:950;}"
            f"QPushButton:hover{{background:{TEAL_DARK};border-color:{TEAL_DARK};}}"
            "QPushButton:disabled{background:#C7D5DB;color:#F2F5F6;border-color:#C7D5DB;}"
        )


def _style_source_view_controls(page) -> None:
    document = getattr(page, "_redesign_document_mode", None)
    paste = getattr(page, "_redesign_paste_mode", None)
    for button, icon_name in ((document, "document"), (paste, "paste")):
        if button is None:
            continue
        button.setMinimumHeight(40)
        button.setMinimumWidth(150)
        button.setIcon(_stateful_icon(icon_name, 18))
        button.setIconSize(QSize(18, 18))
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #CFDCE5;"
            "border-radius:8px;padding:7px 14px;font-size:10px;font-weight:850;}"
            f"QPushButton:hover{{background:#F2FAFA;border-color:#9CCFD3;color:{TEAL_DARK};}}"
            f"QPushButton:checked{{background:{TEAL};color:#FFFFFF;border-color:{TEAL};}}"
        )

    # Some compatibility layers expose Protected text / Compare as buttons rather
    # than native QTabBar tabs. Style only exact labels so unrelated controls are
    # untouched.
    for button in page.findChildren(QPushButton):
        text = " ".join(button.text().split())
        if text not in {"Protected text", "Compare"}:
            continue
        button.setMinimumHeight(40)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #CFDCE5;"
            "border-radius:8px;padding:7px 14px;font-size:10px;font-weight:850;}"
            f"QPushButton:hover{{background:#F2FAFA;border-color:#9CCFD3;color:{TEAL_DARK};}}"
            f"QPushButton:checked{{background:{TEAL};color:#FFFFFF;border-color:{TEAL};}}"
        )

    mode_bar = getattr(page, "_polish_protect_mode_bar", None)
    if mode_bar is not None:
        mode_bar.setStyleSheet(
            "QFrame#ProtectModeBar{background:#FBFDFE;border:1px solid #D7E2EA;"
            "border-radius:10px;}"
        )
        mode_layout = mode_bar.layout()
        if mode_layout is not None:
            mode_layout.setContentsMargins(10, 7, 10, 7)
            mode_layout.setSpacing(8)


def _style_gmail_strip(page) -> None:
    strip = getattr(page, "_gmail_component_strip", None)
    if strip is None:
        return
    strip.setStyleSheet(
        "QFrame#GmailComponentStrip{background:#FBFDFE;border:1px solid #D7E3EA;"
        "border-radius:10px;}"
    )
    layout = strip.layout()
    if layout is not None:
        layout.setContentsMargins(11, 7, 11, 7)
        layout.setSpacing(9)
    for button in getattr(page, "_gmail_component_buttons", {}).values():
        button.setMinimumHeight(34)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#35536A;border:1px solid #D4E0E8;"
            "border-radius:8px;padding:6px 11px;font-size:9px;font-weight:800;text-align:left;}"
            "QPushButton:hover{background:#F1F7FA;border-color:#9FC7CF;}"
            f"QPushButton:checked{{background:{TEAL};color:#FFFFFF;border-color:{TEAL};}}"
        )


def apply_protect_top_area_design(main_window) -> None:
    """Apply the approved Protect top-area mockup without changing behavior."""
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_privacygate_top_area_design", False):
        return
    page._privacygate_top_area_design = True

    _style_workspace_context(page)
    _style_quick_actions(page)
    _style_source_view_controls(page)
    _style_gmail_strip(page)
    _apply_typography_pilot(page)

    # Later Protect presentation layers run synchronously after this one. Apply
    # the pilot once more on the next event-loop turn so their 8-12 px helper text
    # receives the same scale without touching any page outside Protect.
    QTimer.singleShot(0, lambda: _apply_typography_pilot(page))

    # Gmail components are created only after a message package is imported.
    # Refresh through the existing source-selector callback instead of running a
    # new visual timer.
    original_select = getattr(page, "_gmail_component_select", None)
    if callable(original_select) and not getattr(page, "_privacygate_top_area_gmail_wrapped", False):
        page._privacygate_top_area_gmail_wrapped = True

        def select_and_style(key: str):
            value = original_select(key)
            _style_gmail_strip(page)
            _apply_typography_pilot(page)
            return value

        page._gmail_component_select = select_and_style
