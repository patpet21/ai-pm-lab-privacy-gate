from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_accounts import (
    GmailAccountRegistry,
    validate_endpoint,
)
from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_transport import GmailAddonTransport
from .gmail_addon_import import _data_dir, open_gmail_addon_import
from .resources import resource_path


PAGE_BG = '#F5F9FC'
NAVY = '#062B4F'
TEAL = '#0B8F9C'
TEAL_DARK = '#087783'
TEXT = '#526C7D'
BORDER = '#D7E2EA'
SOFT = '#EEF5F8'
DANGER = '#A33A3A'


def release_settings():
    """Return public install URL when approved, and the publisher relay endpoint independently."""
    try:
        data = json.loads(
            Path(resource_path('resources', 'gmail-addon-release.json')).read_text('utf-8')
        )
        endpoint = validate_endpoint(data.get('endpoint', ''))

        install_url = ''
        p = urlsplit(data.get('marketplace_url', ''))
        published = (
            data.get('status') == 'published'
            and data.get('consent_verified') is True
            and p.scheme == 'https'
            and p.netloc == 'workspace.google.com'
            and p.path.startswith('/marketplace/app/')
        )
        if published:
            install_url = data.get('marketplace_url', '')

        return install_url, endpoint
    except (OSError, ValueError, KeyError, TypeError):
        return '', ''


def _text(value, title=False, small=False):
    label = QLabel(value)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    if title:
        label.setStyleSheet(
            f'background:transparent;color:{NAVY};font-size:20px;font-weight:700;'
        )
    elif small:
        label.setStyleSheet(
            f'background:transparent;color:{TEXT};font-size:12px;line-height:1.35;'
        )
    else:
        label.setStyleSheet(
            f'background:transparent;color:{TEXT};font-size:14px;line-height:1.4;'
        )
    return label


def _button_style(primary=False, danger=False):
    if primary:
        return (
            f'QPushButton{{background:{TEAL};color:white;border:1px solid {TEAL};border-radius:9px;'
            'padding:10px 18px;font-size:14px;font-weight:700;min-height:24px;}'
            f'QPushButton:hover{{background:{TEAL_DARK};border-color:{TEAL_DARK};}}'
            'QPushButton:disabled{background:#D8E2E8;color:#8CA0AD;border-color:#D8E2E8;}'
        )
    if danger:
        return (
            f'QPushButton{{background:white;color:{DANGER};border:1px solid #E5C8C8;border-radius:9px;'
            'padding:10px 16px;font-size:14px;font-weight:600;min-height:24px;}'
            'QPushButton:hover{background:#FFF4F4;border-color:#DCAAAA;}'
        )
    return (
        f'QPushButton{{background:white;color:{NAVY};border:1px solid {BORDER};border-radius:9px;'
        'padding:10px 16px;font-size:14px;font-weight:600;min-height:24px;}'
        f'QPushButton:hover{{background:{SOFT};border-color:#B9CCD8;}}'
        'QPushButton:disabled{background:#F3F6F8;color:#9AAAB4;border-color:#E1E8ED;}'
    )


def _card(layout, title, description=''):
    card = QFrame(objectName='GmailStepCard')
    card.setStyleSheet(
        f'QFrame#GmailStepCard{{background:white;border:1px solid {BORDER};border-radius:14px;}}'
    )
    inner = QVBoxLayout(card)
    inner.setContentsMargins(22, 18, 22, 18)
    inner.setSpacing(10)
    inner.addWidget(_text(title, True))
    if description:
        inner.addWidget(_text(description))
    layout.addWidget(card)
    return inner


def _sync_account_endpoint(registry, account_id):
    """Keep saved account slots on the current publisher relay after a deployment change."""
    _, publisher_endpoint = release_settings()
    if not publisher_endpoint:
        return ''
    account = registry.get(account_id)
    if account and account.get('endpoint') != publisher_endpoint:
        registry.update(account_id, endpoint=publisher_endpoint, paired=False)
    return publisher_endpoint


