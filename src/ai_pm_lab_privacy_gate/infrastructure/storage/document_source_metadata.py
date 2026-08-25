from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DocumentSourceMetadata:
    document_id: str
    provider: str
    provider_label: str
    account_id: str = ""
    account_label: str = ""
    item_id: str = ""
    item_title: str = ""
    item_kind: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentSourceMetadataRepository:
    """Local provenance metadata for Library documents.

    This table deliberately stores no document contents, OAuth tokens, restore
    mappings or MCP state.  It only records which connector/account/item supplied
    a document so the local Library can organize content as provider -> account.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS document_source_metadata (
                    document_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    provider_label TEXT NOT NULL,
                    account_id TEXT NOT NULL DEFAULT '',
                    account_label TEXT NOT NULL DEFAULT '',
                    item_id TEXT NOT NULL DEFAULT '',
                    item_title TEXT NOT NULL DEFAULT '',
                    item_kind TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
                )
                """
            )

    def upsert(
        self,
        *,
        document_id: str,
        provider: str,
        provider_label: str,
        account_id: str = "",
        account_label: str = "",
        item_id: str = "",
        item_title: str = "",
        item_kind: str = "",
    ) -> DocumentSourceMetadata:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO document_source_metadata(
                    document_id, provider, provider_label, account_id, account_label,
                    item_id, item_title, item_kind, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    provider = excluded.provider,
                    provider_label = excluded.provider_label,
                    account_id = excluded.account_id,
                    account_label = excluded.account_label,
                    item_id = excluded.item_id,
                    item_title = excluded.item_title,
                    item_kind = excluded.item_kind,
                    updated_at = excluded.updated_at
                """,
                (
                    document_id,
                    provider.strip(),
                    provider_label.strip(),
                    account_id.strip(),
                    account_label.strip(),
                    item_id.strip(),
                    item_title.strip(),
                    item_kind.strip(),
                    now,
                    now,
                ),
            )
        metadata = self.get(document_id)
        if metadata is None:
            raise RuntimeError("Unable to persist document source metadata.")
        return metadata

    def get(self, document_id: str) -> DocumentSourceMetadata | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM document_source_metadata WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return self._to_metadata(row) if row is not None else None

    def list_for_documents(
        self, document_ids: tuple[str, ...] | list[str]
    ) -> dict[str, DocumentSourceMetadata]:
        ids = tuple(dict.fromkeys(str(item) for item in document_ids if str(item)))
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM document_source_metadata WHERE document_id IN ({placeholders})",
                ids,
            ).fetchall()
        return {row["document_id"]: self._to_metadata(row) for row in rows}

    @staticmethod
    def _to_metadata(row: sqlite3.Row) -> DocumentSourceMetadata:
        return DocumentSourceMetadata(
            document_id=row["document_id"],
            provider=row["provider"],
            provider_label=row["provider_label"],
            account_id=row["account_id"],
            account_label=row["account_label"],
            item_id=row["item_id"],
            item_title=row["item_title"],
            item_kind=row["item_kind"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
