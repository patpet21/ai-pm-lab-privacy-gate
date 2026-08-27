from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ActivityIntegrityResult:
    ok: bool
    chained_events: int
    message: str


@dataclass(frozen=True, slots=True)
class DocumentIntegrityResult:
    ok: bool
    status: str
    message: str
    composite_hash: str = ""


@dataclass(frozen=True, slots=True)
class DocumentGovernanceMetadata:
    document_id: str
    workspace_key: str
    workspace_name: str
    policy_version: int
    provenance_scope: str
    integrity_origin: str
    protected_hash: str
    mapping_hash: str
    composite_hash: str
    created_at: str
    verified_at: str


class GovernancePreferencesStore:
    """Local-only governance preferences; never synchronized to the control plane."""

    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir) / "governance_preferences.json"

    def load(self) -> dict[str, object]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def save(self, payload: Mapping[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(dict(payload), indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(self.path)

    def retention_days(self) -> int:
        raw = self.load().get("activity_retention_days", 0)
        try:
            return max(0, int(raw or 0))
        except (TypeError, ValueError):
            return 0

    def set_retention_days(self, days: int) -> None:
        payload = self.load()
        payload["activity_retention_days"] = max(0, int(days))
        self.save(payload)


_ACTIVITY_COLUMNS = {
    "previous_hash": "TEXT NOT NULL DEFAULT ''",
    "event_hash": "TEXT NOT NULL DEFAULT ''",
    "ai_destination": "TEXT NOT NULL DEFAULT ''",
    "policy_version": "INTEGER NOT NULL DEFAULT 0",
    "risk_level": "TEXT NOT NULL DEFAULT ''",
    "protection_mode": "TEXT NOT NULL DEFAULT ''",
    "provenance_scope": "TEXT NOT NULL DEFAULT 'local-only'",
    "record_version": "INTEGER NOT NULL DEFAULT 2",
}


def _safe_text(value: object, limit: int = 240) -> str:
    return str(value or "").replace("\n", " ").strip()[:limit]


def _activity_payload(row: Mapping[str, object], previous_hash: str) -> bytes:
    payload = {
        "event_id": str(row.get("event_id") or ""),
        "created_at": str(row.get("created_at") or ""),
        "event_type": str(row.get("event_type") or ""),
        "workspace_key": str(row.get("workspace_key") or ""),
        "source_kind": str(row.get("source_kind") or ""),
        "source_hash": str(row.get("source_hash") or ""),
        "findings_count": int(row.get("findings_count") or 0),
        "status": str(row.get("status") or ""),
        "detail": str(row.get("detail") or ""),
        "ai_destination": str(row.get("ai_destination") or ""),
        "policy_version": int(row.get("policy_version") or 0),
        "risk_level": str(row.get("risk_level") or ""),
        "protection_mode": str(row.get("protection_mode") or ""),
        "provenance_scope": str(row.get("provenance_scope") or "local-only"),
        "previous_hash": previous_hash,
        "record_version": int(row.get("record_version") or 2),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _event_hash(row: Mapping[str, object], previous_hash: str) -> str:
    return hashlib.sha256(_activity_payload(row, previous_hash)).hexdigest()


def ensure_activity_schema(store: object) -> None:
    path = Path(getattr(store, "path"))
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(activity)").fetchall()
        }
        for name, definition in _ACTIVITY_COLUMNS.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE activity ADD COLUMN {name} {definition}")

        rows = connection.execute(
            "SELECT rowid, * FROM activity ORDER BY created_at ASC, rowid ASC"
        ).fetchall()
        previous = ""
        for row in rows:
            current = str(row["event_hash"] or "")
            if current:
                previous = current
                continue
            values = dict(row)
            digest = _event_hash(values, previous)
            connection.execute(
                "UPDATE activity SET previous_hash = ?, event_hash = ?, record_version = 2 WHERE rowid = ?",
                (previous, digest, int(row["rowid"])),
            )
            previous = digest


def verify_activity_integrity(store: object) -> ActivityIntegrityResult:
    ensure_activity_schema(store)
    path = Path(getattr(store, "path"))
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT rowid, * FROM activity ORDER BY created_at ASC, rowid ASC"
        ).fetchall()
    if not rows:
        return ActivityIntegrityResult(True, 0, "No local activity events yet.")

    prior = ""
    for index, row in enumerate(rows):
        values = dict(row)
        stored_previous = str(row["previous_hash"] or "")
        stored_hash = str(row["event_hash"] or "")
        # A retention purge may remove the prefix of the chain. The first retained
        # event therefore keeps its historic anchor; every subsequent link must
        # point to the immediately preceding retained event.
        if index > 0 and stored_previous != prior:
            return ActivityIntegrityResult(
                False,
                index,
                "The local activity hash chain has a broken link.",
            )
        expected = _event_hash(values, stored_previous)
        if not stored_hash or expected != stored_hash:
            return ActivityIntegrityResult(
                False,
                index,
                "The local activity hash chain does not match the stored event metadata.",
            )
        prior = stored_hash
    return ActivityIntegrityResult(
        True,
        len(rows),
        f"Verified {len(rows)} tamper-evident local event(s).",
    )


def prune_activity(store: object, days: int) -> int:
    days = max(0, int(days))
    if days <= 0:
        return 0
    ensure_activity_schema(store)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    path = Path(getattr(store, "path"))
    with sqlite3.connect(path) as connection:
        cursor = connection.execute(
            "DELETE FROM activity WHERE created_at < ?",
            (cutoff,),
        )
        return max(0, int(cursor.rowcount or 0))


_ACTIVITY_PATCHED = False


def install_activity_hardening() -> None:
    """Upgrade LocalActivityStore additively with hash-chain and governance fields."""
    global _ACTIVITY_PATCHED
    if _ACTIVITY_PATCHED:
        return
    _ACTIVITY_PATCHED = True

    from ai_pm_lab_privacy_gate.application.feature_suite import LocalActivityStore

    previous_init = LocalActivityStore.__init__

    def init(self, data_dir) -> None:
        previous_init(self, data_dir)
        ensure_activity_schema(self)

    def record(
        self,
        event_type: str,
        *,
        workspace_key: str = "personal",
        source: str | Path | None = None,
        source_kind: str = "",
        findings_count: int = 0,
        status: str = "ok",
        detail: str = "",
        ai_destination: str = "",
        policy_version: int = 0,
        risk_level: str = "",
        protection_mode: str = "",
        provenance_scope: str = "local-only",
    ) -> None:
        ensure_activity_schema(self)
        event_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        path = Path(self.path)
        with sqlite3.connect(path) as connection:
            connection.row_factory = sqlite3.Row
            previous_row = connection.execute(
                "SELECT event_hash FROM activity ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
            previous_hash = str(previous_row["event_hash"] or "") if previous_row else ""
            row = {
                "event_id": event_id,
                "created_at": created_at,
                "event_type": _safe_text(event_type, 80),
                "workspace_key": _safe_text(workspace_key or "personal", 160),
                "source_kind": _safe_text(source_kind, 80),
                "source_hash": self._hash_source(source),
                "findings_count": max(0, int(findings_count)),
                "status": _safe_text(status or "ok", 40),
                "detail": _safe_text(detail, 240),
                "ai_destination": _safe_text(ai_destination, 80),
                "policy_version": max(0, int(policy_version or 0)),
                "risk_level": _safe_text(risk_level, 16),
                "protection_mode": _safe_text(protection_mode, 40),
                "provenance_scope": _safe_text(provenance_scope or "local-only", 40),
                "record_version": 2,
            }
            digest = _event_hash(row, previous_hash)
            connection.execute(
                """
                INSERT INTO activity(
                    event_id, created_at, event_type, workspace_key, source_kind,
                    source_hash, findings_count, status, detail, previous_hash,
                    event_hash, ai_destination, policy_version, risk_level,
                    protection_mode, provenance_scope, record_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["event_id"], row["created_at"], row["event_type"],
                    row["workspace_key"], row["source_kind"], row["source_hash"],
                    row["findings_count"], row["status"], row["detail"],
                    previous_hash, digest, row["ai_destination"],
                    row["policy_version"], row["risk_level"],
                    row["protection_mode"], row["provenance_scope"], 2,
                ),
            )

        days = GovernancePreferencesStore(path.parent).retention_days()
        if days > 0:
            prune_activity(self, days)

    LocalActivityStore.__init__ = init
    LocalActivityStore.record = record
    LocalActivityStore.verify_integrity = verify_activity_integrity  # type: ignore[attr-defined]


class DocumentGovernanceRepository:
    """Local metadata + integrity hashes for Library documents.

    It stores no original document values and no extra protected document copy.
    The protected-text and encrypted-mapping hashes are calculated over the bytes
    already stored in library.db.
    """

    def __init__(self, library: object) -> None:
        self.library = library
        self.db_path = Path(getattr(library, "db_path"))
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
                CREATE TABLE IF NOT EXISTS document_governance_metadata (
                    document_id TEXT PRIMARY KEY,
                    workspace_key TEXT NOT NULL DEFAULT 'legacy',
                    workspace_name TEXT NOT NULL DEFAULT 'Legacy / local',
                    policy_version INTEGER NOT NULL DEFAULT 0,
                    provenance_scope TEXT NOT NULL DEFAULT 'local-only',
                    integrity_origin TEXT NOT NULL DEFAULT 'captured',
                    protected_hash TEXT NOT NULL,
                    mapping_hash TEXT NOT NULL,
                    composite_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    verified_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
                )
                """
            )

    def _hash_material(self, document_id: str) -> tuple[str, str, str]:
        with self._connect() as connection:
            document = connection.execute(
                "SELECT document_id, protected_text, replacement_mode, profile_key FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            if document is None:
                raise KeyError(document_id)
            mappings = connection.execute(
                "SELECT token, entity_type, protected_value FROM mappings WHERE document_id = ? ORDER BY token, entity_type",
                (document_id,),
            ).fetchall()

        protected_hash = hashlib.sha256(
            str(document["protected_text"] or "").encode("utf-8", errors="surrogatepass")
        ).hexdigest()
        mapping_digest = hashlib.sha256()
        for row in mappings:
            mapping_digest.update(str(row["token"] or "").encode("utf-8"))
            mapping_digest.update(b"\0")
            mapping_digest.update(str(row["entity_type"] or "").encode("utf-8"))
            mapping_digest.update(b"\0")
            value = row["protected_value"]
            if isinstance(value, memoryview):
                value = value.tobytes()
            elif not isinstance(value, (bytes, bytearray)):
                value = bytes(value or b"")
            mapping_digest.update(bytes(value))
            mapping_digest.update(b"\0")
        mapping_hash = mapping_digest.hexdigest()
        composite = hashlib.sha256(
            "|".join(
                (
                    document_id,
                    protected_hash,
                    mapping_hash,
                    str(document["replacement_mode"] or ""),
                    str(document["profile_key"] or ""),
                )
            ).encode("utf-8")
        ).hexdigest()
        return protected_hash, mapping_hash, composite

    def capture(
        self,
        document_id: str,
        *,
        workspace_key: str = "personal",
        workspace_name: str = "Personal",
        policy_version: int = 0,
        provenance_scope: str = "local-only",
        integrity_origin: str = "captured",
    ) -> DocumentGovernanceMetadata:
        protected_hash, mapping_hash, composite = self._hash_material(document_id)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO document_governance_metadata(
                    document_id, workspace_key, workspace_name, policy_version,
                    provenance_scope, integrity_origin, protected_hash, mapping_hash,
                    composite_hash, created_at, verified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    workspace_key = excluded.workspace_key,
                    workspace_name = excluded.workspace_name,
                    policy_version = excluded.policy_version,
                    provenance_scope = excluded.provenance_scope,
                    protected_hash = excluded.protected_hash,
                    mapping_hash = excluded.mapping_hash,
                    composite_hash = excluded.composite_hash,
                    verified_at = excluded.verified_at
                """,
                (
                    document_id,
                    str(workspace_key or "personal"),
                    str(workspace_name or "Personal"),
                    max(0, int(policy_version or 0)),
                    str(provenance_scope or "local-only"),
                    str(integrity_origin or "captured"),
                    protected_hash,
                    mapping_hash,
                    composite,
                    now,
                    now,
                ),
            )
        metadata = self.get(document_id)
        if metadata is None:
            raise RuntimeError("Unable to persist document governance metadata.")
        return metadata

    def get(self, document_id: str) -> DocumentGovernanceMetadata | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM document_governance_metadata WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentGovernanceMetadata(
            document_id=str(row["document_id"]),
            workspace_key=str(row["workspace_key"]),
            workspace_name=str(row["workspace_name"]),
            policy_version=int(row["policy_version"] or 0),
            provenance_scope=str(row["provenance_scope"]),
            integrity_origin=str(row["integrity_origin"]),
            protected_hash=str(row["protected_hash"]),
            mapping_hash=str(row["mapping_hash"]),
            composite_hash=str(row["composite_hash"]),
            created_at=str(row["created_at"]),
            verified_at=str(row["verified_at"]),
        )

    def ensure_baseline(self, document_id: str) -> DocumentGovernanceMetadata:
        existing = self.get(document_id)
        if existing is not None:
            return existing
        return self.capture(
            document_id,
            workspace_key="legacy",
            workspace_name="Legacy / local",
            policy_version=0,
            provenance_scope="local-only",
            integrity_origin="legacy-baseline",
        )

    def verify(self, document_id: str) -> DocumentIntegrityResult:
        metadata = self.ensure_baseline(document_id)
        protected_hash, mapping_hash, composite = self._hash_material(document_id)
        ok = (
            protected_hash == metadata.protected_hash
            and mapping_hash == metadata.mapping_hash
            and composite == metadata.composite_hash
        )
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "UPDATE document_governance_metadata SET verified_at = ? WHERE document_id = ?",
                (now, document_id),
            )
        if not ok:
            return DocumentIntegrityResult(
                False,
                "failed",
                "Integrity check failed: the protected copy or encrypted restore mapping changed after it was recorded.",
                composite,
            )
        if metadata.integrity_origin == "legacy-baseline":
            return DocumentIntegrityResult(
                True,
                "legacy-baseline",
                "Legacy item baseline recorded locally; future changes can now be detected.",
                composite,
            )
        return DocumentIntegrityResult(
            True,
            "verified",
            "Protected copy and encrypted restore mapping match their local integrity hashes.",
            composite,
        )
