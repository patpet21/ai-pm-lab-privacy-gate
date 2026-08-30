from __future__ import annotations

from pathlib import Path

from ai_pm_lab_privacy_gate.infrastructure.updates.install_channel import (
    InstallChannel,
    direct_update_supported,
    mac_app_bundle_path,
)


def test_mac_app_bundle_path_finds_enclosing_bundle(tmp_path: Path):
    executable = tmp_path / "AI PM LAB Privacy Gate.app" / "Contents" / "MacOS" / "AI PM LAB Privacy Gate"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    assert mac_app_bundle_path(executable) == tmp_path / "AI PM LAB Privacy Gate.app"


def test_direct_update_supported_only_for_installed_direct_channels():
    assert direct_update_supported(InstallChannel.WINDOWS_DIRECT) is True
    assert direct_update_supported(InstallChannel.MAC_DIRECT) is True
    assert direct_update_supported(InstallChannel.WINDOWS_STORE) is False
    assert direct_update_supported(InstallChannel.WINDOWS_PORTABLE) is False
    assert direct_update_supported(InstallChannel.MAC_APP_STORE) is False
    assert direct_update_supported(InstallChannel.SOURCE) is False
