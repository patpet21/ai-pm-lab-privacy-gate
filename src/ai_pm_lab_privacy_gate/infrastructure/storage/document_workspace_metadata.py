from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DocumentWorkspaceMetadata:
    """Local-only workspace ownership metadata for a protected Library item.

    This record deliberately contains no document text, restore values, connector
    credentials, user email, organization membership roster or cloud identifiers
    beyond the local workspace key already cached by PrivacyGate on this device.
    """

    document_id: str
    workspace_key: str
    workspace_name: str
    personal: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentWorkspaceMetadataRepository:
    """Persist document -> workspace context inside the local Library SQLite DB."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_schema()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
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

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS document_workspace_metadata (
                    document_id TEXT PRIMARY KEY,
                    workspace_key TEXT NOT NULL,
                    workspace_name TEXT NOT NULL,
                    personal INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_document_workspace_key "
                "ON document_workspace_metadata(workspace_key)"
            )

    def upsert(
        self,
        *,
        document_id: str,
        workspace_key: str,
        workspace_name: str,
        personal: bool,
    ) -> DocumentWorkspaceMetadata:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO document_workspace_metadata(
                    document_id, workspace_key, workspace_name, personal,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    workspace_key = excluded.workspace_key,
                    workspace_name = excluded.workspace_name,
                    personal = excluded.personal,
                    updated_at = excluded.updated_at
                """,
                (
                    document_id,
                    workspace_key.strip() or "personal",
                    workspace_name.strip() or "Personal",
                    int(bool(personal)),
                    now,
                    now,
                ),
            )
        metadata = self.get(document_id)
        if metadata is None:
            raise RuntimeError("Unable to persist local document workspace metadata.")
        return metadata

    def get(self, document_id: str) -> DocumentWorkspaceMetadata | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM document_workspace_metadata WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return self._to_metadata(row) if row is not None else None

    def list_for_documents(
        self, document_ids: tuple[str, ...] | list[str]
    ) -> dict[str, DocumentWorkspaceMetadata]:
        ids = tuple(dict.fromkeys(str(item) for item in document_ids if str(item)))
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM document_workspace_metadata WHERE document_id IN ({placeholders})",
                ids,
            ).fetchall()
        return {row["document_id"]: self._to_metadata(row) for row in rows}

    @staticmethod
    def _to_metadata(row: sqlite3.Row) -> DocumentWorkspaceMetadata:
        return DocumentWorkspaceMetadata(
            document_id=row["document_id"],
            workspace_key=row["workspace_key"],
            workspace_name=row["workspace_name"],
            personal=bool(row["personal"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
