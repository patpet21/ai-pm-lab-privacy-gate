from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ai_pm_lab_privacy_gate.domain.models import LibraryDocument, ProtectionResult, ReplacementMapping
from ai_pm_lab_privacy_gate.infrastructure.security.local_protector import LocalProtector


SCHEMA_VERSION = 1


def default_data_dir() -> Path:
    override = os.environ.get("PRIVACY_GATE_DATA_DIR")
    if override:
        return Path(override)
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return root / "AI PM LAB Privacy Gate" / "Data"


class LibraryRepository:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir = self.data_dir / "Backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "library.db"
        self._protector = LocalProtector()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    profile_key TEXT NOT NULL,
                    protected_text TEXT NOT NULL,
                    findings_count INTEGER NOT NULL,
                    entity_types_json TEXT NOT NULL,
                    labels_json TEXT NOT NULL,
                    replacement_mode TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    has_mapping INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS mappings (
                    document_id TEXT NOT NULL,
                    token TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    protected_value BLOB NOT NULL,
                    PRIMARY KEY (document_id, token),
                    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
                );
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO app_meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def save(
        self,
        *,
        title: str,
        source_kind: str,
        source_name: str,
        profile_key: str,
        result: ProtectionResult,
        labels: tuple[str, ...] = (),
    ) -> LibraryDocument:
        now = datetime.now(timezone.utc)
        document_id = uuid.uuid4().hex
        entity_types = tuple(sorted({item.entity_type for item in result.applied_findings}))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents(
                    document_id, title, source_kind, source_name, profile_key,
                    protected_text, findings_count, entity_types_json, labels_json,
                    replacement_mode, created_at, updated_at, has_mapping
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    title.strip() or "Untitled protected document",
                    source_kind,
                    source_name,
                    profile_key,
                    result.combined_text,
                    len(result.applied_findings),
                    json.dumps(entity_types),
                    json.dumps(tuple(label.strip() for label in labels if label.strip())),
                    result.replacement_mode,
                    now.isoformat(),
                    now.isoformat(),
                    int(bool(result.mappings)),
                ),
            )
            connection.executemany(
                "INSERT INTO mappings(document_id, token, entity_type, protected_value) VALUES (?, ?, ?, ?)",
                [
                    (
                        document_id,
                        mapping.token,
                        mapping.entity_type,
                        self._protector.protect(mapping.original_text),
                    )
                    for mapping in result.mappings
                ],
            )
        return self.get(document_id)

    def list_documents(self, search: str = "") -> tuple[LibraryDocument, ...]:
        query = "SELECT * FROM documents"
        parameters: tuple[str, ...] = ()
        if search.strip():
            query += " WHERE title LIKE ? OR source_name LIKE ? OR labels_json LIKE ?"
            term = f"%{search.strip()}%"
            parameters = (term, term, term)
        query += " ORDER BY updated_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(self._to_document(row) for row in rows)

    def get(self, document_id: str) -> LibraryDocument:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE document_id = ?", (document_id,)
            ).fetchone()
        if row is None:
            raise KeyError(document_id)
        return self._to_document(row)

    def get_mappings(self, document_id: str) -> tuple[ReplacementMapping, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT token, entity_type, protected_value FROM mappings WHERE document_id = ? ORDER BY token",
                (document_id,),
            ).fetchall()
        return tuple(
            ReplacementMapping(
                token=row["token"],
                entity_type=row["entity_type"],
                original_text=self._protector.unprotect(row["protected_value"]),
            )
            for row in rows
        )

    def delete(self, document_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))

    @staticmethod
    def _to_document(row: sqlite3.Row) -> LibraryDocument:
        return LibraryDocument(
            document_id=row["document_id"],
            title=row["title"],
            source_kind=row["source_kind"],
            source_name=row["source_name"],
            profile_key=row["profile_key"],
            protected_text=row["protected_text"],
            findings_count=int(row["findings_count"]),
            entity_types=tuple(json.loads(row["entity_types_json"])),
            labels=tuple(json.loads(row["labels_json"])),
            replacement_mode=row["replacement_mode"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            has_mapping=bool(row["has_mapping"]),
        )
