from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel,
    QInputDialog, QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_accounts import GmailAccountRegistry, validate_endpoint
from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_transport import GmailAddonTransport
from .gmail_addon_import import _data_dir, _button_style, open_gmail_addon_import
from .resources import resource_path


def release_settings():
    """Only a reviewed publisher release may advertise a customer install link."""
    try:
        data = json.loads(Path(resource_path('resources', 'gmail-addon-release.json')).read_text('utf-8'))
        p = urlsplit(data.get('marketplace_url', ''))
        ready = (data.get('status') == 'published' and data.get('consent_verified') is True
                 and p.scheme == 'https' and p.netloc == 'workspace.google.com'
                 and p.path.startswith('/marketplace/app/'))
        endpoint = validate_endpoint(data.get('endpoint', ''))
        return (data['marketplace_url'], endpoint) if ready and endpoint else ('', '')
    except (OSError, ValueError, KeyError, TypeError):
        return '', ''


def _text(value, title=False):
    label = QLabel(value)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setStyleSheet('background:transparent;color:#062B4F;font-size:18px;font-weight:700;' if title else 'background:transparent;color:#526C7D;font-size:13px;')
    return label


def _card(layout, title, description):
    card = QFrame(objectName='GmailStepCard')
    card.setStyleSheet('QFrame#GmailStepCard{background:white;border:1px solid #D7E2EA;border-radius:12px;}')
    inner = QVBoxLayout(card)
    inner.setContentsMargins(16, 14, 16, 14)
    inner.addWidget(_text(title, True))
    inner.addWidget(_text(description))
    layout.addWidget(card)
    return inner


class GmailPairingDialog(QDialog):
    def __init__(self, window, registry, account_id):
        super().__init__(window)
        self.registry, self.account_id = registry, account_id
        self.transport = GmailAddonTransport(registry.data_dir, account_id=account_id)
        self.future = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.setWindowTitle('Connect Gmail account')
        self.setObjectName('GmailPairingDialog')
        self.resize(740, 650)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)
        label = registry.get(account_id)['label']
        root.addWidget(_text('Connect ' + label, True))
        install_url, endpoint = release_settings()
        first = _card(root, '1  Install the add-on in this Gmail account',
                      'Adding an account here does not install anything in Gmail. Switch accounts using the avatar at the top right of Gmail. Each Google account needs its own add-on installation.')
        buttons = QHBoxLayout()
        gmail = QPushButton('Open Gmail')
        gmail.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://mail.google.com/')))
        buttons.addWidget(gmail)
        install = QPushButton('Install PrivacyGate add-on')
        install.setEnabled(bool(install_url))
        install.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(install_url)))
        buttons.addWidget(install)
        first.addLayout(buttons)
        if not install_url:
            first.addWidget(_text('Installation unavailable in this build. If this Gmail account has no PrivacyGate add-on, you cannot finish connecting it yet. Saving its name here is not a connection.'))
        second = _card(root, '2  Link the installed add-on to this device',
                       'In Gmail, open an email. Find PrivacyGate in the narrow vertical bar on the far right, beside Calendar, Keep and Tasks. Open it, paste this code and press Connect. '
                       'Use a separate PrivacyGate account card and code for each Gmail account. '
                       'The account name here is your label; check the account avatar in Gmail.')
        self.code = QLineEdit(self.transport.channel)
        self.code.setReadOnly(True)
        second.addWidget(self.code)
        help_button = QPushButton('No PrivacyGate icon in Gmail?')
        help_button.setStyleSheet(_button_style(False))
        help_button.clicked.connect(lambda: show_gmail_help(self))
        second.addWidget(help_button)
        copy = QPushButton('Copy pairing code')
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.code.text()))
        second.addWidget(copy)
        self.status = _text('Waiting for confirmation from Gmail…' if self.transport.endpoint else 'Account saved. Connection becomes available when the add-on is published.')
        root.addWidget(self.status)
        # Deployment addresses are publisher configuration, never a customer step.
        if os.environ.get('PRIVACYGATE_GMAIL_ADDON_DEVELOPMENT') == '1':
            dev = QPushButton('Developer deployment settings')
            def configure():
                value, ok = QInputDialog.getText(self, 'Development only', 'Apps Script /exec URL:', text=self.transport.endpoint)
                if ok:
                    try:
                        self.transport.set_endpoint(value)
                        self.status.setText('Waiting for confirmation from Gmail…')
                    except ValueError as exc:
                        self.status.setText(str(exc))
            dev.clicked.connect(configure)
            root.addWidget(dev)
        close = QPushButton('Done')
        close.clicked.connect(self.accept)
        root.addWidget(close)
        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def tick(self):
        if self.future:
            if not self.future.done():
                return
            future, self.future = self.future, None
            try:
                if future.result():
                    self.status.setText('Connected. You can now choose this account in Protect.')
                    self.timer.stop()
            except Exception:
                self.status.setText('No confirmation yet. Check Gmail and retry; your other accounts are unchanged.')
        elif self.transport.endpoint:
            self.future = self.executor.submit(self.transport.check_pairing)

    def done(self, result):
        self.timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
        if QApplication.clipboard().text() == self.code.text():
            QApplication.clipboard().clear()
        super().done(result)


class GmailAccountsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.registry = GmailAccountRegistry(_data_dir(window))
        self.setObjectName('GmailAccountsDialog')
        self.setWindowTitle('Gmail accounts')
        self.resize(790, 660)
        self.setStyleSheet('QDialog{background:#F5F9FC;}')
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        root.addWidget(_text('Your Gmail accounts', True))
        root.addWidget(_text('Connect personal and work Gmail separately. Each account has its own pairing; adding one never replaces another.'))
        _card(root, 'Install in Gmail → Link this device → Import in Protect',
              'Every Google account needs the PrivacyGate add-on installed separately. Add its name below, then complete the installation and pairing steps. A saved account is not connected until Gmail confirms the pairing.')
        help_button = QPushButton('Where is the PrivacyGate icon in Gmail?')
        help_button.setStyleSheet(_button_style(False))
        help_button.clicked.connect(lambda: show_gmail_help(self))
        root.addWidget(help_button, alignment=Qt.AlignmentFlag.AlignLeft)
        root.addWidget(_text('Only the message you send is read. Transfer uses a temporary Google cache for up to 2 minutes; Scan and Protect run on your device.'))
        add = QPushButton('Add Gmail account')
        add.setObjectName('GmailAddAccount')
        add.setStyleSheet(_button_style(True))
        add.clicked.connect(self.add_account)
        root.addWidget(add, alignment=Qt.AlignmentFlag.AlignLeft)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        self.rows = QVBoxLayout(body)
        self.rows.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        close = QPushButton('Close')
        close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.refresh()

    def refresh(self):
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        accounts = self.registry.accounts()
        if not accounts:
            self.rows.addWidget(_text('No Gmail accounts yet. Add your first account to get started.'))
        for account in accounts:
            ready = bool(account.get('paired') and account.get('endpoint'))
            state = 'Paired with this device' if ready else 'Saved only · Installation / pairing incomplete'
            if ready and account['id'] == self.registry.active_id:
                state += ' · Default for imports'
            inner = _card(self.rows, account['label'], state)
            actions = QHBoxLayout()
            pair = QPushButton('Connection details' if ready else 'Connect account')
            pair.setStyleSheet(_button_style(False))
            pair.clicked.connect(lambda _=False, key=account['id']: self.pair_account(key))
            actions.addWidget(pair)
            choose = QPushButton('Use by default')
            choose.setStyleSheet(_button_style(False))
            choose.setEnabled(ready and account['id'] != self.registry.active_id)
            choose.clicked.connect(lambda _=False, key=account['id']: self.select_account(key))
            actions.addWidget(choose)
            remove = QPushButton('Remove from PrivacyGate')
            remove.setStyleSheet(_button_style(False))
            remove.clicked.connect(lambda _=False, key=account['id']: self.remove_account(key))
            actions.addWidget(remove)
            inner.addLayout(actions)

    def add_account(self):
        label, ok = QInputDialog.getText(self, 'Add Gmail account', 'Account label (for example Personal Gmail or Work Gmail):')
        if not ok:
            return
        try:
            _, endpoint = release_settings()
            # Reuse the publisher endpoint of existing action connections.
            if not endpoint:
                endpoint = next((a['endpoint'] for a in self.registry.accounts() if a.get('endpoint')), '')
            account_id = self.registry.add(label, endpoint)
            self.pair_account(account_id)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Gmail account', str(exc))
        self.refresh()

    def pair_account(self, account_id):
        GmailPairingDialog(self.window, self.registry, account_id).exec()
        self.refresh()

    def select_account(self, account_id):
        self.registry.select(account_id)
        self.refresh()

    def remove_account(self, account_id):
        if QMessageBox.question(self, 'Remove Gmail account?', 'Stop receiving this account on this device? Your Gmail messages and other accounts remain unchanged. This does not uninstall the add-on in Gmail.') == QMessageBox.StandardButton.Yes:
            self.registry.remove(account_id)
            self.refresh()


def open_gmail_accounts(window):
    GmailAccountsDialog(window).exec()


def open_configured_gmail_import(window):
    open_gmail_addon_import(window)


# Compatibility with existing imports; there is no longer a mode chooser.
open_gmail_mode_picker = open_gmail_accounts


def show_gmail_help(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle('Find PrivacyGate in Gmail')
    dialog.resize(630, 480)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(24, 24, 24, 24)
    root.setSpacing(18)
    root.addWidget(_text('Where to look', True))
    root.addWidget(_text('Open Gmail on your computer. The add-on lives in the narrow vertical bar on the far RIGHT, beside Calendar, Keep and Tasks. If that bar is hidden, expand the side panel at the bottom right.'))
    root.addWidget(_text('Look for the name PrivacyGate', True))
    root.addWidget(_text('Hover over the icons to see their names. The current test add-on uses the Gmail envelope logo, so its icon may not look like PrivacyGate. Open the icon whose tooltip says PrivacyGate.'))
    root.addWidget(_text('Only Google icons and a + button?', True))
    root.addWidget(_text('The + button opens the add-on marketplace; it is not PrivacyGate. Check the account avatar at the top right. Installing the add-on in one Google account does not install it in another.'))
    url, _ = release_settings()
    root.addWidget(_text('Install PrivacyGate from the official listing for this account, then reload Gmail.' if url else 'This build has no public installation link yet. An account without the test add-on cannot receive the PrivacyGate icon just by adding its name in the app. The publisher must make the add-on available to that account first.'))
    close = QPushButton('Got it')
    close.setStyleSheet(_button_style(True))
    close.clicked.connect(dialog.accept)
    root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
    dialog.exec()
