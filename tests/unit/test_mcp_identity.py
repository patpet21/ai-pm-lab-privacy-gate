import json

from ai_pm_lab_privacy_gate.infrastructure.mcp.identity import ConnectionIdentityStore
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore


def test_connection_identity_is_opaque_and_persists_across_updates(tmp_path) -> None:
    secrets = MemorySecretStore()
    store = ConnectionIdentityStore(tmp_path, secrets)
    first = store.load_or_create()
    second = ConnectionIdentityStore(tmp_path, secrets).load_or_create()

    assert first == second
    assert first.display_name == "This PC"
    access_secret = store.dev_access_secret()
    assert access_secret in store.dev_mcp_path()
    assert access_secret not in store.path.read_text(encoding="utf-8")
    assert "pietr" not in json.dumps(first.__dict__).lower()
    assert "users" not in store.dev_mcp_path().lower()


def test_connection_secret_can_be_revoked_without_changing_customer(tmp_path) -> None:
    secrets = MemorySecretStore()
    store = ConnectionIdentityStore(tmp_path, secrets)
    original = store.load_or_create()
    original_secret = store.dev_access_secret()
    rotated = store.rotate_access_secret()

    assert rotated.customer_id == original.customer_id
    assert rotated.device_id == original.device_id
    assert store.dev_access_secret() != original_secret
    assert ConnectionIdentityStore(tmp_path, secrets).load_or_create() == rotated


def test_remote_enabled_setting_persists(tmp_path) -> None:
    secrets = MemorySecretStore()
    store = ConnectionIdentityStore(tmp_path, secrets)
    assert store.is_remote_enabled() is False
    store.set_remote_enabled(True)
    assert ConnectionIdentityStore(tmp_path, secrets).is_remote_enabled() is True


def test_legacy_plaintext_secret_is_migrated_out_of_identity_json(tmp_path) -> None:
    legacy = {
        "customer_id": "a" * 32,
        "device_id": "b" * 32,
        "access_secret": "legacy-private-secret",
        "display_name": "This PC",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    (tmp_path / "connection_identity.json").write_text(json.dumps(legacy), encoding="utf-8")
    secrets = MemorySecretStore()
    store = ConnectionIdentityStore(tmp_path, secrets)

    identity = store.load_or_create()

    assert identity.installation_id == "a" * 32
    assert store.dev_access_secret() == "legacy-private-secret"
    assert "legacy-private-secret" not in store.path.read_text(encoding="utf-8")
