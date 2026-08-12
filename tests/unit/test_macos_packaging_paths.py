from pathlib import Path

from ai_pm_lab_privacy_gate.infrastructure.mcp import config, tunnels
from ai_pm_lab_privacy_gate.infrastructure.storage import library_repository


def test_macos_frozen_helpers_resolve_inside_app_bundle(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "AI PM LAB Privacy Gate.app" / "Contents" / "MacOS" / "AI PM LAB Privacy Gate"
    resources = executable.parents[1] / "Resources"
    mcp_executable = resources / "AI PM LAB Privacy Gate MCP" / "AI PM LAB Privacy Gate MCP"
    cloudflared = resources / "cloudflared"
    mcp_executable.parent.mkdir(parents=True)
    mcp_executable.touch()
    cloudflared.touch()

    monkeypatch.setattr(config.sys, "platform", "darwin")
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config.sys, "executable", str(executable))
    monkeypatch.setattr(tunnels.sys, "platform", "darwin")
    monkeypatch.setattr(tunnels.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tunnels.sys, "executable", str(executable))

    assert config.mcp_launch_spec() == (str(mcp_executable), [])
    assert tunnels.CloudflaredRuntime.executable() == cloudflared


def test_macos_default_library_uses_application_support(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PRIVACY_GATE_DATA_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(library_repository.sys, "platform", "darwin")
    monkeypatch.setattr(library_repository.Path, "home", classmethod(lambda cls: tmp_path))

    assert library_repository.default_data_dir() == (
        tmp_path / "Library" / "Application Support" / "AI PM LAB Privacy Gate" / "Data"
    )
