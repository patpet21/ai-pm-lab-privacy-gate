from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ai_pm_lab_privacy_gate.domain.automation import (
    AutomationDefinition,
    AutomationDestination,
    AutomationRunRecord,
    AutomationRunStatus,
    AutomationStatus,
    AutomationSummary,
    AutomationTriggerType,
)


SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_hash(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


class AutomationStore:
    """SQLite state for Automation Studio configuration and metadata-only runs."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "automation.db"
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
                CREATE TABLE IF NOT EXISTS automation_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS automations (
                    automation_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    trigger_config_json TEXT NOT NULL,
                    profile_key TEXT NOT NULL,
                    replacement_mode TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS automation_runs (
                    run_id TEXT PRIMARY KEY,
                    automation_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    trigger_event_hash TEXT NOT NULL,
                    source_count INTEGER NOT NULL DEFAULT 0,
                    detected_count INTEGER NOT NULL DEFAULT 0,
                    protected_count INTEGER NOT NULL DEFAULT 0,
                    residual_count INTEGER NOT NULL DEFAULT 0,
                    policy_status TEXT NOT NULL DEFAULT 'not_checked',
                    error_code TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (automation_id) REFERENCES automations(automation_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_automation_runs_started
                ON automation_runs(started_at DESC);

                CREATE INDEX IF NOT EXISTS idx_automation_runs_automation
                ON automation_runs(automation_id, started_at DESC);
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO automation_meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def save_definition(self, definition: AutomationDefinition) -> AutomationDefinition:
        now = _utc_now()
        created_at = definition.created_at or now
        updated = AutomationDefinition(
            automation_id=definition.automation_id,
            name=definition.name,
            trigger_type=definition.trigger_type,
            trigger_config=dict(definition.trigger_config),
            profile_key=definition.profile_key,
            replacement_mode=definition.replacement_mode,
            destination=definition.destination,
            workspace_id=definition.workspace_id,
            status=definition.status,
            created_at=created_at,
            updated_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO automations(
                    automation_id, name, trigger_type, trigger_config_json,
                    profile_key, replacement_mode, destination, workspace_id,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(automation_id) DO UPDATE SET
                    name = excluded.name,
                    trigger_type = excluded.trigger_type,
                    trigger_config_json = excluded.trigger_config_json,
                    profile_key = excluded.profile_key,
                    replacement_mode = excluded.replacement_mode,
                    destination = excluded.destination,
                    workspace_id = excluded.workspace_id,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    updated.automation_id,
                    updated.name,
                    updated.trigger_type.value,
                    json.dumps(dict(updated.trigger_config), sort_keys=True),
                    updated.profile_key,
                    updated.replacement_mode,
                    updated.destination.value,
                    updated.workspace_id,
                    updated.status.value,
                    updated.created_at,
                    updated.updated_at,
                ),
            )
        return updated

    def get_definition(self, automation_id: str) -> AutomationDefinition:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM automations WHERE automation_id = ?",
                (str(automation_id),),
            ).fetchone()
        if row is None:
            raise KeyError(automation_id)
        return self._definition_from_row(row)

    def list_definitions(self, *, include_archived: bool = False) -> tuple[AutomationDefinition, ...]:
        query = "SELECT * FROM automations"
        parameters: tuple[object, ...] = ()
        if not include_archived:
            query += " WHERE status != ?"
            parameters = (AutomationStatus.ARCHIVED.value,)
        query += " ORDER BY updated_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(self._definition_from_row(row) for row in rows)

    def set_status(self, automation_id: str, status: AutomationStatus) -> AutomationDefinition:
        now = _utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE automations SET status = ?, updated_at = ? WHERE automation_id = ?",
                (status.value, now, automation_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(automation_id)
        return self.get_definition(automation_id)

    def start_run(self, automation_id: str, *, trigger_event_key: str = "") -> AutomationRunRecord:
        # Ensure the referenced automation exists before writing the run.
        self.get_definition(automation_id)
        record = AutomationRunRecord(
            run_id=uuid.uuid4().hex,
            automation_id=automation_id,
            status=AutomationRunStatus.RUNNING,
            started_at=_utc_now(),
            trigger_event_hash=_event_hash(trigger_event_key),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO automation_runs(
                    run_id, automation_id, status, started_at, finished_at,
                    trigger_event_hash, source_count, detected_count,
                    protected_count, residual_count, policy_status, error_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.automation_id,
                    record.status.value,
                    record.started_at,
                    record.finished_at,
                    record.trigger_event_hash,
                    record.source_count,
                    record.detected_count,
                    record.protected_count,
                    record.residual_count,
                    record.policy_status,
                    record.error_code,
                ),
            )
        return record

    def finish_run(
        self,
        run_id: str,
        *,
        status: AutomationRunStatus,
        source_count: int = 0,
        detected_count: int = 0,
        protected_count: int = 0,
        residual_count: int = 0,
        policy_status: str = "not_checked",
        error_code: str = "",
    ) -> AutomationRunRecord:
        if status is AutomationRunStatus.RUNNING:
            raise ValueError("finish_run requires a terminal run status")
        counts = (source_count, detected_count, protected_count, residual_count)
        if any(int(value) < 0 for value in counts):
            raise ValueError("Automation run counters cannot be negative")

        finished_at = _utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE automation_runs
                SET status = ?, finished_at = ?, source_count = ?, detected_count = ?,
                    protected_count = ?, residual_count = ?, policy_status = ?, error_code = ?
                WHERE run_id = ?
                """,
                (
                    status.value,
                    finished_at,
                    int(source_count),
                    int(detected_count),
                    int(protected_count),
                    int(residual_count),
                    str(policy_status or "not_checked"),
                    str(error_code or ""),
                    run_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(run_id)
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> AutomationRunRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM automation_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return self._run_from_row(row)

    def list_runs(
        self,
        *,
        automation_id: str = "",
        limit: int = 100,
    ) -> tuple[AutomationRunRecord, ...]:
        safe_limit = max(1, min(int(limit), 500))
        query = "SELECT * FROM automation_runs"
        parameters: list[object] = []
        if automation_id:
            query += " WHERE automation_id = ?"
            parameters.append(automation_id)
        query += " ORDER BY started_at DESC LIMIT ?"
        parameters.append(safe_limit)
        with self._connect() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
        return tuple(self._run_from_row(row) for row in rows)

    def summary(self, *, day_prefix: str | None = None) -> AutomationSummary:
        prefix = day_prefix or datetime.now(timezone.utc).date().isoformat()
        with self._connect() as connection:
            active = connection.execute(
                "SELECT COUNT(*) AS count FROM automations WHERE status = ?",
                (AutomationStatus.ACTIVE.value,),
            ).fetchone()["count"]
            runs_today = connection.execute(
                "SELECT COUNT(*) AS count FROM automation_runs WHERE started_at LIKE ?",
                (f"{prefix}%",),
            ).fetchone()["count"]
            waiting = connection.execute(
                "SELECT COUNT(*) AS count FROM automation_runs WHERE status = ?",
                (AutomationRunStatus.NEEDS_REVIEW.value,),
            ).fetchone()["count"]
            blocked = connection.execute(
                "SELECT COUNT(*) AS count FROM automation_runs WHERE status = ?",
                (AutomationRunStatus.BLOCKED.value,),
            ).fetchone()["count"]
        return AutomationSummary(
            active_automations=int(active),
            runs_today=int(runs_today),
            waiting_approval=int(waiting),
            blocked_by_policy=int(blocked),
        )

    @staticmethod
    def _definition_from_row(row: sqlite3.Row) -> AutomationDefinition:
        return AutomationDefinition(
            automation_id=row["automation_id"],
            name=row["name"],
            trigger_type=AutomationTriggerType(row["trigger_type"]),
            trigger_config=json.loads(row["trigger_config_json"] or "{}"),
            profile_key=row["profile_key"],
            replacement_mode=row["replacement_mode"],
            destination=AutomationDestination(row["destination"]),
            workspace_id=row["workspace_id"],
            status=AutomationStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> AutomationRunRecord:
        return AutomationRunRecord(
            run_id=row["run_id"],
            automation_id=row["automation_id"],
            status=AutomationRunStatus(row["status"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            trigger_event_hash=row["trigger_event_hash"],
            source_count=int(row["source_count"]),
            detected_count=int(row["detected_count"]),
            protected_count=int(row["protected_count"]),
            residual_count=int(row["residual_count"]),
            policy_status=row["policy_status"],
            error_code=row["error_code"],
        )
