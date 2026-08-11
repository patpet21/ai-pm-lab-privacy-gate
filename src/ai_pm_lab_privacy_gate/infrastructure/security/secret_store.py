from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from ai_pm_lab_privacy_gate.infrastructure.security.local_protector import LocalProtector


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> None: ...

    def delete(self, name: str) -> None: ...


def _safe_name(name: str) -> str:
    if not re.fullmatch(r"[a-z0-9_.-]{1,80}", name):
        raise ValueError("Invalid secret name")
    return name


class WindowsDpapiSecretStore:
    """Store per-user secrets as DPAPI-protected blobs outside the install directory."""

    def __init__(self, data_dir: str | Path) -> None:
        self.secret_dir = Path(data_dir) / "Secrets"
        self.secret_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.secret_dir / f"{_safe_name(name)}.bin"

    def get(self, name: str) -> str | None:
        path = self._path(name)
        if not path.exists():
            return None
        return LocalProtector.unprotect(path.read_bytes())

    def set(self, name: str, value: str) -> None:
        path = self._path(name)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(LocalProtector.protect(value))
        temporary.replace(path)

    def delete(self, name: str) -> None:
        self._path(name).unlink(missing_ok=True)


class MacOSKeychainSecretStore:
    """Use the current macOS user's login Keychain without putting secrets in JSON."""

    SERVICE = "AI PM LAB Privacy Gate"

    def get(self, name: str) -> str | None:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", self.SERVICE, "-a", _safe_name(name), "-w"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.rstrip("\r\n")

    def set(self, name: str, value: str) -> None:
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                self.SERVICE,
                "-a",
                _safe_name(name),
                "-w",
                value,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def delete(self, name: str) -> None:
        subprocess.run(
            ["security", "delete-generic-password", "-s", self.SERVICE, "-a", _safe_name(name)],
            check=False,
            capture_output=True,
            text=True,
        )


class MemorySecretStore:
    """Test-only in-memory secret store."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(_safe_name(name))

    def set(self, name: str, value: str) -> None:
        self.values[_safe_name(name)] = value

    def delete(self, name: str) -> None:
        self.values.pop(_safe_name(name), None)


def platform_secret_store(data_dir: str | Path) -> SecretStore:
    if sys.platform == "darwin":
        return MacOSKeychainSecretStore()
    return WindowsDpapiSecretStore(data_dir)

