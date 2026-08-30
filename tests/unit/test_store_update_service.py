from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.updates.store_update_service import (
    StoreUpdateService,
    is_store_packaged_install,
)


def _simulate_windows_store(monkeypatch) -> None:
    monkeypatch.setattr(
        "ai_pm_lab_privacy_gate.infrastructure.updates.store_update_service.platform.system",
        lambda: "Windows",
    )
    monkeypatch.setenv("PRIVACY_GATE_SIMULATE_STORE", "1")


def test_simulated_store_install(monkeypatch):
    _simulate_windows_store(monkeypatch)
    assert is_store_packaged_install() is True


def test_simulated_silent_install_success(monkeypatch):
    _simulate_windows_store(monkeypatch)
    monkeypatch.setenv("PRIVACY_GATE_SIMULATE_STORE_RESULT", "installed")
    result = StoreUpdateService().try_silent_update()
    assert result.status == "installed"


def test_simulated_action_required(monkeypatch):
    _simulate_windows_store(monkeypatch)
    monkeypatch.setenv("PRIVACY_GATE_SIMULATE_STORE_RESULT", "action_required")
    result = StoreUpdateService().try_silent_update()
    assert result.status == "action_required"


def test_simulated_store_preparing(monkeypatch):
    _simulate_windows_store(monkeypatch)
    monkeypatch.setenv("PRIVACY_GATE_SIMULATE_STORE_RESULT", "preparing")
    result = StoreUpdateService().try_silent_update()
    assert result.status == "preparing"
