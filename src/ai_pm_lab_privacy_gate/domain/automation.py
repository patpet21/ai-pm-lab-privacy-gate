from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Mapping


class AutomationStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class AutomationTriggerType(StrEnum):
    GMAIL = "gmail"
    MANUAL = "manual"


class AutomationDestination(StrEnum):
    LIBRARY = "library"


class AutomationRunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"
    FAILED = "failed"


_FORBIDDEN_PERSISTED_CONFIG_KEYS = {
    "body",
    "content",
    "email_body",
    "attachment_text",
    "original_text",
    "protected_text",
    "payload",
    "document_text",
}


@dataclass(frozen=True, slots=True)
class AutomationDefinition:
    """Persistable workflow configuration; never stores business payloads."""

    automation_id: str
    name: str
    trigger_type: AutomationTriggerType
    trigger_config: Mapping[str, object] = field(default_factory=dict)
    profile_key: str = "default"
    replacement_mode: str = "reversible"
    destination: AutomationDestination = AutomationDestination.LIBRARY
    workspace_id: str = ""
    status: AutomationStatus = AutomationStatus.DRAFT
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.automation_id.strip():
            raise ValueError("AutomationDefinition.automation_id is required")
        if not self.name.strip():
            raise ValueError("AutomationDefinition.name is required")
        if not self.profile_key.strip():
            raise ValueError("AutomationDefinition.profile_key is required")
        if self.replacement_mode not in {"reversible", "redacted"}:
            raise ValueError("AutomationDefinition replacement_mode is invalid")

        unsafe = {
            str(key).strip().lower()
            for key in self.trigger_config
            if str(key).strip().lower() in _FORBIDDEN_PERSISTED_CONFIG_KEYS
        }
        if unsafe:
            keys = ", ".join(sorted(unsafe))
            raise ValueError(
                f"Automation trigger_config cannot persist business payload fields: {keys}"
            )

        # Fail early if a config cannot be serialized into the local state store.
        json.dumps(dict(self.trigger_config), sort_keys=True)

    @property
    def enabled(self) -> bool:
        return self.status is AutomationStatus.ACTIVE

    def with_status(self, status: AutomationStatus, *, updated_at: str = "") -> "AutomationDefinition":
        return replace(self, status=status, updated_at=updated_at or self.updated_at)

    def to_dict(self) -> dict[str, object]:
        return {
            "automation_id": self.automation_id,
            "name": self.name,
            "trigger_type": self.trigger_type.value,
            "trigger_config": dict(self.trigger_config),
            "profile_key": self.profile_key,
            "replacement_mode": self.replacement_mode,
            "destination": self.destination.value,
            "workspace_id": self.workspace_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "AutomationDefinition":
        return cls(
            automation_id=str(payload.get("automation_id") or "").strip(),
            name=str(payload.get("name") or "").strip(),
            trigger_type=AutomationTriggerType(str(payload.get("trigger_type") or "manual")),
            trigger_config=dict(payload.get("trigger_config") or {}),
            profile_key=str(payload.get("profile_key") or "default").strip(),
            replacement_mode=str(payload.get("replacement_mode") or "reversible").strip(),
            destination=AutomationDestination(str(payload.get("destination") or "library")),
            workspace_id=str(payload.get("workspace_id") or "").strip(),
            status=AutomationStatus(str(payload.get("status") or "draft")),
            created_at=str(payload.get("created_at") or "").strip(),
            updated_at=str(payload.get("updated_at") or "").strip(),
        )


@dataclass(frozen=True, slots=True)
class AutomationRunRecord:
    """Metadata-only execution record safe for local run history."""

    run_id: str
    automation_id: str
    status: AutomationRunStatus
    started_at: str
    finished_at: str = ""
    trigger_event_hash: str = ""
    source_count: int = 0
    detected_count: int = 0
    protected_count: int = 0
    residual_count: int = 0
    policy_status: str = "not_checked"
    error_code: str = ""


@dataclass(frozen=True, slots=True)
class AutomationSummary:
    active_automations: int = 0
    runs_today: int = 0
    waiting_approval: int = 0
    blocked_by_policy: int = 0
