from __future__ import annotations

import base64
import hashlib
import hmac
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from .google_tls import google_ssl_context


CONFIG_FILENAME = "gmail_addon.json"
ENV_ENDPOINT = "PRIVACYGATE_GMAIL_ADDON_ENDPOINT"
MAX_ATTACHMENT_BYTES = 6 * 1024 * 1024

MODE_ACTION = "action"


@dataclass(frozen=True)
class GmailAddonAttachment:
    filename: str
    mime_type: str
    data: bytes


@dataclass(frozen=True)
class GmailAddonMessage:
    message_id: str
    thread_id: str
    subject: str
    sender: str
    recipients: str
    sent_at: str
    body: str
    attachments: tuple[GmailAddonAttachment, ...]


class GmailAddonTransport:
    """One independently paired Gmail account; explicit current-message action only."""
    def __init__(self, data_dir: Path, *, account_id=None, registry=None):
        from .gmail_addon_accounts import GmailAccountRegistry
        self.registry = registry or GmailAccountRegistry(data_dir)
        self.data_dir = Path(data_dir)
        self.account_id = account_id or self.registry.active_id
        if not self.registry.get(self.account_id):
            raise ValueError('Connect a Gmail account in Apps first.')

    @property
    def channel(self):
        return self.registry.channel(self.account_id)

    @property
    def endpoint(self):
        account = self.registry.get(self.account_id)
        return account.get('endpoint', '') if account else ''

    @property
    def paired(self):
        account = self.registry.get(self.account_id)
        return bool(account and account.get('paired'))

    def set_endpoint(self, endpoint):
        self.registry.update(self.account_id, endpoint=endpoint, paired=False)

    def mark_paired(self, paired=True):
        self.registry.update(self.account_id, paired=bool(paired))

    def reset_pairing(self):
        self.registry.reset(self.account_id)

    def check_pairing(self, timeout: float = 2.5) -> bool:
        if not self.endpoint:
            return False
        data = self._post({"action": "status", "channel": self.channel}, timeout)
        paired = bool(data.get("paired"))
        if paired and not self.paired:
            self.mark_paired(True)
        return paired

    def poll(self, timeout: float = 2.5) -> GmailAddonMessage | None:
        if not self.endpoint:
            return None
        data = self._post({"action": "poll", "channel": self.channel}, timeout)
        if not bool(data.get("ready")):
            return None

        payload_b64 = str(data.get("payload_b64") or "")
        signature = str(data.get("signature") or "")
        if not payload_b64 or not signature:
            raise RuntimeError("The Gmail add-on relay returned an incomplete payload.")

        expected = base64.urlsafe_b64encode(
            hmac.new(
                self.channel.encode("utf-8"),
                payload_b64.encode("ascii"),
                hashlib.sha256,
            ).digest()
        ).decode("ascii").rstrip("=")
        if not hmac.compare_digest(expected, signature.rstrip("=")):
            raise RuntimeError("Gmail add-on payload signature verification failed.")

        raw = _decode_websafe(payload_b64)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("The Gmail add-on returned invalid message data.") from exc
        return _message_from_payload(payload)

    def materialize_attachment(self, attachment: GmailAddonAttachment) -> Path:
        safe_name = Path(attachment.filename or "gmail-attachment.bin").name
        folder = Path(tempfile.mkdtemp(prefix="privacygate-gmail-"))
        path = folder / safe_name
        path.write_bytes(attachment.data)
        return path

    def _post(self, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        try:
            response = httpx.post(
                self.endpoint,
                json=payload,
                timeout=timeout,
                verify=google_ssl_context(),
                follow_redirects=True,
                headers={"User-Agent": "PrivacyGate-Gmail-Addon/0.5"},
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError("PrivacyGate could not reach the Gmail add-on relay.") from exc
        except ValueError as exc:
            raise RuntimeError("The Gmail add-on relay returned an invalid response.") from exc

        if not isinstance(data, dict):
            raise RuntimeError("The Gmail add-on relay returned an invalid response.")
        if data.get("ok") is False:
            raise RuntimeError(str(data.get("error") or "Gmail add-on relay error."))
        return data


def _decode_websafe(value: str) -> bytes:
    padded = value + ("=" * ((4 - len(value) % 4) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _message_from_payload(payload: dict[str, Any]) -> GmailAddonMessage:
    attachments: list[GmailAddonAttachment] = []
    for item in payload.get("attachments") or ():
        if not isinstance(item, dict):
            continue
        encoded = str(item.get("data_b64") or "")
        if not encoded:
            continue
        try:
            data = _decode_websafe(encoded)
        except Exception as exc:
            raise RuntimeError("One Gmail attachment could not be decoded.") from exc
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise RuntimeError(
                f"{item.get('filename') or 'Attachment'} is too large for the Gmail add-on import path."
            )
        attachments.append(
            GmailAddonAttachment(
                filename=Path(str(item.get("filename") or "attachment.bin")).name,
                mime_type=str(item.get("mime_type") or "application/octet-stream"),
                data=data,
            )
        )

    return GmailAddonMessage(
        message_id=str(payload.get("message_id") or ""),
        thread_id=str(payload.get("thread_id") or ""),
        subject=str(payload.get("subject") or "(No subject)"),
        sender=str(payload.get("sender") or ""),
        recipients=str(payload.get("recipients") or ""),
        sent_at=str(payload.get("sent_at") or ""),
        body=str(payload.get("body") or ""),
        attachments=tuple(attachments),
    )
