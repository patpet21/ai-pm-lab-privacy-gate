from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_transport import (
    CONFIG_FILENAME,
    GmailAddonTransport,
    MODE_ACTION,
    MODE_READONLY,
)
from ai_pm_lab_privacy_gate.ui.gmail_addon_import import _data_dir, open_gmail_addon_import
from ai_pm_lab_privacy_gate.ui.gmail_addon_readonly_import import open_gmail_readonly_import


NAVY = "#062B4F"
MUTED = "#607789"
PETROL = "#0B7180"


def _config_path(main_window) -> Path:
    return Path(_data_dir(main_window)) / CONFIG_FILENAME


def get_active_gmail_mode(main_window) -> str:
    path = _config_path(main_window)
    try:
        raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        mode = str(raw.get("active_mode") or MODE_ACTION).strip().lower()
        return mode if mode in {MODE_ACTION, MODE_READONLY} else MODE_ACTION
    except Exception:
        return MODE_ACTION


def set_active_gmail_mode(main_window, mode: str) -> None:
    normalized = str(mode or MODE_ACTION).strip().lower()
    if normalized not in {MODE_ACTION, MODE_READONLY}:
        normalized = MODE_ACTION
    path = _config_path(main_window)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(raw, dict):
            raw = {}
    except Exception:
        raw = {}
    raw["active_mode"] = normalized
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def open_configured_gmail_import(main_window) -> None:
    if get_active_gmail_mode(main_window) == MODE_READONLY:
        open_gmail_readonly_import(main_window)
    else:
        open_gmail_addon_import(main_window)


def _status_text(transport: GmailAddonTransport) -> tuple[str, str]:
    if transport.endpoint and transport.paired:
        return "CONNECTED", "#E8F6F6;color:#0B7180;border:1px solid #B8E1E4"
    if transport.endpoint:
        return "PAIR DEVICE", "#FFF8E8;color:#7A5B16;border:1px solid #EFD79A"
    return "SETUP", "#F1F5F8;color:#607789;border:1px solid #D7E2EA"


def _mode_row(
    title: str,
    description: str,
    permission: str,
    status: tuple[str, str],
    active: bool,
) -> tuple[QFrame, QPushButton, QPushButton]:
    row = QFrame(objectName="GmailModeRow")
    row.setStyleSheet(
        "QFrame#GmailModeRow{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:11px;}"
    )
    layout = QHBoxLayout(row)
    layout.setContentsMargins(16, 13, 14, 13)
    layout.setSpacing(14)

    copy = QVBoxLayout()
    copy.setSpacing(4)
    head = QHBoxLayout()
    name = QLabel(title)
    name.setStyleSheet(f"color:{NAVY};font-size:14px;font-weight:900;")
    head.addWidget(name)
    if active:
        current = QLabel("CURRENT")
        current.setStyleSheet(
            "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
            "border-radius:7px;padding:3px 7px;font-size:8px;font-weight:900;"
        )
        head.addWidget(current)
    head.addStretch(1)
    copy.addLayout(head)

    desc = QLabel(description)
    desc.setWordWrap(True)
    desc.setStyleSheet(f"color:{MUTED};font-size:10px;")
    copy.addWidget(desc)

    scope = QLabel(permission)
    scope.setWordWrap(True)
    scope.setStyleSheet("color:#7A8E9D;font-size:8px;")
    copy.addWidget(scope)
    layout.addLayout(copy, 1)

    actions = QVBoxLayout()
    actions.setSpacing(7)
    status_label = QLabel(status[0])
    status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status_label.setStyleSheet(
        f"background:{status[1]};border-radius:7px;padding:4px 7px;font-size:8px;font-weight:900;"
    )
    actions.addWidget(status_label)

    manage = QPushButton("Manage")
    manage.setMinimumWidth(108)
    manage.setMinimumHeight(34)
    manage.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #B9CAD5;"
        "border-radius:8px;padding:7px 11px;font-weight:800;}"
        "QPushButton:hover{background:#F4F8FA;}"
    )
    actions.addWidget(manage)

    use = QPushButton("Use for imports" if not active else "Selected")
    use.setEnabled(not active)
    use.setMinimumWidth(108)
    use.setMinimumHeight(34)
    use.setStyleSheet(
        "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
        "border-radius:8px;padding:7px 11px;font-weight:800;}"
        "QPushButton:disabled{background:#E8F6F6;color:#0B7180;border-color:#B8E1E4;}"
    )
    actions.addWidget(use)
    layout.addLayout(actions)
    return row, manage, use