class GmailPairingDialog(QDialog):
    def __init__(self, window, registry, account_id):
        super().__init__(window)
        self.registry, self.account_id = registry, account_id
        _sync_account_endpoint(self.registry, self.account_id)
        self.transport = GmailAddonTransport(registry.data_dir, account_id=account_id)
        self.future = None
        self.executor = ThreadPoolExecutor(max_workers=1)

        self.setWindowTitle('Connect Gmail account')
        self.setObjectName('GmailPairingDialog')
        self.resize(860, 700)
        self.setMinimumSize(780, 620)
        self.setStyleSheet(f'QDialog#GmailPairingDialog{{background:{PAGE_BG};}}')

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(16)

        label = registry.get(account_id)['label']
        heading = _text('Connect ' + label, True)
        heading.setStyleSheet(
            f'background:transparent;color:{NAVY};font-size:25px;font-weight:750;'
        )
        root.addWidget(heading)
        root.addWidget(
            _text('Two steps only: make PrivacyGate available in this Gmail account, then pair it with this device.')
        )

        install_url, endpoint = release_settings()
        first = _card(
            root,
            '1. Make PrivacyGate available in Gmail',
            'Each Google account needs its own PrivacyGate add-on installation. Open Gmail using the account you want to connect.',
        )
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        gmail = QPushButton('Open Gmail')
        gmail.setStyleSheet(_button_style(True))
        gmail.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://mail.google.com/')))
        buttons.addWidget(gmail)

        install = QPushButton('Install PrivacyGate add-on')
        install.setStyleSheet(_button_style(False))
        install.setEnabled(bool(install_url))
        install.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(install_url)))
        buttons.addWidget(install)
        first.addLayout(buttons)

        if not install_url:
            first.addWidget(
                _text(
                    'Public Marketplace installation is not live yet. For testing, install the Apps Script test deployment in this Google account, reload Gmail, then continue below.',
                    small=True,
                )
            )

        second = _card(
            root,
            '2. Pair this device',
            'In Gmail, open an email and open PrivacyGate from the right-side add-on bar. Paste the pairing code below and press Connect.',
        )
        second.addWidget(_text('Pairing code', small=True))
        self.code = QLineEdit(self.transport.channel)
        self.code.setReadOnly(True)
        self.code.setMinimumHeight(46)
        self.code.setStyleSheet(
            f'QLineEdit{{background:#FAFCFD;color:{NAVY};border:1px solid {BORDER};border-radius:9px;'
            'padding:0 14px;font-size:14px;font-family:Consolas,monospace;}}'
        )
        second.addWidget(self.code)

        code_actions = QHBoxLayout()
        code_actions.setSpacing(10)
        copy = QPushButton('Copy pairing code')
        copy.setStyleSheet(_button_style(True))
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.code.text()))
        code_actions.addWidget(copy)
        help_button = QPushButton('Where is PrivacyGate in Gmail?')
        help_button.setStyleSheet(_button_style(False))
        help_button.clicked.connect(lambda: show_gmail_help(self))
        code_actions.addWidget(help_button)
        second.addLayout(code_actions)

        status_card = QFrame(objectName='GmailStatusCard')
        status_card.setStyleSheet(
            f'QFrame#GmailStatusCard{{background:{SOFT};border:1px solid {BORDER};border-radius:12px;}}'
        )
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(18, 14, 18, 14)
        status_layout.setSpacing(5)
        status_layout.addWidget(_text('Connection status', True))
        self.status = _text(
            'Waiting for confirmation from Gmail…'
            if self.transport.endpoint
            else 'The Gmail relay endpoint is not configured in this build.'
        )
        status_layout.addWidget(self.status)
        root.addWidget(status_card)

        if endpoint and self.transport.endpoint:
            root.addWidget(
                _text('PrivacyGate is using the current Gmail relay deployment for this account.', small=True)
            )

        # Deployment addresses are publisher configuration, never a customer step.
        if os.environ.get('PRIVACYGATE_GMAIL_ADDON_DEVELOPMENT') == '1':
            dev = QPushButton('Developer deployment settings')
            dev.setStyleSheet(_button_style(False))

            def configure():
                value, ok = QInputDialog.getText(
                    self,
                    'Development only',
                    'Apps Script /exec URL:',
                    text=self.transport.endpoint,
                )
                if ok:
                    try:
                        self.transport.set_endpoint(value)
                        self.status.setText('Waiting for confirmation from Gmail…')
                    except ValueError as exc:
                        self.status.setText(str(exc))

            dev.clicked.connect(configure)
            root.addWidget(dev)

        close = QPushButton('Done')
        close.setStyleSheet(_button_style(False))
        close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

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
                    self.status.setText('Connected. This Gmail account is ready to use in Protect.')
                    self.timer.stop()
            except Exception as exc:
                self.status.setText(f'Not connected yet. {exc}')
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
        self.resize(920, 720)
        self.setMinimumSize(820, 620)
        self.setStyleSheet(f'QDialog#GmailAccountsDialog{{background:{PAGE_BG};}}')

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(16)

        heading = _text('Gmail accounts', True)
        heading.setStyleSheet(
            f'background:transparent;color:{NAVY};font-size:26px;font-weight:750;'
        )
        root.addWidget(heading)
        root.addWidget(
            _text('Connect each Gmail account once. PrivacyGate only receives the email you explicitly send from the Gmail add-on.')
        )

        how = _card(root, 'How it works')
        how.addWidget(
            _text('1. Install PrivacyGate in Gmail   →   2. Pair this device   →   3. Choose the account when importing an email in Protect')
        )

        top_actions = QHBoxLayout()
        top_actions.setSpacing(10)
        add = QPushButton('Add Gmail account')
        add.setObjectName('GmailAddAccount')
        add.setStyleSheet(_button_style(True))
        add.clicked.connect(self.add_account)
        top_actions.addWidget(add)

        help_button = QPushButton('Find PrivacyGate in Gmail')
        help_button.setStyleSheet(_button_style(False))
        help_button.clicked.connect(lambda: show_gmail_help(self))
        top_actions.addWidget(help_button)
        top_actions.addStretch(1)
        root.addLayout(top_actions)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea{background:transparent;border:none;}')
        body = QWidget()
        body.setStyleSheet('background:transparent;')
        self.rows = QVBoxLayout(body)
        self.rows.setContentsMargins(0, 0, 4, 0)
        self.rows.setSpacing(12)
        self.rows.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.addWidget(
            _text('Email content is scanned and protected locally on this device.', small=True)
        )
        footer.addStretch(1)
        close = QPushButton('Close')
        close.setStyleSheet(_button_style(False))
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

        self.refresh()

    def refresh(self):
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        accounts = self.registry.accounts()
        if not accounts:
            empty = _card(self.rows, 'No Gmail accounts connected yet')
            empty.addWidget(_text('Click “Add Gmail account” above to connect your first account.'))
            return

        for account in accounts:
            ready = bool(account.get('paired') and account.get('endpoint'))
            active = ready and account['id'] == self.registry.active_id
            if ready:
                state = 'Connected to this device'
                if active:
                    state += ' · Default account'
            else:
                state = 'Not connected yet · Finish pairing'

            inner = _card(self.rows, account['label'], state)
            actions = QHBoxLayout()
            actions.setSpacing(10)

            pair = QPushButton('Connection details' if ready else 'Connect account')
            pair.setStyleSheet(_button_style(not ready))
            pair.clicked.connect(
                lambda _=False, key=account['id']: self.pair_account(key)
            )
            actions.addWidget(pair)

            choose = QPushButton('Default account' if active else 'Set as default')
            choose.setStyleSheet(_button_style(False))
            choose.setEnabled(ready and not active)
            choose.clicked.connect(
                lambda _=False, key=account['id']: self.select_account(key)
            )
            actions.addWidget(choose)

            remove = QPushButton('Remove')
            remove.setStyleSheet(_button_style(False, danger=True))
            remove.clicked.connect(
                lambda _=False, key=account['id']: self.remove_account(key)
            )
            actions.addWidget(remove)
            actions.addStretch(1)
            inner.addLayout(actions)

    def add_account(self):
        label, ok = QInputDialog.getText(
            self,
            'Add Gmail account',
            'Account label (for example Personal Gmail or Work Gmail):',
        )
        if not ok:
            return
        try:
            _, endpoint = release_settings()
            if not endpoint:
                endpoint = next(
                    (a['endpoint'] for a in self.registry.accounts() if a.get('endpoint')),
                    '',
                )
            account_id = self.registry.add(label, endpoint)
            self.pair_account(account_id)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Gmail account', str(exc))
        self.refresh()

    def pair_account(self, account_id):
        _sync_account_endpoint(self.registry, account_id)
        GmailPairingDialog(self.window, self.registry, account_id).exec()
        self.refresh()

    def select_account(self, account_id):
        try:
            self.registry.select(account_id)
        except ValueError as exc:
            QMessageBox.warning(self, 'Gmail account', str(exc))
        self.refresh()

    def remove_account(self, account_id):
        if (
            QMessageBox.question(
                self,
                'Remove Gmail account?',
                'Remove this Gmail account from PrivacyGate on this device? This does not delete Gmail messages or uninstall the Gmail add-on.',
            )
            == QMessageBox.StandardButton.Yes
        ):
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
    dialog.resize(700, 520)
    dialog.setMinimumSize(640, 460)
    dialog.setStyleSheet(f'QDialog{{background:{PAGE_BG};}}')

    root = QVBoxLayout(dialog)
    root.setContentsMargins(28, 26, 28, 26)
    root.setSpacing(14)

    heading = _text('Find PrivacyGate in Gmail', True)
    heading.setStyleSheet(
        f'background:transparent;color:{NAVY};font-size:24px;font-weight:750;'
    )
    root.addWidget(heading)

    where = _card(
        root,
        '1. Open the Gmail side panel',
        'On Gmail desktop, look at the narrow vertical bar on the far right beside Calendar, Keep and Tasks. If the bar is hidden, expand it from the bottom-right corner.',
    )
    where.addWidget(_text('Hover over the icons and open the one named PrivacyGate.', small=True))

    account = _card(
        root,
        '2. Check the Google account',
        'PrivacyGate must be installed separately for each Google account. Check the avatar at the top right of Gmail before pairing.',
    )
    account.addWidget(
        _text('The + button opens the Google Workspace Marketplace; it is not the PrivacyGate add-on itself.', small=True)
    )

    url, _ = release_settings()
    if url:
        install = QPushButton('Install PrivacyGate')
        install.setStyleSheet(_button_style(True))
        install.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        root.addWidget(install, alignment=Qt.AlignmentFlag.AlignLeft)
    else:
        root.addWidget(
            _text(
                'Marketplace installation is not live yet. During testing, install the Apps Script test deployment using the same Google account, then reload Gmail.'
            )
        )

    close = QPushButton('Got it')
    close.setStyleSheet(_button_style(True))
    close.clicked.connect(dialog.accept)
    root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
    dialog.exec()
