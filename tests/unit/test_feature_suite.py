from __future__ import annotations

from pathlib import Path

import pytest

from ai_pm_lab_privacy_gate.application import portable_backup_runtime  # noqa: F401
from ai_pm_lab_privacy_gate.application.feature_suite import (
    AdvancedFileService,
    FullEncryptedBackupService,
    LocalActivityStore,
    WorkspaceRule,
    WorkspaceRuleStore,
)
from ai_pm_lab_privacy_gate.domain.plans import (
    Capability,
    PlanCode,
    minimum_plan_for,
    require_capability,
    supports,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository


def test_advanced_capabilities_are_gated_by_plan() -> None:
    assert supports(PlanCode.BASIC, Capability.LOCAL_PRIVACY_CORE)
    assert not supports(PlanCode.BASIC, Capability.LOCAL_OCR)
    assert supports(PlanCode.PRO, Capability.LOCAL_OCR)
    assert supports(PlanCode.PRO, Capability.BATCH_PROTECTION)
    assert not supports(PlanCode.PRO, Capability.WORKSPACE_RULES)
    assert supports(PlanCode.BUSINESS, Capability.WORKSPACE_RULES)
    assert supports(PlanCode.ENTERPRISE, Capability.ENTERPRISE_AUDIT)
    assert minimum_plan_for(Capability.LOCAL_OCR) is PlanCode.PRO
    assert minimum_plan_for(Capability.WORKSPACE_RULES) is PlanCode.BUSINESS


def test_backend_capability_guard_cannot_be_bypassed() -> None:
    with pytest.raises(PermissionError):
        require_capability(PlanCode.BASIC, Capability.BATCH_PROTECTION)
    require_capability(PlanCode.PRO, Capability.BATCH_PROTECTION)


def test_advanced_file_service_is_workspace_scoped_and_safe_delete_is_reversible(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    source = root / "document.txt"
    source.write_text("protected placeholder text", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    service = AdvancedFileService()
    renamed = service.rename(PlanCode.PRO, root, source, "renamed.txt")
    assert renamed.name == "renamed.txt"
    assert renamed.exists()

    trash_target = service.safe_delete(PlanCode.PRO, root, renamed)
    assert trash_target.exists()
    assert trash_target.parent.name == ".PrivacyGate Trash"
    assert not renamed.exists()

    with pytest.raises(PermissionError):
        service.safe_delete(PlanCode.PRO, root, outside)
    with pytest.raises(PermissionError):
        service.create_folder(PlanCode.BASIC, root, "Locked")


def test_activity_store_keeps_metadata_not_source_name(tmp_path: Path) -> None:
    store = LocalActivityStore(tmp_path)
    source = tmp_path / "Very Sensitive Client Name.pdf"
    store.record(
        "document_scanned",
        workspace_key="personal",
        source=source,
        source_kind="pdf",
        findings_count=14,
        detail="Scan completed",
    )
    row = store.recent(1)[0]
    assert row["findings_count"] == 14
    assert row["source_kind"] == "pdf"
    assert row["source_hash"]
    assert "Very Sensitive Client Name" not in str(row)


def test_workspace_rules_require_business_and_enforce_destinations(tmp_path: Path) -> None:
    store = WorkspaceRuleStore(tmp_path)
    rule = WorkspaceRule(
        provider="google_drive",
        account_id="work-account",
        workspace_key="company-a",
        allowed_destinations=("ChatGPT", "Claude"),
        default_folder="C:/PrivacyGate/CompanyA",
    )
    with pytest.raises(PermissionError):
        store.save(PlanCode.PRO, [rule])
    store.save(PlanCode.BUSINESS, [rule])
    assert store.allows("company-a", "ChatGPT")
    assert not store.allows("company-a", "Gemini")
    assert store.allows("personal", "Gemini")


def test_portable_backup_uses_passphrase_container(tmp_path: Path) -> None:
    library = LibraryRepository(tmp_path / "data")
    service = FullEncryptedBackupService(library)
    target = service.create(PlanCode.PRO, tmp_path / "backup.pgbak", "correct horse battery")
    assert target.read_bytes().startswith(b"PGBK2")
    restored = service.restore(PlanCode.PRO, target, "correct horse battery")
    assert restored == library.db_path
    with pytest.raises(ValueError):
        service.restore(PlanCode.PRO, target, "wrong password")
