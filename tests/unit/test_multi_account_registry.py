from ai_pm_lab_privacy_gate.infrastructure.connectors.multi_account_registry import MultiAccountRegistry
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore


def test_migrates_existing_single_account_without_losing_credentials():
    store = MemorySecretStore()
    store.set("connected.google_drive.token", "old-access")
    store.set("connected.google_drive.refresh_token", "old-refresh")
    store.set("connected.google_drive.client_id", "client")

    registry = MultiAccountRegistry(store)
    registry.initialize_provider("google_drive")

    accounts = registry.list_accounts("google_drive")
    assert len(accounts) == 1
    assert accounts[0].is_default is True
    assert store.get("connected.google_drive.token") == "old-access"
    assert store.get("connected.google_drive.refresh_token") == "old-refresh"


def test_two_accounts_switch_independent_credentials_and_keep_default():
    store = MemorySecretStore()
    registry = MultiAccountRegistry(store)

    store.set("connected.gmail.token", "token-one")
    first = registry.capture_legacy("gmail", identity="one@example.com", label="one@example.com")

    store.set("connected.gmail.token", "token-two")
    second = registry.capture_legacy("gmail", identity="two@example.com", label="two@example.com")

    accounts = registry.list_accounts("gmail")
    assert len(accounts) == 2
    assert registry.default_account_id("gmail") == first
    assert registry.active_account_id("gmail") == second

    registry.activate("gmail", first)
    assert store.get("connected.gmail.token") == "token-one"
    assert registry.default_account_id("gmail") == first

    registry.activate("gmail", second, make_default=True)
    assert store.get("connected.gmail.token") == "token-two"
    assert registry.default_account_id("gmail") == second


def test_disconnect_only_selected_account_and_falls_back_safely():
    store = MemorySecretStore()
    registry = MultiAccountRegistry(store)

    store.set("connected.asana.token", "one")
    first = registry.capture_legacy("asana", identity="user-1", label="User one")
    store.set("connected.asana.token", "two")
    second = registry.capture_legacy("asana", identity="user-2", label="User two")
    registry.activate("asana", second, make_default=True)

    registry.disconnect_account("asana", second)

    accounts = registry.list_accounts("asana")
    assert [account.account_id for account in accounts] == [first]
    assert accounts[0].is_default is True
    assert store.get("connected.asana.token") == "one"


def test_rekey_collapses_legacy_identity_to_stable_provider_identity():
    store = MemorySecretStore()
    store.set("connected.notion.token", "notion-token")
    store.set("connected.notion.workspace_name", "AI PM LAB")
    registry = MultiAccountRegistry(store)
    registry.initialize_provider("notion")

    old_id = registry.list_accounts("notion")[0].account_id
    new_id = registry.account_id_for_identity("notion", "workspace-123:bot-456")
    resolved = registry.rekey_account("notion", old_id, new_id)
    registry.update_account_metadata(
        "notion",
        resolved,
        label="AI PM LAB",
        subtitle="Workspace",
        identity="workspace-123:bot-456",
    )

    accounts = registry.list_accounts("notion")
    assert len(accounts) == 1
    assert accounts[0].account_id == new_id
    assert accounts[0].label == "AI PM LAB"
    assert store.get(f"connected.notion.account.{new_id}.token") == "notion-token"