def open_gmail_mode_picker(main_window) -> None:
    """Manage Gmail add-on access modes from Apps."""
    action_transport = GmailAddonTransport(_data_dir(main_window), mode=MODE_ACTION)
    readonly_transport = GmailAddonTransport(_data_dir(main_window), mode=MODE_READONLY)
    active = get_active_gmail_mode(main_window)

    dialog = QDialog(main_window)
    dialog.setObjectName("GmailModePicker")
    dialog.setWindowTitle("Gmail integration")
    dialog.resize(760, 520)
    dialog.setMinimumSize(700, 500)
    dialog.setStyleSheet("QDialog#GmailModePicker{background:#F8FBFC;}")

    root = QVBoxLayout(dialog)
    root.setContentsMargins(24, 22, 24, 20)
    root.setSpacing(13)

    title = QLabel("Gmail integration")
    title.setStyleSheet(f"color:{NAVY};font-size:22px;font-weight:950;")
    subtitle = QLabel(
        "Configure Gmail here once. Protect will then use the Gmail mode selected below automatically."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;")
    root.addWidget(title)
    root.addWidget(subtitle)

    explainer = QLabel(
        "Standard requires an explicit “Send to PrivacyGate” click in Gmail. Enhanced can preview the currently open email inside the Gmail sidebar before you import it. After import, both use the same local Protect workflow."
    )
    explainer.setWordWrap(True)
    explainer.setStyleSheet(
        "background:#EEF7F7;color:#214B55;border:1px solid #CDE5E7;"
        "border-radius:9px;padding:10px;font-size:9px;font-weight:650;"
    )
    root.addWidget(explainer)

    standard_row, standard_manage, standard_use = _mode_row(
        "Standard",
        "Open a message in Gmail, then press “Send to PrivacyGate”. Only after that action can the add-on transfer the selected email.",
        "Google permission: gmail.addons.current.message.action",
        _status_text(action_transport),
        active == MODE_ACTION,
    )
    enhanced_row, enhanced_manage, enhanced_use = _mode_row(
        "Enhanced preview",
        "Open a message and the PrivacyGate Gmail sidebar can already show its subject, sender and body before you choose to import it.",
        "Google permission: gmail.addons.current.message.readonly",
        _status_text(readonly_transport),
        active == MODE_READONLY,
    )
    root.addWidget(standard_row)
    root.addWidget(enhanced_row)

    steps = QLabel(
        "Connection: click Manage on the mode you want → configure its Apps Script deployment if required → pair this device once → install/open that PrivacyGate add-on in Gmail. Enhanced uses its own deployment and does not replace Standard."
    )
    steps.setWordWrap(True)
    steps.setStyleSheet("color:#607789;font-size:9px;")
    root.addWidget(steps)
    root.addStretch(1)

    close = QPushButton("Close")
    close.setMinimumHeight(36)
    close.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C4D3DE;"
        "border-radius:8px;padding:7px 14px;font-weight:800;}"
    )
    root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def choose(mode: str) -> None:
        set_active_gmail_mode(main_window, mode)
        dialog.accept()
        open_gmail_mode_picker(main_window)

    def manage(mode: str) -> None:
        set_active_gmail_mode(main_window, mode)
        dialog.accept()
        if mode == MODE_READONLY:
            open_gmail_readonly_import(main_window)
        else:
            open_gmail_addon_import(main_window)

    standard_use.clicked.connect(lambda: choose(MODE_ACTION))
    enhanced_use.clicked.connect(lambda: choose(MODE_READONLY))
    standard_manage.clicked.connect(lambda: manage(MODE_ACTION))
    enhanced_manage.clicked.connect(lambda: manage(MODE_READONLY))
    close.clicked.connect(dialog.reject)
    dialog.exec()
