from __future__ import annotations

import json
import io
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ai_pm_lab_privacy_gate.domain.models import LibraryDocument, ProtectionResult, ReplacementMapping
from ai_pm_lab_privacy_gate.infrastructure.security.local_protector import LocalProtector


SCHEMA_VERSION = 3
BACKUP_FORMAT = "ai-pm-lab-privacy-gate-backup-v1"


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

    def _initialize(self) -> None:
        existing_version = 0
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
                    has_mapping INTEGER NOT NULL DEFAULT 0,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    mcp_shared INTEGER NOT NULL DEFAULT 0,
                    deleted_at TEXT
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
            row = connection.execute(
                "SELECT value FROM app_meta WHERE key = 'schema_version'"
            ).fetchone()
            existing_version = int(row["value"]) if row else 0
            columns = {
                item["name"] for item in connection.execute("PRAGMA table_info(documents)").fetchall()
            }
            if "favorite" not in columns:
                self._backup_database_file(f"pre_migration_v{existing_version or 1}")
                connection.execute(
                    "ALTER TABLE documents ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0"
                )
            if "deleted_at" not in columns:
                connection.execute("ALTER TABLE documents ADD COLUMN deleted_at TEXT")
            if "mcp_shared" not in columns:
                connection.execute(
                    "ALTER TABLE documents ADD COLUMN mcp_shared INTEGER NOT NULL DEFAULT 0"
                )
            connection.execute(
                "INSERT OR REPLACE INTO app_meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def _backup_database_file(self, reason: str) -> Path | None:
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = self.backup_dir / f"library_{reason}_{timestamp}.db"
        shutil.copy2(self.db_path, destination)
        return destination

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

    def list_documents(
        self,
        search: str = "",
        *,
        include_deleted: bool = False,
        favorites_only: bool = False,
    ) -> tuple[LibraryDocument, ...]:
        query = "SELECT * FROM documents"
        conditions: list[str] = []
        parameters: list[str] = []
        conditions.append("deleted_at IS NOT NULL" if include_deleted else "deleted_at IS NULL")
        if favorites_only:
            conditions.append("favorite = 1")
        if search.strip():
            conditions.append("(title LIKE ? OR source_name LIKE ? OR labels_json LIKE ? OR profile_key LIKE ?)")
            term = f"%{search.strip()}%"
            parameters.extend((term, term, term, term))
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY updated_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
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

    def list_mcp_documents(
        self,
        search: str = "",
        *,
        favorites_only: bool = False,
        limit: int = 50,
    ) -> tuple[LibraryDocument, ...]:
        """Return only active documents explicitly approved for MCP access."""
        safe_limit = max(1, min(int(limit), 200))
        query = "SELECT * FROM documents WHERE deleted_at IS NULL AND mcp_shared = 1"
        parameters: list[object] = []
        if favorites_only:
            query += " AND favorite = 1"
        if search.strip():
            query += (
                " AND (title LIKE ? OR labels_json LIKE ? OR profile_key LIKE ? "
                "OR protected_text LIKE ?)"
            )
            term = f"%{search.strip()}%"
            parameters.extend((term, term, term, term))
        query += " ORDER BY updated_at DESC LIMIT ?"
        parameters.append(safe_limit)
        with self._connect() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
        return tuple(self._to_document(row) for row in rows)

    def get_mcp_document(self, document_id: str) -> LibraryDocument:
        """Load a document only when it is active and explicitly MCP-shared."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM documents
                WHERE document_id = ? AND deleted_at IS NULL AND mcp_shared = 1
                """,
                (document_id,),
            ).fetchone()
        if row is None:
            raise KeyError(document_id)
        return self._to_document(row)

    def update_metadata(
        self,
        document_id: str,
        *,
        title: str | None = None,
        labels: tuple[str, ...] | None = None,
    ) -> LibraryDocument:
        assignments = ["updated_at = ?"]
        parameters: list[object] = [datetime.now(timezone.utc).isoformat()]
        if title is not None:
            assignments.append("title = ?")
            parameters.append(title.strip() or "Untitled protected document")
        if labels is not None:
            assignments.append("labels_json = ?")
            parameters.append(json.dumps(tuple(label.strip() for label in labels if label.strip())))
        parameters.append(document_id)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE documents SET {', '.join(assignments)} WHERE document_id = ?",
                tuple(parameters),
            )
        return self.get(document_id)

    def set_favorite(self, document_id: str, favorite: bool) -> LibraryDocument:
        with self._connect() as connection:
            connection.execute(
                "UPDATE documents SET favorite = ?, updated_at = ? WHERE document_id = ?",
                (int(favorite), datetime.now(timezone.utc).isoformat(), document_id),
            )
        return self.get(document_id)

    def set_mcp_shared(self, document_id: str, shared: bool) -> LibraryDocument:
        with self._connect() as connection:
            connection.execute(
                "UPDATE documents SET mcp_shared = ?, updated_at = ? WHERE document_id = ?",
                (int(shared), datetime.now(timezone.utc).isoformat(), document_id),
            )
        return self.get(document_id)

    def move_to_trash(self, document_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE documents SET deleted_at = ?, updated_at = ? WHERE document_id = ?",
                (
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                    document_id,
                ),
            )

    def restore_from_trash(self, document_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE documents SET deleted_at = NULL, updated_at = ? WHERE document_id = ?",
                (datetime.now(timezone.utc).isoformat(), document_id),
            )

    def delete_permanently(self, document_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))

    def delete(self, document_id: str) -> None:
        """Compatibility alias: deletion is recoverable in schema v2."""
        self.move_to_trash(document_id)

    def create_backup(self, destination: str | Path | None = None) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = Path(destination) if destination else self.backup_dir / f"privacy_gate_{timestamp}.pgbackup"
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="privacy_gate_backup_") as temp_dir:
            snapshot = Path(temp_dir) / "library.db"
            with self._connect() as source, closing(sqlite3.connect(snapshot)) as output:
                source.backup(output)
            manifest = {
                "format": BACKUP_FORMAT,
                "schema_version": SCHEMA_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "protection": "Windows DPAPI current user",
            }
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr("manifest.json", json.dumps(manifest, indent=2))
                bundle.write(snapshot, "library.db")
            protected = self._protector.protect_bytes(archive.getvalue())
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(protected)
            os.replace(temporary, target)
        return target

    def restore_backup(self, source: str | Path) -> Path:
        source_path = Path(source)
        raw = self._protector.unprotect_bytes(source_path.read_bytes())
        with zipfile.ZipFile(io.BytesIO(raw), "r") as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
            if manifest.get("format") != BACKUP_FORMAT:
                raise ValueError("This is not a supported Privacy Gate backup.")
            database_bytes = bundle.read("library.db")
        with tempfile.NamedTemporaryFile(
            dir=self.data_dir, prefix="restore_", suffix=".db", delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(database_bytes)
        try:
            with closing(sqlite3.connect(temporary_path)) as connection:
                result = connection.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise ValueError("The backup database failed its integrity check.")
            safety_backup = self.create_backup()
            os.replace(temporary_path, self.db_path)
            self._initialize()
            return safety_backup
        finally:
            temporary_path.unlink(missing_ok=True)

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
            favorite=bool(row["favorite"]),
            mcp_shared=bool(row["mcp_shared"]),
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None,
        )
