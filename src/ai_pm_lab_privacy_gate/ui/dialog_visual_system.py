from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTextEdit,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
RED = "#B54747"
BORDER = "#DCE5EA"
SOFT = "#F7FAFC"
WHITE = "#FFFFFF"


_DIALOG_QSS = f"""
QDialog, QMessageBox {{
    background: {SOFT};
    color: {INK};
}}
QDialog QLabel, QMessageBox QLabel {{
    color: {INK};
    background: transparent;
}}
QDialog QLineEdit,
QDialog QPlainTextEdit,
QDialog QTextEdit,
QDialog QComboBox {{
    background: {WHITE};
    color: {INK};
    border: 1px solid #C7D5DE;
    border-radius: 9px;
    padding: 8px 10px;
    min-height: 22px;
    selection-background-color: #DDF1F2;
    selection-color: {NAVY};
}}
QDialog QLineEdit:focus,
QDialog QPlainTextEdit:focus,
QDialog QTextEdit:focus,
QDialog QComboBox:focus {{
    border: 1px solid {TEAL};
    background: #FFFFFF;
}}
QDialog QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QDialog QComboBox QAbstractItemView {{
    background: #FFFFFF;
    color: {INK};
    border: 1px solid {BORDER};
    selection-background-color: #E7F5F5;
    selection-color: {NAVY};
    padding: 5px;
    outline: 0;
}}
QDialog QCheckBox {{
    color: {INK};
    spacing: 8px;
    min-height: 24px;
}}
QDialog QCheckBox::indicator {{
    width: 17px;
    height: 17px;
}}
QDialog QCheckBox::indicator:unchecked {{
    background: #FFFFFF;
    border: 1px solid #B7C8D2;
    border-radius: 5px;
}}
QDialog QCheckBox::indicator:checked {{
    background: {TEAL};
    border: 1px solid {TEAL};
    border-radius: 5px;
}}
QDialog QTableWidget {{
    background: #FFFFFF;
    color: {INK};
    border: 1px solid {BORDER};
    border-radius: 9px;
    gridline-color: #E8EEF1;
    font-size: 10px;
    selection-background-color: #E7F5F5;
    selection-color: {NAVY};
}}
QDialog QTableWidget::item {{
    padding: 7px;
}}
QDialog QHeaderView::section {{
    background: #F5F8FA;
    color: #425D70;
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px;
    font-size: 9px;
    font-weight: 800;
}}
QDialog QPushButton#PrivacyGateDialogPrimary {{
    background: {TEAL};
    color: #FFFFFF;
    border: 1px solid {TEAL};
    border-radius: 9px;
    min-height: 38px;
    min-width: 92px;
    padding: 8px 14px;
    font-size: 10px;
    font-weight: 850;
}}
QDialog QPushButton#PrivacyGateDialogPrimary:hover {{
    background: #096D76;
    border-color: #096D76;
}}
QDialog QPushButton#PrivacyGateDialogPrimary:pressed {{
    background: #075F67;
    border-color: #075F67;
}}
QDialog QPushButton#PrivacyGateDialogSecondary {{
    background: #FFFFFF;
    color: {INK};
    border: 1px solid #C6D4DD;
    border-radius: 9px;
    min-height: 38px;
    min-width: 88px;
    padding: 8px 13px;
    font-size: 10px;
    font-weight: 800;
}}
QDialog QPushButton#PrivacyGateDialogSecondary:hover {{
    background: #EAF7F7;
    color: {TEAL};
    border-color: #91C8CC;
}}
QDialog QPushButton#PrivacyGateDialogDanger {{
    background: #FFFFFF;
    color: {RED};
    border: 1px solid #E3B5B5;
    border-radius: 9px;
    min-height: 38px;
    min-width: 92px;
    padding: 8px 13px;
    font-size: 10px;
    font-weight: 850;
}}
QDialog QPushButton#PrivacyGateDialogDanger:hover {{
    background: #FDEEEE;
    color: #923737;
    border-color: #D88F8F;
}}
QDialog QPushButton#PrivacyGateDialogSuccess {{
    background: {GREEN};
    color: #FFFFFF;
    border: 1px solid {GREEN};
    border-radius: 9px;
    min-height: 38px;
    min-width: 92px;
    padding: 8px 14px;
    font-size: 10px;
    font-weight: 850;
}}
QDialog QPushButton#PrivacyGateDialogSuccess:hover {{
    background: #1B6D3E;
    border-color: #1B6D3E;
}}
QDialog QPushButton:disabled {{
    background: #E5ECEF;
    color: #91A0AA;
    border-color: #D9E2E7;
}}
"""

