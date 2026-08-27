from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from ai_pm_lab_privacy_gate.infrastructure.security.temporary_workspace import (
    as_read_once_path,
    new_working_path,
)

from .service import ConnectedAppsService, RemoteItem


SUPPORTED_ATTACHMENT_SUFFIXES = {".pdf", ".docx", ".xlsx", ".pptx", ".txt"}


@dataclass(frozen=True, slots=True)
class GmailAttachment:
    attachment_id: str
    filename: str
    mime_type: str
    part_id: str = ""
    inline_data: str = ""


def _decode(data: str) -> str:
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode((data + padding).encode("ascii")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _decode_bytes(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _collect_text(part: dict) -> list[str]:
    mime = str(part.get("mimeType") or "")
    filename = str(part.get("filename") or "").strip()
    body = part.get("body") or {}
    chunks: list[str] = []
    # A text/plain attachment can also carry body.data. Do not merge attachment
    # contents into the message body merely because Gmail encoded it inline.
    if mime == "text/plain" and not filename and body.get("data"):
        text = _decode(str(body.get("data") or "")).strip()
        if text:
            chunks.append(text)
    for child in part.get("parts") or []:
        if isinstance(child, dict):
            chunks.extend(_collect_text(child))
    return chunks


def _collect_attachments(part: dict) -> list[GmailAttachment]:
    found: list[GmailAttachment] = []
    filename = str(part.get("filename") or "").strip()
    body = part.get("body") or {}
    attachment_id = str(body.get("attachmentId") or "").strip()
    inline_data = str(body.get("data") or "").strip()
    supported = filename and Path(filename).suffix.lower() in SUPPORTED_ATTACHMENT_SUFFIXES
    if supported and (attachment_id or inline_data):
        found.append(
            GmailAttachment(
                attachment_id=attachment_id,
                filename=filename,
                mime_type=str(part.get("mimeType") or "application/octet-stream"),
                part_id=str(part.get("partId") or ""),
                inline_data=inline_data,
            )
        )
    for child in part.get("parts") or []:
        if isinstance(child, dict):
            found.extend(_collect_attachments(child))
    return found


def _headers(payload: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in payload.get("headers") or []:
        name = str(item.get("name") or "").strip().lower()
        if name in {"subject", "from", "to", "cc", "date"}:
            result[name] = str(item.get("value") or "")
    return result


def _safe_filename(title: str, suffix: str = ".txt") -> str:
    clean = re.sub(r"[^A-Za-z0-9._ -]+", "_", title).strip(" ._")
    name = clean[:120] or "gmail-message"
    if suffix and not name.lower().endswith(suffix.lower()):
        name += suffix
    return name


def _fetch_message(service: ConnectedAppsService, item: RemoteItem) -> dict:
    token = service._token("gmail")
    response = httpx.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item.item_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"format": "full"},
        timeout=service.timeout,
    )
    response.raise_for_status()
    return response.json()


def list_gmail_attachments(service: ConnectedAppsService, item: RemoteItem) -> tuple[GmailAttachment, ...]:
    """Return supported attachments for one Gmail message without downloading them."""
    message = _fetch_message(service, item)
    return tuple(_collect_attachments(message.get("payload") or {}))


def materialize_gmail_attachment(
    service: ConnectedAppsService,
    item: RemoteItem,
    attachment: GmailAttachment,
) -> Path:
    """Materialize one supported Gmail attachment in PrivacyGate's local workspace."""
    suffix = Path(attachment.filename).suffix.lower()
    if suffix not in SUPPORTED_ATTACHMENT_SUFFIXES:
        raise ValueError("Unsupported Gmail attachment format.")

    encoded = attachment.inline_data
    if not encoded:
        if not attachment.attachment_id:
            raise ValueError("Gmail did not provide attachment content.")
        token = service._token("gmail")
        response = httpx.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item.item_id}/attachments/{attachment.attachment_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=service.timeout,
        )
        response.raise_for_status()
        encoded = str(response.json().get("data") or "")
    if not encoded:
        raise ValueError("Gmail returned an empty attachment.")

    target = new_working_path("gmail", _safe_filename(attachment.filename, suffix=""))
    target.write_bytes(_decode_bytes(encoded))
    return target


def materialize_gmail_message(service: ConnectedAppsService, item: RemoteItem) -> Path:
    message = _fetch_message(service, item)
    payload = message.get("payload") or {}
    headers = _headers(payload)
    text_parts = _collect_text(payload)
    if not text_parts and not payload.get("filename") and payload.get("body", {}).get("data"):
        text_parts = [_decode(str(payload.get("body", {}).get("data") or ""))]
    body = "\n\n".join(part for part in text_parts if part.strip()).strip()
    if not body:
        body = str(message.get("snippet") or "")

    lines = [
        f"Subject: {headers.get('subject', item.title)}",
        f"From: {headers.get('from', '')}",
        f"To: {headers.get('to', '')}",
    ]
    if headers.get("cc"):
        lines.append(f"Cc: {headers['cc']}")
    if headers.get("date"):
        lines.append(f"Date: {headers['date']}")
    lines.extend(["", body])

    target = new_working_path("gmail", _safe_filename(item.title))
    target.write_text("\n".join(lines), encoding="utf-8")
    return as_read_once_path(target)
