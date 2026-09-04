from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.connectors import (
    google_drive_file_access as access,
)


class _Store:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: str) -> None:
        self.values[key] = str(value)

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


class _Service:
    def __init__(self) -> None:
        self.secret_store = _Store()

    def active_account_id(self, _provider: str) -> str:
        return "full-drive-account-a"


def test_legacy_migration_cleans_poc_keys_and_disconnect_does_not_resurrect() -> None:
    service = _Service()
    old_prefix = "connected.google_drive.drive_file.full-drive-account-a"
    service.secret_store.set(f"{old_prefix}.token", "legacy-token")
    service.secret_store.set(f"{old_prefix}.refresh_token", "legacy-refresh")
    service.secret_store.set(f"{old_prefix}.expires_at", "9999999999")
    service.secret_store.set(f"{old_prefix}.file_ids", '["legacy-file"]')

    records = access.list_selected_file_accounts(service)

    assert len(records) == 1
    migrated_id = records[0].account_id
    assert migrated_id == access._legacy_account_id("full-drive-account-a")
    assert access.stored_file_ids(service) == ("legacy-file",)
    assert service.secret_store.get(f"{old_prefix}.token") is None
    assert service.secret_store.get(f"{old_prefix}.refresh_token") is None
    assert service.secret_store.get(f"{old_prefix}.expires_at") is None
    assert service.secret_store.get(f"{old_prefix}.file_ids") is None

    access.disconnect_selected_file_account(service, migrated_id)

    assert access.list_selected_file_accounts(service) == ()


def test_existing_migrated_registry_cleans_stale_poc_copy_without_touching_new_account() -> None:
    service = _Service()
    legacy_id = "full-drive-account-a"
    migrated_id = access._legacy_account_id(legacy_id)
    old_prefix = f"connected.google_drive.drive_file.{legacy_id}"
    new_prefix = f"connected.google_drive.drive_file.account.{migrated_id}"

    service.secret_store.set(
        "connected.google_drive.drive_file.accounts",
        f'["{migrated_id}"]',
    )
    service.secret_store.set("connected.google_drive.drive_file.active", migrated_id)
    service.secret_store.set(f"{new_prefix}.token", "new-token")
    service.secret_store.set(f"{new_prefix}.expires_at", "9999999999")
    service.secret_store.set(f"{new_prefix}.file_ids", '["new-file"]')
    service.secret_store.set(f"{new_prefix}.label", "Selected-file account")

    service.secret_store.set(f"{old_prefix}.token", "stale-token")
    service.secret_store.set(f"{old_prefix}.file_ids", '["stale-file"]')

    records = access.list_selected_file_accounts(service)

    assert [record.account_id for record in records] == [migrated_id]
    assert service.secret_store.get(f"{old_prefix}.token") is None
    assert service.secret_store.get(f"{old_prefix}.file_ids") is None
    assert service.secret_store.get(f"{new_prefix}.token") == "new-token"
    assert access.stored_file_ids(service) == ("new-file",)
