from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_transport import (
    GmailAddonMessage,
    GmailAddonTransport,
)
from ai_pm_lab_privacy_gate.ui import gmail_component_preview_polish, gmail_component_session
from ai_pm_lab_privacy_gate.ui.iconography import icon


NAVY = "#062B4F"
PETROL = "#0B7180"
MUTED = "#607789"
GMAIL_URL = "https://mail.google.com/"


def _button_style(primary: bool = False) -> str:
    if primary:
        return (
            "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
            "border-radius:9px;padding:8px 14px;font-weight:850;}"
            "QPushButton:hover{background:#095F6B;border-color:#095F6B;}"
            "QPushButton:disabled{background:#D9E2E8;color:#8A99A5;border-color:#D9E2E8;}"
        )
    return (
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C4D3DE;"
        "border-radius:9px;padding:8px 13px;font-weight:750;}"
        "QPushButton:hover{background:#EDF7F7;color:#062B4F;border-color:#9BCDD1;}"
    )


def _data_dir(main_window) -> Path:
    apps_page = getattr(main_window, "apps_hub_page", None)
    service = getattr(apps_page, "service", None) if apps_page is not None else None
    data_dir = getattr(service, "data_dir", None) if service is not None else None
    if data_dir:
        return Path(data_dir)
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local) / "PrivacyGate"
    return Path.home() / ".privacygate"


def _format_message(message: GmailAddonMessage) -> str:
    lines = []
    if message.sender:
        lines.append(f"From: {message.sender}")
    if message.recipients:
        lines.append(f"To: {message.recipients}")
    if message.sent_at:
        lines.append(f"Date: {message.sent_at}")
    lines.append(f"Subject: {message.subject}")
    lines.append("")
    lines.append(message.body)
    return "\n".join(lines).strip()


def _bring_to_front(dialog: QDialog, main_window) -> None:
    """Best-effort foreground activation after Gmail delivers a message."""

    def activate() -> None:
        try:
            main_window.showNormal()
            main_window.raise_()
            main_window.activateWindow()
        except Exception:
            pass
        try:
            dialog.showNormal()
            dialog.raise_()
            dialog.activateWindow()
            QApplication.alert(dialog, 3000)
        except Exception:
            pass
        if os.name == "nt":
            try:
                import ctypes

                hwnd = int(dialog.winId())
                user32 = ctypes.windll.user32
                SW_RESTORE = 9
                HWND_TOPMOST = -1
                HWND_NOTOPMOST = -2
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                flags = SWP_NOMOVE | SWP_NOSIZE
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
                user32.SetForegroundWindow(hwnd)
                user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            except Exception:
                pass

    activate()
    QTimer.singleShot(120, activate)
    QTimer.singleShot(400, activate)


def _adopt_addon_component(main_window, message: GmailAddonMessage, kind: str, index: int, transport) -> tuple[str, str]:
    """Put one selected Gmail component into the existing Gmail-aware Protect runtime."""
    protect = main_window.protection_page
    gmail_component_session.apply_gmail_component_session(main_window)

    if kind == "body":
        content = _format_message(message)
        paste_button = getattr(protect, "_redesign_paste_mode", None)
        if paste_button is not None and not paste_button.isChecked():
            paste_button.click()
        protect.input_tabs.setCurrentIndex(0)
        protect.text_input.setPlainText(content)
        component_title = "Email body"
        component_kind = "email_body"
        component = {
            "key": "gmail_body",
            "label": "Email body",
            "component_kind": "body",
            "text": content,
            "path": "",
        }
    else:
        attachment = message.attachments[int(index)]
        local_path = transport.materialize_attachment(attachment)
        document_button = getattr(protect, "_redesign_document_mode", None)
        if document_button is not None and not document_button.isChecked():
            document_button.click()
        protect.input_tabs.setCurrentIndex(1)
        protect.pdf_path.setText(str(local_path))
        component_title = attachment.filename
        component_kind = Path(attachment.filename).suffix.lower().lstrip(".") or "attachment"
        component = {
            "key": "gmail_attachment_1",
            "label": component_title,
            "component_kind": "attachment",
            "text": "",
            "path": str(local_path),
        }

    protect._gmail_component_manifest = (component,)
    protect._gmail_component_sources = {}
    protect._gmail_component_results = {}
    protect._gmail_component_active_key = str(component["key"])
    protect._gmail_package_active = False
    protect.current_document = None
    protect.current_findings = ()
    protect.current_result = None
    protect.findings_table.setRowCount(0)
    protect.category_list.clear()
    protect.preview.clear()
    protect._set_result_actions(False)

    protect._external_source_name = " • ".join(
        part for part in ("Gmail Add-on", message.subject, component_title) if part
    )
    protect._external_source_metadata = {
        "provider": "gmail",
        "provider_label": "Gmail Add-on",
        "account_id": transport.account_id,
        "account_label": transport.registry.get(transport.account_id)["label"],
        "item_id": message.message_id,
        "thread_id": message.thread_id,
        "item_title": message.subject,
        "item_kind": "email",
        "source_component": component_kind,
        "source_component_title": component_title,
        "package_mode": "gmail_message_package",
        "selected_components": [component_title],
        "email_body_selected": kind == "body",
        "attachment_count": 0 if kind == "body" else 1,
        "access_model": "gmail_addons_current_message_action",
    }

    gmail_component_session._refresh_component_strip(protect)
    gmail_component_preview_polish._show_unprotected_source(protect, str(component["key"]))
    return component_title, component_kind


class GmailImportDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        from PySide6.QtWidgets import QComboBox
        from .gmail_addon_accounts_ui import _card, _text
        from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_accounts import GmailAccountRegistry
        self.window = main_window
        self.registry = GmailAccountRegistry(_data_dir(main_window))
        self.transport = None
        self.message = None
        self.future = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.setWindowTitle('Gmail → PrivacyGate')
        self.setObjectName('GmailImportDialog')
        self.resize(780, 680)
        self.setStyleSheet('QDialog{background:#F5F9FC;}')
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(12)
        root.addWidget(_text('Import from Gmail', True))
        account_row = QHBoxLayout()
        account_row.addWidget(_text('Account'))
        self.accounts = QComboBox()
        self.accounts.setObjectName('GmailImportAccount')
        account_row.addWidget(self.accounts, 1)
        manage = QPushButton('Manage accounts')
        manage.setStyleSheet(_button_style(False))
        manage.clicked.connect(self.manage)
        account_row.addWidget(manage)
        root.addLayout(account_row)
        self.instructions = QFrame()
        instructions = QVBoxLayout(self.instructions)
        instructions.setContentsMargins(0, 8, 0, 8)
        instructions.addWidget(_text('Send the message you want to protect', True))
        instructions.addWidget(_text('1. Open the same account in Gmail, then open an email.'))
        instructions.addWidget(_text('2. In the far-right sidebar, open the icon named PrivacyGate.'))
        instructions.addWidget(_text('3. Click Send to PrivacyGate. Keep this window open.'))
        actions = QHBoxLayout()
        gmail = QPushButton('Open Gmail')
        gmail.setStyleSheet(_button_style(True))
        gmail.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GMAIL_URL)))
        actions.addWidget(gmail)
        help_button = QPushButton('Cannot find the PrivacyGate icon?')
        help_button.setStyleSheet(_button_style(False))
        from .gmail_addon_accounts_ui import show_gmail_help
        help_button.clicked.connect(lambda: show_gmail_help(self))
        actions.addWidget(help_button)
        actions.addStretch()
        instructions.addLayout(actions)
        root.addWidget(self.instructions)
        self.status = _text('')
        root.addWidget(self.status)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(260)
        self.preview.setStyleSheet('QTextEdit{background:white;color:#17384E;font-size:14px;border:1px solid #D7E2EA;border-radius:10px;padding:16px;}')
        self.preview.setPlaceholderText('Your selected message will appear here. After importing, run Scan and Protect in PrivacyGate.')
        root.addWidget(self.preview, 1)
        root.addWidget(_text('Transfer uses a temporary Google cache for up to 2 minutes. Scan and Protect run locally. Attachments are not imported.'))
        row = QHBoxLayout()
        close = QPushButton('Cancel')
        close.setStyleSheet(_button_style(False))
        close.clicked.connect(self.reject)
        row.addWidget(close)
        row.addStretch()
        self.use = QPushButton('Use in Protect')
        self.use.setStyleSheet(_button_style(True))
        self.use.setEnabled(False)
        self.use.clicked.connect(self.adopt)
        row.addWidget(self.use)
        root.addLayout(row)
        self.timer = QTimer(self)
        self.timer.setInterval(1200)
        self.timer.timeout.connect(self.tick)
        self.accounts.currentIndexChanged.connect(self.select)
        self.reload()
        self.timer.start()

    def reload(self):
        self.accounts.blockSignals(True)
        self.accounts.clear()
        for account in self.registry.accounts():
            if account.get('endpoint') and account.get('paired'):
                self.accounts.addItem(account['label'], account['id'])
        index = self.accounts.findData(self.registry.active_id)
        if index >= 0:
            self.accounts.setCurrentIndex(index)
        self.accounts.blockSignals(False)
        self.select()

    def select(self, *_):
        account_id = self.accounts.currentData()
        self.message = None
        self.instructions.show()
        self.preview.clear()
        self.use.setEnabled(False)
        self.transport = GmailAddonTransport(self.registry.data_dir, account_id=account_id) if account_id else None
        self.status.setText('Waiting for a message from ' + self.accounts.currentText() + '…' if account_id else 'Connect an account in Apps to begin.')

    def manage(self):
        # Close this receiver before opening account setup, so no background import consumes a message.
        self.reject()
        from .gmail_addon_accounts_ui import open_gmail_accounts
        open_gmail_accounts(self.window)

    def tick(self):
        if self.future:
            if not self.future.done():
                return
            future, self.future = self.future, None
            self.accounts.setEnabled(True)
            try:
                account_id, message = future.result()
                if self.transport and account_id == self.transport.account_id and message:
                    self.render_message(message)
            except Exception:
                self.status.setText('Connection interrupted. Retrying… Keep Gmail open and send again if needed.')
            return
        if self.transport and self.message is None:
            transport = self.transport
            self.accounts.setEnabled(False)
            self.future = self.executor.submit(lambda: (transport.account_id, transport.poll(timeout=5)))

    def render_message(self, message):
        self.message = message
        self.instructions.hide()
        self.preview.setPlainText(_format_message(message))
        self.use.setEnabled(True)
        self.status.setText('Message received · Review below, then choose Use in Protect')
        _bring_to_front(self, self.window)

    def adopt(self):
        if self.message is None or self.transport is None:
            return
        try:
            _adopt_addon_component(self.window, self.message, 'body', -1, self.transport)
            self.window._show_page(0)
            page = self.window.protection_page
            def reveal_import():
                if page._external_source_metadata.get('item_id') == self.message.message_id:
                    page._gmail_component_select('gmail_body')
            QTimer.singleShot(0, reveal_import)
        except Exception as exc:
            QMessageBox.warning(self, 'Unable to import from Gmail', str(exc))
            return
        self.accept()

    def done(self, result):
        self.timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().done(result)


def open_gmail_addon_import(main_window):
    GmailImportDialog(main_window).exec()
