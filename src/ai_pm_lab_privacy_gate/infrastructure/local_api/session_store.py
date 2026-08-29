from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable

from ai_pm_lab_privacy_gate.domain.models import ReplacementMapping


DEFAULT_SESSION_TTL_SECONDS = 8 * 60 * 60
DEFAULT_MAX_SESSIONS = 100


class LocalSessionNotFound(KeyError):
    """Raised when a browser/local bridge session is missing or has expired."""


@dataclass(slots=True)
class _Session:
    session_id: str
    created_at: float
    last_access: float
    turn: int = 0
    mappings: dict[str, ReplacementMapping] = field(default_factory=dict)


class LocalProtectionSessionStore:
    """Keep reversible browser mappings in memory only, never in the Library/database."""

    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        clock=time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_sessions <= 0:
            raise ValueError("max_sessions must be positive")
        self.ttl_seconds = int(ttl_seconds)
        self.max_sessions = int(max_sessions)
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[str, _Session] = {}

    def create(self) -> str:
        with self._lock:
            now = self._clock()
            self._purge_expired_locked(now)
            if len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions.values(), key=lambda item: item.last_access)
                self._sessions.pop(oldest.session_id, None)
            session_id = secrets.token_hex(16)
            while session_id in self._sessions:
                session_id = secrets.token_hex(16)
            self._sessions[session_id] = _Session(
                session_id=session_id,
                created_at=now,
                last_access=now,
            )
            return session_id

    def next_namespace(self, session_id: str) -> str:
        with self._lock:
            session = self._get_locked(session_id)
            session.turn += 1
            session.last_access = self._clock()
            return f"B{session.session_id[:8].upper()}_T{session.turn:04d}"

    def add_mappings(
        self,
        session_id: str,
        mappings: Iterable[ReplacementMapping],
    ) -> None:
        with self._lock:
            session = self._get_locked(session_id)
            for mapping in mappings:
                existing = session.mappings.get(mapping.token)
                if existing is not None and existing.original_text != mapping.original_text:
                    raise ValueError("Local session token collision")
                session.mappings[mapping.token] = mapping
            session.last_access = self._clock()

    def mappings(self, session_id: str) -> tuple[ReplacementMapping, ...]:
        with self._lock:
            session = self._get_locked(session_id)
            session.last_access = self._clock()
            return tuple(session.mappings.values())

    def touch(self, session_id: str) -> None:
        with self._lock:
            session = self._get_locked(session_id)
            session.last_access = self._clock()

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def _get_locked(self, session_id: str) -> _Session:
        now = self._clock()
        self._purge_expired_locked(now)
        session = self._sessions.get(session_id)
        if session is None:
            raise LocalSessionNotFound(session_id)
        return session

    def _purge_expired_locked(self, now: float) -> None:
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.last_access > self.ttl_seconds
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)
