from __future__ import annotations

import threading

from ai_pm_lab_privacy_gate.infrastructure.local_api.manager import (
    LOCAL_API_AUTH_TOKEN_SECRET,
    LocalApiManager,
)
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore
from ai_pm_lab_privacy_gate.infrastructure.settings.preferences import AppPreferences, PreferencesStore


class FakeServer:
    def __init__(self, port: int) -> None:
        self.server_port = port
        self.closed = False
        self._stop = threading.Event()

    def serve_forever(self, poll_interval: float = 0.25) -> None:
        self._stop.wait(timeout=5)

    def shutdown(self) -> None:
        self._stop.set()

    def server_close(self) -> None:
        self.closed = True


class RecordingServerFactory:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.servers: list[FakeServer] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        server = FakeServer(int(kwargs["port"]))
        self.servers.append(server)
        return server


def test_preferences_keep_local_bridge_opt_in(tmp_path) -> None:
    store = PreferencesStore(tmp_path)
    defaults = store.load()
    assert defaults.local_api_enabled is False
    assert defaults.local_api_port == 8765

    expected = AppPreferences(local_api_enabled=True, local_api_port=9123)
    store.save(expected)
    loaded = store.load()
    assert loaded.local_api_enabled is True
    assert loaded.local_api_port == 9123
    assert loaded.manual_port == 8766


def test_manager_starts_loopback_only_and_persists_secret_token(tmp_path) -> None:
    secrets = MemorySecretStore()
    factory = RecordingServerFactory()
    service = object()
    manager = LocalApiManager(
        service,  # type: ignore[arg-type]
        tmp_path,
        secret_store=secrets,
        server_factory=factory,
    )
    status = manager.apply_preferences(
        AppPreferences(local_api_enabled=True, local_api_port=9123)
    )
    assert status.state == "online"
    assert status.port == 9123
    assert factory.calls[0]["host"] == "127.0.0.1"
    assert factory.calls[0]["allowed_origins"] == ()
    first_token = factory.calls[0]["auth_token"]
    assert isinstance(first_token, str) and len(first_token) >= 24
    assert secrets.get(LOCAL_API_AUTH_TOKEN_SECRET) == first_token

    manager.stop()
    manager.start(9124)
    assert factory.calls[1]["auth_token"] == first_token
    manager.stop()
    assert factory.servers[-1].closed is True


def test_disabled_preference_stops_bridge(tmp_path) -> None:
    factory = RecordingServerFactory()
    manager = LocalApiManager(
        object(),  # type: ignore[arg-type]
        tmp_path,
        secret_store=MemorySecretStore(),
        server_factory=factory,
    )
    manager.start(9123)
    assert manager.status.state == "online"
    status = manager.apply_preferences(AppPreferences(local_api_enabled=False))
    assert status.state == "disabled"
    assert factory.servers[0].closed is True


def test_start_failure_is_reported_without_crashing_app(tmp_path) -> None:
    def failing_factory(**_kwargs):
        raise OSError("port is already in use")

    manager = LocalApiManager(
        object(),  # type: ignore[arg-type]
        tmp_path,
        secret_store=MemorySecretStore(),
        server_factory=failing_factory,
    )
    status = manager.start(9123)
    assert status.state == "error"
    assert status.port == 9123
    assert "port is already in use" in status.error
