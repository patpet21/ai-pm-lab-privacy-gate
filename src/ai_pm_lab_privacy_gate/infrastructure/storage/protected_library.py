from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ProtectedDocument:
    document_id: str
    title: str
    profile_key: str
    protected_text: str
    findings_count: int
    entity_types: tuple[str, ...]
    updated_at: datetime
    favorite: bool
    labels: tuple[str, ...] = ()
    source_kind: str = "protected"


class ProtectedDocumentSource(Protocol):
    def list_mcp_documents(
        self, search: str = "", *, favorites_only: bool = False, limit: int = 50
    ) -> tuple[ProtectedDocument, ...]: ...

    def get_mcp_document(self, document_id: str) -> ProtectedDocument: ...


class ProtectedLibraryRepository:
    """A physically separate store containing no originals, mappings, or restore keys."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "protected_library.db"
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
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
                CREATE TABLE IF NOT EXISTS protected_documents (
                    document_id TEXT PRIMARY KEY,
                    safe_title TEXT NOT NULL,
                    profile_key TEXT NOT NULL,
                    protected_text TEXT NOT NULL,
                    findings_count INTEGER NOT NULL,
                    entity_types_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    favorite INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    def publish(
        self,
        *,
        document_id: str,
        profile_key: str,
        protected_text: str,
        findings_count: int,
        entity_types: tuple[str, ...],
        updated_at: datetime,
        favorite: bool,
    ) -> None:
        safe_title = f"Protected document {document_id[:8].upper()}"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO protected_documents(
                    document_id, safe_title, profile_key, protected_text,
                    findings_count, entity_types_json, updated_at, favorite
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    safe_title=excluded.safe_title,
                    profile_key=excluded.profile_key,
                    protected_text=excluded.protected_text,
                    findings_count=excluded.findings_count,
                    entity_types_json=excluded.entity_types_json,
                    updated_at=excluded.updated_at,
                    favorite=excluded.favorite
                """,
                (
                    document_id,
                    safe_title,
                    profile_key,
                    protected_text,
                    int(findings_count),
                    json.dumps(tuple(entity_types)),
                    updated_at.isoformat(),
                    int(favorite),
                ),
            )

    def withdraw(self, document_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM protected_documents WHERE document_id = ?", (document_id,)
            )

    def list_mcp_documents(
        self,
        search: str = "",
        *,
        favorites_only: bool = False,
        limit: int = 50,
    ) -> tuple[ProtectedDocument, ...]:
        query = "SELECT * FROM protected_documents WHERE 1 = 1"
        parameters: list[object] = []
        if favorites_only:
            query += " AND favorite = 1"
        if search.strip():
            query += " AND (safe_title LIKE ? OR profile_key LIKE ? OR protected_text LIKE ?)"
            term = f"%{search.strip()}%"
            parameters.extend((term, term, term))
        query += " ORDER BY updated_at DESC LIMIT ?"
        parameters.append(max(1, min(int(limit), 200)))
        with self._connect() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
        return tuple(self._to_document(row) for row in rows)

    def get_mcp_document(self, document_id: str) -> ProtectedDocument:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM protected_documents WHERE document_id = ?", (document_id,)
            ).fetchone()
        if row is None:
            raise KeyError(document_id)
        return self._to_document(row)

    @staticmethod
    def _to_document(row: sqlite3.Row) -> ProtectedDocument:
        return ProtectedDocument(
            document_id=row["document_id"],
            title=row["safe_title"],
            profile_key=row["profile_key"],
            protected_text=row["protected_text"],
            findings_count=int(row["findings_count"]),
            entity_types=tuple(json.loads(row["entity_types_json"])),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            favorite=bool(row["favorite"]),
        )

