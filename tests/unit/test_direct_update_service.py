from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from ai_pm_lab_privacy_gate.infrastructure.updates.direct_update_service import (
    DirectUpdateError,
    DirectUpdateService,
)
from ai_pm_lab_privacy_gate.infrastructure.updates.install_channel import InstallChannel


OFFICIAL_BASE = "https://github.com/patpet21/ai-pm-lab-privacy-gate-downloads/releases/download/v0.5.0"


@dataclass
class Release:
    version: str = "0.5.0"
    download_url: str = f"{OFFICIAL_BASE}/AI_PM_LAB_Privacy_Gate_Setup_0.5.0.exe"
    sha256: str = "a" * 64


def test_direct_updater_requires_release_version():
    assert DirectUpdateService._validated_version("0.5.0") == "0.5.0"
    for value in ("", "v0.5.0", "0.5", "../0.5.0", "0.5.0-beta"):
        with pytest.raises(DirectUpdateError):
            DirectUpdateService._validated_version(value)


def test_direct_updater_requires_https():
    release = Release(download_url=Release.download_url.replace("https://", "http://"))
    with pytest.raises(DirectUpdateError):
        DirectUpdateService._validated_download_name(release, InstallChannel.WINDOWS_DIRECT)


def test_direct_updater_restricts_artifacts_to_official_release_repository():
    release = Release(download_url="https://example.test/PrivacyGate.exe")
    with pytest.raises(DirectUpdateError):
        DirectUpdateService._validated_download_name(release, InstallChannel.WINDOWS_DIRECT)


def test_direct_updater_accepts_matching_official_package_type():
    release = Release()
    assert DirectUpdateService._validated_download_name(
        release, InstallChannel.WINDOWS_DIRECT
    ) == "AI_PM_LAB_Privacy_Gate_Setup_0.5.0.exe"


def test_direct_updater_requires_expected_package_type():
    release = Release(
        download_url=f"{OFFICIAL_BASE}/AI_PM_LAB_Privacy_Gate_0.5.0_Apple-Silicon.dmg"
    )
    with pytest.raises(DirectUpdateError):
        DirectUpdateService._validated_download_name(release, InstallChannel.WINDOWS_DIRECT)


def test_direct_updater_requires_full_sha256():
    with pytest.raises(DirectUpdateError):
        DirectUpdateService._validate_expected_sha256("abc")
    assert DirectUpdateService._validate_expected_sha256("A" * 64) == "a" * 64


def test_sha256_matches_file_content(tmp_path: Path):
    artifact = tmp_path / "artifact.exe"
    artifact.write_bytes(b"privacygate")
    assert DirectUpdateService._sha256(artifact) == (
        "ea68c5acbe1cd1873ea90c6437dbfb7c9952ba05ae27c123fb992fb8f30429e4"
    )
