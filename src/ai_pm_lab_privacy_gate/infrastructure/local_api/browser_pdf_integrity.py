from __future__ import annotations

import base64
import binascii
import io
import re
from typing import Any

from pypdf import PdfReader

from ai_pm_lab_privacy_gate.infrastructure.storage.ai_library_repository import (
    AiLibraryRepository,
)

from .browser_pdf import PersistentBrowserPdfRequestHandler
from .server import LocalApiHttpServer
from .session_store import LocalSessionNotFound


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


class IntegrityBrowserPdfRequestHandler(PersistentBrowserPdfRequestHandler):
    """Fail closed if a selected original value survives in the generated PDF."""

    def _mapping_tokens_before(self, session_id: object) -> set[str]:
        if not isinstance(session_id, str) or not session_id:
            return set()
        try:
            _turn, mappings = self.server.session_store.snapshot(session_id)
            return {mapping.token for mapping in mappings}
        except LocalSessionNotFound:
            pass

        repository = getattr(self.server, "ai_library_repository", None)
        if isinstance(repository, AiLibraryRepository):
            snapshot = repository.load_session(session_id)
            if snapshot is not None:
                return {mapping.token for mapping in snapshot.mappings}
        return set()

    def _current_mappings(self, session_id: object):
        if not isinstance(session_id, str) or not session_id:
            return ()
        try:
            _turn, mappings = self.server.session_store.snapshot(session_id)
            return mappings
        except LocalSessionNotFound:
            repository = getattr(self.server, "ai_library_repository", None)
            if isinstance(repository, AiLibraryRepository):
                snapshot = repository.load_session(session_id)
                if snapshot is not None:
                    return snapshot.mappings
        return ()

    @staticmethod
    def _pdf_text(encoded: object) -> str:
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("Protected PDF integrity check failed: output payload is missing")
        try:
            raw = base64.b64decode(encoded, validate=True)
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except (binascii.Error, ValueError, TypeError) as error:
            raise ValueError(
                "Protected PDF integrity check failed: output PDF could not be verified"
            ) from error
        except Exception as error:
            raise ValueError(
                "Protected PDF integrity check failed: output PDF could not be verified"
            ) from error

    def _protect_pdf(self, payload: dict[str, Any]) -> dict[str, object]:
        before_tokens = self._mapping_tokens_before(payload.get("session_id"))
        response = super()._protect_pdf(payload)

        session_id = response.get("session_id")
        mappings = self._current_mappings(session_id)
        current_turn_mappings = tuple(
            mapping for mapping in mappings if mapping.token not in before_tokens
        )

        protected_text = _normalized(
            self._pdf_text(response.get("protected_file_base64"))
        )
        leaked_types: list[str] = []
        for mapping in current_turn_mappings:
            original = _normalized(mapping.original_text)
            if original and original in protected_text:
                leaked_types.append(mapping.entity_type)

        if leaked_types:
            categories = ", ".join(sorted(set(leaked_types)))
            raise ValueError(
                "Protected PDF integrity check failed: selected sensitive value remains "
                f"in generated PDF ({categories})"
            )

        response["integrity_verified"] = True
        response["integrity_checked_mappings"] = len(current_turn_mappings)
        return response


def install_browser_pdf_integrity(server: object) -> bool:
    """Install only after browser PDF support; never changes the base local API."""
    if not isinstance(server, LocalApiHttpServer):
        return False
    if not hasattr(server, "browser_pdf_store"):
        return False
    server.RequestHandlerClass = IntegrityBrowserPdfRequestHandler
    return True
