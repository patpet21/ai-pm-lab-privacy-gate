import time

import pytest

from ai_pm_lab_privacy_gate.infrastructure.connectors.multi_account_registry import MultiAccountRegistry
from ai_pm_lab_privacy_gate.infrastructure.connectors.multi_account_safety import _isolated_connect
from ai_pm_lab_privacy_gate.infrastructure.connectors.service import ConnectedAppsService
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore


def _service() -> tuple[ConnectedAppsService, MemorySecretStore]:
    store = MemorySecretStore()
    service = ConnectedAppsService(".", secret_store=store)
    return service, store


def test_new_account_oauth_cannot_inherit_previous_refresh_token():
    service, store = _service()
    registry = MultiAccountRegistry(store)

    store.set("connected.gmail.token", "access-a")
    store.set("connected.gmail.refresh_token", "refresh-a")
    first = registry.capture_legacy("gmail", identity="a@example.com", label="a@example.com")
    assert registry.active_account_id("gmail") == first

    def provider_connect(self):
        # Simulate a provider response for a second account that does not issue
        # a refresh token. The old account's token must not remain in the alias.
        self.secret_store.set("connected.gmail.token", "access-b")
        return "connected"

    safe_connect = _isolated_connect("gmail", provider_connect)
    result = safe_connect(service)

    assert result == "connected"
    assert store.get("connected.gmail.token") == "access-b"
    assert store.get("connected.gmail.refresh_token") in (None, "")


def test_failed_new_account_oauth_restores_previous_active_alias():
    service, store = _service()
    registry = MultiAccountRegistry(store)

    store.set("connected.gmail.token", "access-a")
    store.set("connected.gmail.refresh_token", "refresh-a")
    registry.capture_legacy("gmail", identity="a@example.com", label="a@example.com")

    def provider_connect(_self):
        raise RuntimeError("oauth cancelled")

    safe_connect = _isolated_connect("gmail", provider_connect)
    with pytest.raises(RuntimeError, match="oauth cancelled"):
        safe_connect(service)

    assert store.get("connected.gmail.token") == "access-a"
    assert store.get("connected.gmail.refresh_token") == "refresh-a"


def test_selected_google_drive_account_forces_refresh_when_expired(monkeypatch):
    service, store = _service()
    registry = MultiAccountRegistry(store)

    store.set("connected.google_drive.token", "expired-access")
    store.set("connected.google_drive.refresh_token", "drive-refresh")
    store.set("connected.google_drive.expires_at", str(int(time.time()) - 30))
    account_id = registry.capture_legacy(
        "google_drive",
        identity="permission-123",
        label="work@example.com",
    )
    registry.activate("google_drive", account_id)

    calls = []

    def fake_refresh():
        calls.append(True)
        store.set("connected.google_drive.token", "fresh-access")
        store.set("connected.google_drive.expires_at", str(int(time.time()) + 3600))
        return "fresh-access"

    monkeypatch.setattr(service, "force_google_refresh", fake_refresh)

    assert service._token("google_drive") == "fresh-access"
    assert calls == [True]
    assert store.get(f"connected.google_drive.account.{account_id}.token") == "fresh-access"
