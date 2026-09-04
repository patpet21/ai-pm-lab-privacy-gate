from __future__ import annotations

import re
from typing import Any

from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_provider import browser_provider
from ai_pm_lab_privacy_gate.infrastructure.local_api.server import (
    LocalApiHttpServer,
    LocalApiRequestHandler,
)
from ai_pm_lab_privacy_gate.infrastructure.local_api.session_store import LocalSessionNotFound
from ai_pm_lab_privacy_gate.infrastructure.storage.ai_library_repository import AiLibraryRepository


_SESSION_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


class PersistentBrowserAiRequestHandler(LocalApiRequestHandler):
    """Add encrypted Library persistence only to authenticated browser routes.

    The proven LocalApiRequestHandler remains authoritative for validation,
    protection, authentication and restore. This subclass only rehydrates a stale
    RAM session before those methods run and snapshots successful browser Protect
    sessions afterwards. Base /v1/protect and /v1/restore behavior is unchanged.
    """

    @property
    def _ai_library(self) -> AiLibraryRepository | None:
        value = getattr(self.server, "ai_library_repository", None)
        return value if isinstance(value, AiLibraryRepository) else None

    @staticmethod
    def _candidate_session_id(payload: dict[str, Any]) -> str | None:
        value = payload.get("session_id")
        if isinstance(value, str) and _SESSION_ID_PATTERN.fullmatch(value):
            return value
        return None

    def _rehydrate_browser_session(self, payload: dict[str, Any]) -> None:
        if self.path not in {"/v1/browser/protect", "/v1/browser/restore"}:
            return
        repository = self._ai_library
        session_id = self._candidate_session_id(payload)
        if repository is None or session_id is None:
            return

        try:
            self.server.session_store.touch(session_id)
            return
        except LocalSessionNotFound:
            pass

        snapshot = repository.load_session(session_id)
        if snapshot is None:
            return
        self.server.session_store.rehydrate(
            snapshot.session_id,
            snapshot.mappings,
            turn=snapshot.turn,
        )

    def _protect(self, payload: dict[str, Any]) -> dict[str, object]:
        self._rehydrate_browser_session(payload)
        response = super()._protect(payload)

        if self.path != "/v1/browser/protect":
            return response
        repository = self._ai_library
        session_id = response.get("session_id")
        if repository is None or not isinstance(session_id, str):
            return response
        if not _SESSION_ID_PATTERN.fullmatch(session_id):
            return response

        # A reversible mapping turn is the durable unit. Non-sensitive / fully
        # deselected prompts do not create mappings and therefore do not need a
        # restore record in the AI Library.
        if int(response.get("applied_findings_count", 0) or 0) <= 0:
            return response

        turn, mappings = self.server.session_store.snapshot(session_id)
        repository.save_session(
            session_id=session_id,
            provider=browser_provider(payload),
            turn=turn,
            mappings=mappings,
            user_protected_text=str(response.get("protected_text") or ""),
        )
        return response

    def _restore(self, payload: dict[str, Any]) -> dict[str, object]:
        # Rehydration is enough for restore persistence. The protected assistant
        # message remains in the AI website and is restored locally again on page
        # load; we intentionally do not duplicate assistant text until a stable
        # message identity is supplied by the extension in a later isolated step.
        self._rehydrate_browser_session(payload)
        return super()._restore(payload)


def install_browser_ai_persistence(
    server: object,
    repository: AiLibraryRepository,
) -> bool:
    """Attach browser-only encrypted persistence without altering server.py."""
    if not isinstance(server, LocalApiHttpServer):
        return False
    server.ai_library_repository = repository
    server.RequestHandlerClass = PersistentBrowserAiRequestHandler
    return True
