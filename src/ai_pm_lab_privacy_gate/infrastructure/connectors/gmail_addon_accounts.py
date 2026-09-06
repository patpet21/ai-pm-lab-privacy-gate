from __future__ import annotations

import hashlib
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit

from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import platform_secret_store

CONFIG_FILENAME = 'gmail_addon.json'
_LOCK = threading.RLock()


def validate_endpoint(value: str) -> str:
    value = value.strip()
    if not value:
        return ''
    p = urlsplit(value)
    if (p.scheme != 'https' or p.netloc != 'script.google.com'
            or not p.path.startswith('/macros/s/') or not p.path.endswith('/exec')
            or p.query or p.fragment):
        raise ValueError('Use the published HTTPS Apps Script /exec address.')
    return value


class GmailAccountRegistry:
    """Independent account slots; display labels are user supplied, not verified identity."""

    def __init__(self, data_dir, secret_store=None):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / CONFIG_FILENAME
        self.secrets = secret_store if secret_store is not None else platform_secret_store(self.data_dir)
        self.namespace = hashlib.sha256(str(self.data_dir.resolve()).encode()).hexdigest()[:12]
        with _LOCK:
            data = self._read()
            if 'accounts' not in data and data.get('channel'):
                account_id = secrets.token_hex(12)
                self.secrets.set(self._key(account_id), data['channel'])
                legacy = {'id': account_id, 'label': 'Existing Gmail account',
                          'endpoint': data.get('endpoint', ''), 'paired': bool(data.get('paired'))}
                self._write({'version': 2, 'accounts': [legacy], 'active_account': account_id})

    def _key(self, account_id):
        return f'gmail-addon.{self.namespace}.{account_id}'

    def _read(self):
        if not self.path.exists():
            return {'version': 2, 'accounts': [], 'active_account': ''}
        data = json.loads(self.path.read_text('utf-8'))
        if not isinstance(data, dict):
            raise ValueError('Invalid Gmail account configuration.')
        return data

    def _write(self, data):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
        temporary.replace(self.path)

    def accounts(self):
        with _LOCK:
            return [dict(a) for a in self._read().get('accounts', [])]

    def get(self, account_id):
        return next((a for a in self.accounts() if a['id'] == account_id), None)

    @property
    def active_id(self):
        with _LOCK:
            return self._read().get('active_account', '')

    def add(self, label, endpoint=''):
        label = str(label).strip()
        if not label or len(label) > 100:
            raise ValueError('Choose an account label between 1 and 100 characters.')
        endpoint = validate_endpoint(endpoint)
        with _LOCK:
            data = self._read()
            accounts = data.setdefault('accounts', [])
            if any(a['label'].casefold() == label.casefold() for a in accounts):
                raise ValueError('An account with this label already exists.')
            account_id = secrets.token_hex(12)
            self.secrets.set(self._key(account_id), secrets.token_urlsafe(32))
            accounts.append({'id': account_id, 'label': label, 'endpoint': endpoint, 'paired': False})
            # Adding an unpaired account must not replace a working selection.
            data.setdefault('active_account', '')
            data['version'] = 2
            self._write(data)
            return account_id

    def update(self, account_id, **fields):
        if set(fields) - {'endpoint', 'paired'}:
            raise ValueError('Unsupported account update.')
        if 'endpoint' in fields:
            fields['endpoint'] = validate_endpoint(fields['endpoint'])
        with _LOCK:
            data = self._read()
            account = next((a for a in data.get('accounts', []) if a['id'] == account_id), None)
            if account is None:
                raise ValueError('This Gmail account was removed.')
            account.update(fields)
            if fields.get('paired') and not data.get('active_account'):
                data['active_account'] = account_id
            self._write(data)

    def select(self, account_id):
        with _LOCK:
            data = self._read()
            account = next((a for a in data.get('accounts', []) if a['id'] == account_id), None)
            if not account or not account.get('paired') or not account.get('endpoint'):
                raise ValueError('Connect this account before selecting it for imports.')
            data['active_account'] = account_id
            self._write(data)

    def channel(self, account_id):
        if not self.get(account_id):
            raise ValueError('This Gmail account was removed.')
        value = self.secrets.get(self._key(account_id))
        if not value:
            raise ValueError('The pairing key is unavailable. Remove this account and connect it again.')
        return value

    def reset(self, account_id):
        with _LOCK:
            if not self.get(account_id):
                raise ValueError('This Gmail account was removed.')
            self.secrets.set(self._key(account_id), secrets.token_urlsafe(32))
            self.update(account_id, paired=False)

    def remove(self, account_id):
        with _LOCK:
            data = self._read()
            data['accounts'] = [a for a in data.get('accounts', []) if a['id'] != account_id]
            if data.get('active_account') == account_id:
                data['active_account'] = next((a['id'] for a in data['accounts'] if a.get('paired') and a.get('endpoint')), '')
            self._write(data)
            self.secrets.delete(self._key(account_id))