_PRIMARY_WORDS = (
    "save",
    "ok",
    "yes",
    "apply",
    "continue",
    "create",
    "add",
    "invite",
    "connect",
    "authorize",
    "allow",
    "approve",
    "update",
    "install",
    "open",
    "browse",
    "import",
    "send",
    "use in protect",
    "keep running",
    "edit policy",
    "review policy",
    "manage",
)

_DANGER_WORDS = (
    "delete",
    "remove",
    "revoke",
    "disconnect",
    "disable",
    "quit",
    "sign out",
    "discard",
    "clear all",
    "reset",
)

_SECONDARY_WORDS = (
    "cancel",
    "close",
    "no",
    "back",
    "later",
    "skip",
    "not now",
    "refresh",
)

_SUCCESS_WORDS = (
    "done",
    "finish",
    "completed",
)


def _set_role(button: QPushButton, role: str) -> None:
    object_name = {
        "primary": "PrivacyGateDialogPrimary",
        "secondary": "PrivacyGateDialogSecondary",
        "danger": "PrivacyGateDialogDanger",
        "success": "PrivacyGateDialogSuccess",
    }[role]
    button.setObjectName(object_name)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(40)

    text = button.text().strip().lower()
    if role == "danger":
        button.setIcon(icon("power" if "quit" in text or "sign out" in text else "clear", color=RED, size=17))
    elif "save" in text:
        button.setIcon(icon("save", color="#FFFFFF" if role in {"primary", "success"} else INK, size=17))
    elif "open" in text or "browse" in text:
        button.setIcon(icon("external", color="#FFFFFF" if role in {"primary", "success"} else INK, size=17))
    elif "connect" in text or "authorize" in text:
        button.setIcon(icon("cloud", color="#FFFFFF" if role in {"primary", "success"} else INK, size=17))
    elif "policy" in text or "setting" in text:
        button.setIcon(icon("settings", color="#FFFFFF" if role in {"primary", "success"} else INK, size=17))
    elif "cancel" in text or "close" in text:
        button.setIcon(icon("clear", color=INK, size=16))
    elif role in {"primary", "success"}:
        button.setIcon(icon("check", color="#FFFFFF", size=17))


def _role_from_text(text: str) -> str:
    normalized = " ".join(text.lower().replace("&", " ").split())
    if any(word in normalized for word in _DANGER_WORDS):
        return "danger"
    if any(word in normalized for word in _SUCCESS_WORDS):
        return "success"
    if any(word in normalized for word in _SECONDARY_WORDS):
        return "secondary"
    if any(word in normalized for word in _PRIMARY_WORDS):
        return "primary"
    return "secondary"


def _role_from_standard(standard) -> str | None:
    if standard in {
        QDialogButtonBox.StandardButton.Save,
        QDialogButtonBox.StandardButton.SaveAll,
        QDialogButtonBox.StandardButton.Ok,
        QDialogButtonBox.StandardButton.Yes,
        QDialogButtonBox.StandardButton.YesToAll,
        QDialogButtonBox.StandardButton.Apply,
        QDialogButtonBox.StandardButton.Open,
    }:
        return "primary"
    if standard in {
        QDialogButtonBox.StandardButton.Discard,
        QDialogButtonBox.StandardButton.Abort,
    }:
        return "danger"
    if standard in {
        QDialogButtonBox.StandardButton.Cancel,
        QDialogButtonBox.StandardButton.Close,
        QDialogButtonBox.StandardButton.No,
        QDialogButtonBox.StandardButton.NoToAll,
        QDialogButtonBox.StandardButton.Ignore,
        QDialogButtonBox.StandardButton.Retry,
        QDialogButtonBox.StandardButton.Reset,
        QDialogButtonBox.StandardButton.RestoreDefaults,
    }:
        return "secondary"
    return None


def _rename_context_buttons(dialog: QDialog) -> None:
    title = dialog.windowTitle().lower()
    for box in dialog.findChildren(QDialogButtonBox):
        save = box.button(QDialogButtonBox.StandardButton.Save)
        ok = box.button(QDialogButtonBox.StandardButton.Ok)
        if "policy" in title and save is not None:
            save.setText("Save policy")
        elif "workspace permissions" in title and save is not None:
            save.setText("Save permissions")
        elif isinstance(dialog, QInputDialog) and ("name" in title or "account" in title):
            target = ok or save
            if target is not None:
                target.setText("Save name")


