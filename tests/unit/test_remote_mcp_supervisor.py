from __future__ import annotations

import subprocess
import threading

from ai_pm_lab_privacy_gate.infrastructure.mcp.modes import ConnectionMode
from ai_pm_lab_privacy_gate.infrastructure.mcp.remote import RemoteMcpManager, RemoteMcpStatus
from ai_pm_lab_privacy_gate.infrastructure.mcp.tunnels import CloudflaredRuntime


def _manager_without_storage() -> RemoteMcpManager:
    manager = RemoteMcpManager.__new__(RemoteMcpManager)
    manager._lock = threading.Lock()
    manager._status = RemoteMcpStatus()
    manager._server_process = None
    manager._tunnel_process = None
    manager._monitor_thread = None
    manager._stop_event = threading.Event()
    return manager


class ImmediateRetryEvent(threading.Event):
    def wait(self, timeout: float | None = None) -> bool:
        if timeout and timeout >= 1:
            return self.is_set()
        return super().wait(timeout)


def test_production_supervisor_retries_without_reprovisioning(monkeypatch) -> None:
    manager = _manager_without_storage()
    stop_event = ImmediateRetryEvent()
    attempts = 0

    def run_once(_mode, event) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("network interrupted")
        event.set()

    monkeypatch.setattr(manager, "_run_once", run_once)
    manager._supervise(ConnectionMode.PROD_NAMED, stop_event)

    assert attempts == 2
    assert "Reconnecting automatically" in manager.status.error


def test_development_quick_tunnel_does_not_silently_change_url(monkeypatch) -> None:
    manager = _manager_without_storage()
    attempts = 0

    def run_once(_mode, _event) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("temporary tunnel stopped")

    monkeypatch.setattr(manager, "_run_once", run_once)
    manager._supervise(ConnectionMode.DEV_QUICK, threading.Event())

    assert attempts == 1
    assert manager.status.state == "error"


def test_named_tunnel_can_discard_output_without_an_unread_pipe(monkeypatch) -> None:
    captured = {}

    def fake_popen(command, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    CloudflaredRuntime.popen(["cloudflared"], capture_output=False)

    assert captured["stdout"] is subprocess.DEVNULL
    assert captured["stderr"] is subprocess.DEVNULL
