from pathlib import Path

import pytest

from ai_pm_lab_privacy_gate.domain.automation import (
    AutomationDefinition,
    AutomationDestination,
    AutomationRunStatus,
    AutomationStatus,
    AutomationTriggerType,
)
from ai_pm_lab_privacy_gate.infrastructure.automation.automation_store import AutomationStore


def definition() -> AutomationDefinition:
    return AutomationDefinition(
        automation_id="gmail-to-library",
        name="Gmail → Protect → Library",
        trigger_type=AutomationTriggerType.GMAIL,
        trigger_config={
            "account_id": "acct-1",
            "query": "has:attachment",
            "attachment_suffixes": [".pdf", ".docx", ".xlsx", ".pptx", ".txt"],
            "poll_seconds": 120,
        },
        profile_key="real_estate_sensitive",
        destination=AutomationDestination.LIBRARY,
        workspace_id="workspace-1",
        status=AutomationStatus.ACTIVE,
    )


def test_store_persists_definition_and_real_summary(tmp_path: Path):
    store = AutomationStore(tmp_path)
    saved = store.save_definition(definition())

    assert saved.created_at
    assert saved.updated_at
    assert store.get_definition(saved.automation_id).trigger_config["query"] == "has:attachment"
    assert store.summary().active_automations == 1


def test_run_history_is_metadata_only_and_hashes_trigger_event(tmp_path: Path):
    store = AutomationStore(tmp_path)
    store.save_definition(definition())
    raw_event_key = "gmail-message-id-very-sensitive-linkage"

    started = store.start_run("gmail-to-library", trigger_event_key=raw_event_key)
    assert started.status is AutomationRunStatus.RUNNING
    assert started.trigger_event_hash
    assert started.trigger_event_hash != raw_event_key

    finished = store.finish_run(
        started.run_id,
        status=AutomationRunStatus.SUCCESS,
        source_count=2,
        detected_count=14,
        protected_count=14,
        residual_count=0,
        policy_status="allowed",
    )

    assert finished.status is AutomationRunStatus.SUCCESS
    assert finished.detected_count == 14
    assert finished.protected_count == 14
    assert finished.residual_count == 0
    assert raw_event_key.encode("utf-8") not in store.db_path.read_bytes()


def test_summary_counts_review_and_blocked_runs(tmp_path: Path):
    store = AutomationStore(tmp_path)
    store.save_definition(definition())

    review = store.start_run("gmail-to-library", trigger_event_key="m1")
    store.finish_run(
        review.run_id,
        status=AutomationRunStatus.NEEDS_REVIEW,
        residual_count=1,
        policy_status="review",
    )
    blocked = store.start_run("gmail-to-library", trigger_event_key="m2")
    store.finish_run(
        blocked.run_id,
        status=AutomationRunStatus.BLOCKED,
        policy_status="blocked",
        error_code="policy_blocked",
    )

    summary = store.summary()
    assert summary.runs_today == 2
    assert summary.waiting_approval == 1
    assert summary.blocked_by_policy == 1


def test_definition_rejects_business_payload_fields():
    with pytest.raises(ValueError, match="cannot persist business payload"):
        AutomationDefinition(
            automation_id="unsafe",
            name="Unsafe",
            trigger_type=AutomationTriggerType.GMAIL,
            trigger_config={"email_body": "do not store me"},
        )


def test_finish_run_rejects_negative_counters(tmp_path: Path):
    store = AutomationStore(tmp_path)
    store.save_definition(definition())
    run = store.start_run("gmail-to-library")

    with pytest.raises(ValueError, match="cannot be negative"):
        store.finish_run(
            run.run_id,
            status=AutomationRunStatus.FAILED,
            detected_count=-1,
        )