def _style_buttons(dialog: QDialog) -> None:
    handled: set[int] = set()
    for box in dialog.findChildren(QDialogButtonBox):
        for standard in QDialogButtonBox.StandardButton:
            if standard == QDialogButtonBox.StandardButton.NoButton:
                continue
            button = box.button(standard)
            if button is None:
                continue
            handled.add(id(button))
            role = _role_from_standard(standard) or _role_from_text(button.text())
            _set_role(button, role)

    if isinstance(dialog, QMessageBox):
        affirmative = {
            QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Save,
            QMessageBox.StandardButton.Apply,
        }
        destructive = {
            QMessageBox.StandardButton.Discard,
            QMessageBox.StandardButton.Abort,
        }
        for button in dialog.buttons():
            if not isinstance(button, QPushButton):
                continue
            handled.add(id(button))
            standard = dialog.standardButton(button)
            if standard in destructive:
                role = "danger"
            elif standard in affirmative or button is dialog.defaultButton():
                role = "primary"
            else:
                role = _role_from_text(button.text())
            _set_role(button, role)

    for button in dialog.findChildren(QPushButton):
        if id(button) in handled:
            continue
        _set_role(button, _role_from_text(button.text()))


def _polish_dialog(dialog: QDialog) -> None:
    try:
        if not bool(dialog.property("privacygatePremiumDialogStyled")):
            dialog.setProperty("privacygatePremiumDialogStyled", True)
            dialog.setStyleSheet(dialog.styleSheet() + _DIALOG_QSS)

        title = dialog.windowTitle().lower()
        if isinstance(dialog, QMessageBox):
            dialog.setMinimumWidth(max(dialog.minimumWidth(), 500))
        elif isinstance(dialog, QInputDialog):
            dialog.setMinimumWidth(max(dialog.minimumWidth(), 520))
        elif "workspace permissions" in title:
            dialog.setMinimumWidth(max(dialog.minimumWidth(), 560))
        elif "policy" in title:
            dialog.setMinimumWidth(max(dialog.minimumWidth(), 820))
        elif dialog.width() < 460:
            dialog.setMinimumWidth(max(dialog.minimumWidth(), 460))

        _rename_context_buttons(dialog)
        _style_buttons(dialog)

        for edit in dialog.findChildren(QLineEdit):
            edit.setMinimumHeight(max(edit.minimumHeight(), 40))
        for combo in dialog.findChildren(QComboBox):
            combo.setMinimumHeight(max(combo.minimumHeight(), 40))
        for text in dialog.findChildren((QPlainTextEdit, QTextEdit)):
            text.setMinimumHeight(max(text.minimumHeight(), 90))
        for table in dialog.findChildren(QTableWidget):
            table.verticalHeader().setDefaultSectionSize(max(34, table.verticalHeader().defaultSectionSize()))
        for check in dialog.findChildren(QCheckBox):
            check.setMinimumHeight(max(check.minimumHeight(), 26))
        for label in dialog.findChildren(QLabel):
            if label.wordWrap():
                label.setMinimumWidth(min(360, max(0, label.minimumWidth())))
    except RuntimeError:
        return


class _PremiumDialogFilter(QObject):
    def eventFilter(self, watched, event):  # noqa: N802 - Qt API
        if event.type() == QEvent.Type.Show and isinstance(watched, QDialog):
            # Run after existing dialog-specific setup and the older popup polish.
            QTimer.singleShot(0, lambda target=watched: _polish_dialog(target))
            QTimer.singleShot(90, lambda target=watched: _polish_dialog(target))
        return super().eventFilter(watched, event)


def apply_dialog_visual_system(main_window) -> None:
    """Install one consistent premium visual system for every PrivacyGate dialog.

    This affects presentation only: QMessageBox, QInputDialog, policy editors,
    workspace-permission dialogs, connector dialogs and other QDialog subclasses
    keep their existing actions and data flow.
    """

    app = QApplication.instance()
    if app is None or getattr(app, "_privacygate_premium_dialog_filter", None) is not None:
        return
    event_filter = _PremiumDialogFilter(app)
    app.installEventFilter(event_filter)
    app._privacygate_premium_dialog_filter = event_filter
