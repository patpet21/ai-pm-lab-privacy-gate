from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from ai_pm_lab_privacy_gate.infrastructure.updates.direct_update_service import (
    DirectUpdateError,
    DirectUpdateService,
)
from ai_pm_lab_privacy_gate.infrastructure.updates.install_channel import InstallChannel


@dataclass
class Release:
    version: str = "0.5.0"
    download_url: str = "https://example.test/PrivacyGate.exe"
    sha256: str = "a" * 64


def test_direct_updater_requires_https():
    release = Release(download_url="http://example.test/PrivacyGate.exe")
    with pytest.raises(DirectUpdateError):
        DirectUpdateService._validated_download_name(release, InstallChannel.WINDOWS_DIRECT)


def test_direct_updater_requires_expected_package_type():
    release = Release(download_url="https://example.test/PrivacyGate.dmg")
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
        "fdb2947bb2ee527766925c7ad8a913ff62565bdcf40c65b4a2c9a730aac5bfec"
    )
