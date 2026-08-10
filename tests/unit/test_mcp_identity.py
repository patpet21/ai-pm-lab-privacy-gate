import json

from ai_pm_lab_privacy_gate.infrastructure.mcp.identity import ConnectionIdentityStore


def test_connection_identity_is_opaque_and_persists_across_updates(tmp_path) -> None:
    store = ConnectionIdentityStore(tmp_path)
    first = store.load_or_create()
    second = ConnectionIdentityStore(tmp_path).load_or_create()

    assert first == second
    assert first.display_name == "This PC"
    assert first.access_secret in first.mcp_path
    assert "pietr" not in json.dumps(first.__dict__).lower()
    assert "users" not in first.mcp_path.lower()


def test_connection_secret_can_be_revoked_without_changing_customer(tmp_path) -> None:
    store = ConnectionIdentityStore(tmp_path)
    original = store.load_or_create()
    rotated = store.rotate_access_secret()

    assert rotated.customer_id == original.customer_id
    assert rotated.device_id == original.device_id
    assert rotated.access_secret != original.access_secret
    assert ConnectionIdentityStore(tmp_path).load_or_create() == rotated


def test_remote_enabled_setting_persists(tmp_path) -> None:
    store = ConnectionIdentityStore(tmp_path)
    assert store.is_remote_enabled() is False
    store.set_remote_enabled(True)
    assert ConnectionIdentityStore(tmp_path).is_remote_enabled() is True
