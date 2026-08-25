from __future__ import annotations

import base64
import re
from pathlib import Path

import httpx

from ai_pm_lab_privacy_gate.infrastructure.security.temporary_workspace import new_working_path

from .service import ConnectedAppsService, RemoteItem


def _decode(data: str) -> str:
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode((data + padding).encode("ascii")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _collect_text(part: dict) -> list[str]:
    mime = str(part.get("mimeType") or "")
    body = part.get("body") or {}
    chunks: list[str] = []
    if mime == "text/plain" and body.get("data"):
        text = _decode(str(body.get("data") or "")).strip()
        if text:
            chunks.append(text)
    for child in part.get("parts") or []:
        if isinstance(child, dict):
            chunks.extend(_collect_text(child))
    return chunks


def _headers(payload: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in payload.get("headers") or []:
        name = str(item.get("name") or "").strip().lower()
        if name in {"subject", "from", "to", "cc", "date"}:
            result[name] = str(item.get("value") or "")
    return result


def _safe_filename(title: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._ -]+", "_", title).strip(" ._")
    return (clean[:90] or "gmail-message") + ".txt"


def materialize_gmail_message(service: ConnectedAppsService, item: RemoteItem) -> Path:
    token = service._token("gmail")
    response = httpx.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item.item_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"format": "full"},
        timeout=service.timeout,
    )
    response.raise_for_status()
    message = response.json()
    payload = message.get("payload") or {}
    headers = _headers(payload)
    text_parts = _collect_text(payload)
    if not text_parts and payload.get("body", {}).get("data"):
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
    return target
