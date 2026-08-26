from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QIcon
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
    QSizePolicy,
    QTableWidget,
    QTextEdit,
)

# Modern PrivacyGate modal language: light surfaces, soft borders, generous
# spacing and a restrained teal accent. This deliberately avoids the heavy,
# high-contrast "desktop utility" look while keeping every existing dialog's
# behavior and data flow intact.
NAVY = "#0B2D45"
INK = "#17384E"
MUTED = "#6B7F8E"
TEAL = "#0F9CA3"
TEAL_DARK = "#0B7D86"
TEAL_SOFT = "#E9F8F8"
BORDER = "#DCE6EB"
BORDER_SOFT = "#E8EEF2"
SURFACE = "#FFFFFF"
CANVAS = "#F8FAFC"
FIELD = "#FBFCFD"
GREEN = "#24865D"
RED = "#C94F55"
RED_SOFT = "#FFF1F1"


_DIALOG_QSS = f"""
QDialog, QMessageBox {{
    background: {CANVAS};
    color: {INK};
}}
QDialog QLabel, QMessageBox QLabel {{
    color: {INK};
    background: transparent;
    font-size: 10px;
}}
QMessageBox QLabel#qt_msgbox_label {{
    color: {NAVY};
    font-size: 13px;
    font-weight: 800;
}}
QMessageBox QLabel#qt_msgbox_informativelabel {{
    color: {MUTED};
    font-size: 10px;
    font-weight: 500;
}}
QInputDialog QLabel {{
    color: {NAVY};
    font-size: 11px;
    font-weight: 700;
}}
QDialog QLineEdit,
QDialog QPlainTextEdit,
QDialog QTextEdit,
QDialog QComboBox {{
    background: {FIELD};
    color: {INK};
    border: 1px solid #D4E0E6;
    border-radius: 11px;
    padding: 9px 11px;
    min-height: 24px;
    font-size: 11px;
    selection-background-color: #DDF3F3;
    selection-color: {NAVY};
}}
QDialog QLineEdit:hover,
QDialog QPlainTextEdit:hover,
QDialog QTextEdit:hover,
QDialog QComboBox:hover {{
    border-color: #BDD0D9;
    background: #FFFFFF;
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
    width: 28px;
}}
QDialog QComboBox QAbstractItemView {{
    background: #FFFFFF;
    color: {INK};
    border: 1px solid {BORDER};
    border-radius: 9px;
    selection-background-color: {TEAL_SOFT};
    selection-color: {NAVY};
    padding: 6px;
    outline: 0;
}}
QDialog QCheckBox {{
    color: {INK};
    spacing: 9px;
    min-height: 26px;
    font-size: 10px;
}}
QDialog QTableWidget {{
    background: #FFFFFF;
    color: {INK};
    border: 1px solid {BORDER_SOFT};
    border-radius: 11px;
    gridline-color: #EDF2F4;
    font-size: 10px;
    selection-background-color: {TEAL_SOFT};
    selection-color: {NAVY};
}}
QDialog QTableWidget::item {{ padding: 8px; }}
QDialog QHeaderView::section {{
    background: #F5F8FA;
    color: #466071;
    border: none;
    border-bottom: 1px solid {BORDER_SOFT};
    padding: 9px;
    font-size: 9px;
    font-weight: 800;
}}
"""


_PRIMARY_WORDS = (
    "save", "ok", "yes", "apply", "continue", "create", "add", "invite",
    "connect", "authorize", "allow", "approve", "update", "install", "open",
    "browse", "import", "send", "use in protect", "background", "edit policy",
    "review policy", "manage",
)
_DANGER_WORDS = (
    "delete", "remove", "revoke", "disconnect", "disable", "quit", "sign out",
    "discard", "clear all", "reset",
)
_SECONDARY_WORDS = (
    "cancel", "close", "no", "back", "later", "skip", "not now", "refresh",
    "retry", "ignore", "restore defaults",
)
_SUCCESS_WORDS = ("done", "finish", "completed")


