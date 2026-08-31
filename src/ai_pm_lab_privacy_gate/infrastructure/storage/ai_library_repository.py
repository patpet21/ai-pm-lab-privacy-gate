from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ai_pm_lab_privacy_gate.domain.models import ReplacementMapping
from ai_pm_lab_privacy_gate.infrastructure.security.local_protector import LocalProtector


_ALLOWED_PROVIDERS = {"chatgpt", "claude", "gemini"}
_ALLOWED_ROLES = {"user", "assistant"}


@dataclass(frozen=True, slots=True)
class AiConversationSummary:
    session_id: str
    provider: str
    display_name: str
    turn: int
    message_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AiSessionSnapshot:
    session_id: str
    provider: str
    turn: int
    mappings: tuple[ReplacementMapping, ...]


@dataclass(frozen=True, slots=True)
class AiConversationMessage:
    session_id: str
    turn: int
    role: str
    protected_text: str
    created_at: datetime


class AiLibraryRepository:
    """Encrypted-at-rest browser AI history inside the Personal Library database.

    The existing ``library.db`` remains the single local Library archive.  AI data
    lives in dedicated tables so document/MCP semantics do not change. Prompt and
    assistant text are encrypted as well as reversible mapping values. Only
    provider, generic display name, opaque session id, turn counters and timestamps
    remain as metadata.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "library.db"
        self._protector = LocalProtector()
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ai_conversations (
                    session_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    turn INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ai_mappings (
                    session_id TEXT NOT NULL,
                    token TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    protected_value BLOB NOT NULL,
                    PRIMARY KEY (session_id, token),
                    FOREIGN KEY (session_id) REFERENCES ai_conversations(session_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ai_messages (
                    session_id TEXT NOT NULL,
                    turn INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    protected_content BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, turn, role),
                    FOREIGN KEY (session_id) REFERENCES ai_conversations(session_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_ai_conversations_provider_updated
                    ON ai_conversations(provider, updated_at DESC);
                """
            )

    @staticmethod
    def _provider(value: str) -> str:
        provider = str(value or "chatgpt").strip().lower()
        if provider not in _ALLOWED_PROVIDERS:
            raise ValueError("unsupported AI provider")
        return provider

    @staticmethod
    def _display_name(provider: str, created_at: datetime) -> str:
        label = {
            "chatgpt": "ChatGPT",
            "claude": "Claude",
            "gemini": "Gemini",
        }[provider]
        return f"{label} conversation · {created_at.astimezone().strftime('%Y-%m-%d %H:%M')}"

    def save_session(
        self,
        *,
        session_id: str,
        provider: str,
        turn: int,
        mappings: Iterable[ReplacementMapping],
        user_protected_text: str | None = None,
    ) -> None:
        provider = self._provider(provider)
        safe_turn = max(0, int(turn))
        now = datetime.now(timezone.utc)
        mappings = tuple(mappings)

        with self._connect() as connection:
            existing = connection.execute(
                "SELECT created_at, display_name FROM ai_conversations WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if existing is None:
                created_at = now
                display_name = self._display_name(provider, created_at)
                connection.execute(
                    """
                    INSERT INTO ai_conversations(
                        session_id, provider, display_name, turn, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        provider,
                        display_name,
                        safe_turn,
                        created_at.isoformat(),
                        now.isoformat(),
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE ai_conversations
                    SET provider = ?, turn = MAX(turn, ?), updated_at = ?
                    WHERE session_id = ?
                    """,
                    (provider, safe_turn, now.isoformat(), session_id),
                )

            connection.executemany(
                """
                INSERT INTO ai_mappings(session_id, token, entity_type, protected_value)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, token) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    protected_value = excluded.protected_value
                """,
                [
                    (
                        session_id,
                        mapping.token,
                        mapping.entity_type,
                        self._protector.protect(mapping.original_text),
                    )
                    for mapping in mappings
                ],
            )

            if user_protected_text is not None and safe_turn > 0:
                self._upsert_message(
                    connection,
                    session_id=session_id,
                    turn=safe_turn,
                    role="user",
                    protected_text=user_protected_text,
                    created_at=now,
                )

    def save_assistant_message(
        self,
        *,
        session_id: str,
        turn: int,
        protected_text: str,
    ) -> None:
        safe_turn = max(0, int(turn))
        if safe_turn <= 0:
            return
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM ai_conversations WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if exists is None:
                return
            self._upsert_message(
                connection,
                session_id=session_id,
                turn=safe_turn,
                role="assistant",
                protected_text=protected_text,
                created_at=now,
            )
            connection.execute(
                "UPDATE ai_conversations SET updated_at = ? WHERE session_id = ?",
                (now.isoformat(), session_id),
            )

    def _upsert_message(
        self,
        connection: sqlite3.Connection,
        *,
        session_id: str,
        turn: int,
        role: str,
        protected_text: str,
        created_at: datetime,
    ) -> None:
        if role not in _ALLOWED_ROLES:
            raise ValueError("unsupported AI message role")
        connection.execute(
            """
            INSERT INTO ai_messages(
                session_id, turn, role, protected_content, created_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id, turn, role) DO UPDATE SET
                protected_content = excluded.protected_content
            """,
            (
                session_id,
                int(turn),
                role,
                self._protector.protect(protected_text),
                created_at.isoformat(),
            ),
        )

    def load_session(self, session_id: str) -> AiSessionSnapshot | None:
        with self._connect() as connection:
            conversation = connection.execute(
                "SELECT session_id, provider, turn FROM ai_conversations WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if conversation is None:
                return None
            rows = connection.execute(
                """
                SELECT token, entity_type, protected_value
                FROM ai_mappings WHERE session_id = ? ORDER BY token
                """,
                (session_id,),
            ).fetchall()
        return AiSessionSnapshot(
            session_id=conversation["session_id"],
            provider=conversation["provider"],
            turn=int(conversation["turn"]),
            mappings=tuple(
                ReplacementMapping(
                    token=row["token"],
                    entity_type=row["entity_type"],
                    original_text=self._protector.unprotect(row["protected_value"]),
                )
                for row in rows
            ),
        )

    def list_conversations(self, *, provider: str | None = None) -> tuple[AiConversationSummary, ...]:
        parameters: list[object] = []
        query = """
            SELECT c.*, COUNT(m.role) AS message_count
            FROM ai_conversations c
            LEFT JOIN ai_messages m ON m.session_id = c.session_id
        """
        if provider is not None:
            query += " WHERE c.provider = ?"
            parameters.append(self._provider(provider))
        query += " GROUP BY c.session_id ORDER BY c.updated_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
        return tuple(
            AiConversationSummary(
                session_id=row["session_id"],
                provider=row["provider"],
                display_name=row["display_name"],
                turn=int(row["turn"]),
                message_count=int(row["message_count"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        )

    def list_messages(self, session_id: str) -> tuple[AiConversationMessage, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT session_id, turn, role, protected_content, created_at
                FROM ai_messages
                WHERE session_id = ?
                ORDER BY turn ASC, CASE role WHEN 'user' THEN 0 ELSE 1 END ASC
                """,
                (session_id,),
            ).fetchall()
        return tuple(
            AiConversationMessage(
                session_id=row["session_id"],
                turn=int(row["turn"]),
                role=row["role"],
                protected_text=self._protector.unprotect(row["protected_content"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        )

    def delete_session(self, session_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM ai_conversations WHERE session_id = ?",
                (session_id,),
            )
        return bool(cursor.rowcount)
