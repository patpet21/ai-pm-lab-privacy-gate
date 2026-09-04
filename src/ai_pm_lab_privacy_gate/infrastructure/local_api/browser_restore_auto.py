from __future__ import annotations

import json
import re
from typing import Any

from ai_pm_lab_privacy_gate.infrastructure.storage.ai_library_repository import (
    AiLibraryRepository,
)


MAX_AUTO_RESTORE_REQUEST_BYTES = 1_000_000
MAX_AUTO_RESTORE_TEXT_CHARS = 250_000
_TOKEN_NAMESPACE_RE = re.compile(
    r"\[\[PG_B([A-F0-9]{8})_T\d{4}_[A-Z0-9_]+\]\]",
    re.IGNORECASE,
)


def _canonical_tokens(text: str) -> str:
    return str(text or "").replace("\\_", "_")


def token_session_prefixes(text: str) -> tuple[str, ...]:
    canonical = _canonical_tokens(text)
    return tuple(
        dict.fromkeys(match.group(1).lower() for match in _TOKEN_NAMESPACE_RE.finditer(canonical))
    )


def restore_from_local_ai_library(
    repository: AiLibraryRepository,
    privacy_service: Any,
    text: str,
) -> tuple[str, tuple[str, ...]]:
    prefixes = token_session_prefixes(text)
    if not prefixes:
        return text, ()

    summaries = repository.list_conversations()
    mappings_by_token: dict[str, Any] = {}
    resolved_session_ids: list[str] = []

    for prefix in prefixes:
        matches = [
            item
            for item in summaries
            if item.session_id.lower().startswith(prefix)
        ]
        # Eight hex characters are intentionally only a local lookup hint. Never
        # guess when a prefix is ambiguous.
        if len(matches) != 1:
            continue
        snapshot = repository.load_session(matches[0].session_id)
        if snapshot is None:
            continue
        resolved_session_ids.append(snapshot.session_id)
        for mapping in snapshot.mappings:
            current = mappings_by_token.get(mapping.token)
            if current is not None and current.original_text != mapping.original_text:
                # Collision means the fallback must fail closed for that token.
                continue
            mappings_by_token[mapping.token] = mapping

    if not mappings_by_token:
        return text, tuple(resolved_session_ids)

    restored = privacy_service.restore_text(
        _canonical_tokens(text),
        tuple(mappings_by_token.values()),
    )
    return restored, tuple(dict.fromkeys(resolved_session_ids))


def install_browser_restore_auto(server: object) -> bool:
    base_handler = getattr(server, "RequestHandlerClass", None)
    if base_handler is None:
        return False
    if getattr(base_handler, "_privacygate_restore_auto_support", False):
        return True

    class BrowserRestoreAutoRequestHandler(base_handler):
        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path != "/v1/browser/restore-auto":
                super().do_POST()
                return

            if self._reject_if_untrusted_transport():
                return
            if not self._browser_authorized():
                self._send_json(401, {"error": "browser_pairing_required"})
                return

            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._send_json(415, {"error": "application_json_required"})
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._send_json(411, {"error": "content_length_required"})
                return
            if length < 0 or length > MAX_AUTO_RESTORE_REQUEST_BYTES:
                self._send_json(413, {"error": "request_too_large"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"error": "invalid_json"})
                return
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "json_object_required"})
                return

            text = payload.get("text")
            if not isinstance(text, str) or not text.strip():
                self._send_json(400, {"error": "invalid_request", "message": "text must not be empty"})
                return
            if len(text) > MAX_AUTO_RESTORE_TEXT_CHARS:
                self._send_json(413, {"error": "text_too_large"})
                return

            repository = getattr(self.server, "ai_library_repository", None)
            if not isinstance(repository, AiLibraryRepository):
                self._send_json(
                    200,
                    {
                        "restored_text": text,
                        "mapping_found": False,
                        "resolved_session_count": 0,
                    },
                )
                return

            restored, session_ids = restore_from_local_ai_library(
                repository,
                self.server.privacy_service,
                text,
            )
            self._send_json(
                200,
                {
                    "restored_text": restored,
                    "mapping_found": restored != text,
                    "resolved_session_count": len(session_ids),
                },
            )

    BrowserRestoreAutoRequestHandler.__name__ = "BrowserRestoreAutoRequestHandler"
    BrowserRestoreAutoRequestHandler._privacygate_restore_auto_support = True
    server.RequestHandlerClass = BrowserRestoreAutoRequestHandler
    return True