def _button_qss(role: str) -> str:
    if role == "primary":
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {TEAL}, stop:1 {TEAL_DARK});
                color: #FFFFFF; border: none; border-radius: 11px;
                padding: 9px 16px; font-size: 11px; font-weight: 800;
            }}
            QPushButton:hover {{ background: {TEAL_DARK}; }}
            QPushButton:pressed {{ background: #096B73; }}
            QPushButton:disabled {{ background: #DCE6EA; color: #91A0AA; }}
        """
    if role == "danger":
        return f"""
            QPushButton {{
                background: {RED_SOFT}; color: {RED}; border: 1px solid #F0D1D3;
                border-radius: 11px; padding: 9px 15px; font-size: 11px; font-weight: 800;
            }}
            QPushButton:hover {{ background: #FDE5E6; border-color: #E6B6B9; }}
            QPushButton:pressed {{ background: #F9DCDD; }}
            QPushButton:disabled {{ background: #F5F6F7; color: #A8B1B8; border-color: #E6EAED; }}
        """
    if role == "success":
        return f"""
            QPushButton {{
                background: {GREEN}; color: #FFFFFF; border: none; border-radius: 11px;
                padding: 9px 16px; font-size: 11px; font-weight: 800;
            }}
            QPushButton:hover {{ background: #1D7550; }}
            QPushButton:pressed {{ background: #176442; }}
            QPushButton:disabled {{ background: #DCE6EA; color: #91A0AA; }}
        """
    return f"""
        QPushButton {{
            background: #F1F5F7; color: {INK}; border: 1px solid #E1E9ED;
            border-radius: 11px; padding: 9px 15px; font-size: 11px; font-weight: 750;
        }}
        QPushButton:hover {{ background: #E9F3F4; color: {TEAL_DARK}; border-color: #C9DFE1; }}
        QPushButton:pressed {{ background: #E1EDEE; }}
        QPushButton:disabled {{ background: #F5F6F7; color: #A1ADB5; border-color: #E8ECEF; }}
    """


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
    primary = {
        QDialogButtonBox.StandardButton.Save,
        QDialogButtonBox.StandardButton.SaveAll,
        QDialogButtonBox.StandardButton.Ok,
        QDialogButtonBox.StandardButton.Yes,
        QDialogButtonBox.StandardButton.YesToAll,
        QDialogButtonBox.StandardButton.Apply,
        QDialogButtonBox.StandardButton.Open,
    }
    danger = {
        QDialogButtonBox.StandardButton.Discard,
        QDialogButtonBox.StandardButton.Abort,
    }
    secondary = {
        QDialogButtonBox.StandardButton.Cancel,
        QDialogButtonBox.StandardButton.Close,
        QDialogButtonBox.StandardButton.No,
        QDialogButtonBox.StandardButton.NoToAll,
        QDialogButtonBox.StandardButton.Ignore,
        QDialogButtonBox.StandardButton.Retry,
        QDialogButtonBox.StandardButton.Reset,
        QDialogButtonBox.StandardButton.RestoreDefaults,
    }
    if standard in primary:
        return "primary"
    if standard in danger:
        return "danger"
    if standard in secondary:
        return "secondary"
    return None


def _set_role(button: QPushButton, role: str) -> None:
    button.setObjectName({
        "primary": "PrivacyGateDialogPrimary",
        "secondary": "PrivacyGateDialogSecondary",
        "danger": "PrivacyGateDialogDanger",
        "success": "PrivacyGateDialogSuccess",
    }[role])
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(42)
    button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    # Modern SaaS-style actions: text and color hierarchy, no busy outline icons.
    button.setIcon(QIcon())
    button.setStyleSheet(_button_qss(role))
    button.ensurePolished()
    # QPushButton labels do not wrap, so always reserve their real text width.
    button.setMinimumWidth(max(96, button.sizeHint().width() + 16))


def _rename_context_buttons(dialog: QDialog) -> None:
    title = dialog.windowTitle().lower()
    if isinstance(dialog, QMessageBox) and "close privacygate" in title:
        for button in dialog.buttons():
            if isinstance(button, QPushButton) and "keep running in background" in button.text().lower():
                button.setText("Run in background")

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
    standards = (
        QDialogButtonBox.StandardButton.Save,
        QDialogButtonBox.StandardButton.SaveAll,
        QDialogButtonBox.StandardButton.Ok,
        QDialogButtonBox.StandardButton.Yes,
        QDialogButtonBox.StandardButton.YesToAll,
        QDialogButtonBox.StandardButton.Apply,
        QDialogButtonBox.StandardButton.Open,
        QDialogButtonBox.StandardButton.Discard,
        QDialogButtonBox.StandardButton.Abort,
        QDialogButtonBox.StandardButton.Cancel,
        QDialogButtonBox.StandardButton.Close,
        QDialogButtonBox.StandardButton.No,
        QDialogButtonBox.StandardButton.NoToAll,
        QDialogButtonBox.StandardButton.Ignore,
        QDialogButtonBox.StandardButton.Retry,
        QDialogButtonBox.StandardButton.Reset,
        QDialogButtonBox.StandardButton.RestoreDefaults,
    )
    for box in dialog.findChildren(QDialogButtonBox):
        for standard in standards:
            button = box.button(standard)
            if button is None:
                continue
            handled.add(id(button))
            _set_role(button, _role_from_standard(standard) or _role_from_text(button.text()))

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
        if id(button) not in handled:
            _set_role(button, _role_from_text(button.text()))


def _fit_dialog_to_buttons(dialog: QDialog) -> None:
    buttons = [button for button in dialog.findChildren(QPushButton) if button.isVisible()]
    if not buttons:
        return
    if isinstance(dialog, QMessageBox):
        widths = [max(96, button.minimumWidth(), button.sizeHint().width() + 16) for button in buttons]
        desired = min(760, 72 + sum(widths) + max(0, len(widths) - 1) * 10)
        dialog.setMinimumWidth(max(dialog.minimumWidth(), 520, desired))


def _polish_labels(dialog: QDialog) -> None:
    for label in dialog.findChildren(QLabel):
        text = label.text().strip()
        if label.pixmap() is not None:
            continue
        if len(text) > 52:
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setMaximumWidth(640)


def _polish_dialog(dialog: QDialog) -> None:
    try:
        if not bool(dialog.property("privacygateModernDialogStyled")):
            dialog.setProperty("privacygateModernDialogStyled", True)
            dialog.setStyleSheet(dialog.styleSheet() + _DIALOG_QSS)

        title = dialog.windowTitle().lower()
        if isinstance(dialog, QMessageBox):
            dialog.setMinimumWidth(max(dialog.minimumWidth(), 520))
            # Remove the large native Windows glyph for a cleaner platform-neutral modal.
            dialog.setIcon(QMessageBox.Icon.NoIcon)
        elif isinstance(dialog, QInputDialog):
            dialog.setMinimumWidth(max(dialog.minimumWidth(), 560))
        elif "workspace permissions" in title:
            dialog.setMinimumWidth(max(dialog.minimumWidth(), 600))
        elif "policy" in title:
            dialog.setMinimumWidth(max(dialog.minimumWidth(), 860))
        elif dialog.width() < 480:
            dialog.setMinimumWidth(max(dialog.minimumWidth(), 480))

        _rename_context_buttons(dialog)
        _style_buttons(dialog)
        _fit_dialog_to_buttons(dialog)
        _polish_labels(dialog)

        for edit in dialog.findChildren(QLineEdit):
            edit.setMinimumHeight(max(edit.minimumHeight(), 44))
        for combo in dialog.findChildren(QComboBox):
            combo.setMinimumHeight(max(combo.minimumHeight(), 44))
        for text in dialog.findChildren(QPlainTextEdit):
            text.setMinimumHeight(max(text.minimumHeight(), 96))
        for text in dialog.findChildren(QTextEdit):
            text.setMinimumHeight(max(text.minimumHeight(), 96))
        for table in dialog.findChildren(QTableWidget):
            table.verticalHeader().setDefaultSectionSize(
                max(36, table.verticalHeader().defaultSectionSize())
            )
        for check in dialog.findChildren(QCheckBox):
            check.setMinimumHeight(max(check.minimumHeight(), 28))
    except (RuntimeError, TypeError):
        return


class _ModernDialogFilter(QObject):
    def eventFilter(self, watched, event):  # noqa: N802 - Qt API
        if event.type() == QEvent.Type.Show and isinstance(watched, QDialog):
            QTimer.singleShot(0, lambda target=watched: _polish_dialog(target))
            QTimer.singleShot(100, lambda target=watched: _polish_dialog(target))
        return super().eventFilter(watched, event)


def apply_dialog_visual_system(main_window) -> None:
    """Install the modern PrivacyGate visual language for every modal dialog.

    Presentation only: QMessageBox, QInputDialog, policy editors, workspace
    permissions, connector dialogs and other QDialog subclasses keep their
    existing actions and data flow.
    """
    app = QApplication.instance()
    if app is None or getattr(app, "_privacygate_premium_dialog_filter", None) is not None:
        return
    event_filter = _ModernDialogFilter(app)
    app.installEventFilter(event_filter)
    app._privacygate_premium_dialog_filter = event_filter
