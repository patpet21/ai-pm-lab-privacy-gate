from __future__ import annotations

from enum import Enum
import os
from pathlib import Path
import platform
import sys

from ai_pm_lab_privacy_gate.infrastructure.updates.store_update_service import (
    is_store_packaged_install,
)


APP_NAME = "AI PM LAB Privacy Gate"
INNO_APP_ID = "{2F5D4173-04C2-46F2-BE8D-3FC0FBC2EE17}"


class InstallChannel(str, Enum):
    WINDOWS_STORE = "windows_store"
    WINDOWS_DIRECT = "windows_direct"
    WINDOWS_PORTABLE = "windows_portable"
    MAC_DIRECT = "mac_direct"
    MAC_APP_STORE = "mac_app_store"
    SOURCE = "source"
    OTHER = "other"


def mac_app_bundle_path(executable: str | Path | None = None) -> Path | None:
    """Return the enclosing .app bundle for a frozen macOS executable."""
    path = Path(executable or sys.executable).expanduser().resolve()
    for candidate in (path, *path.parents):
        if candidate.suffix.lower() == ".app":
            return candidate
    return None


def _windows_inno_install_location() -> Path | None:
    """Resolve the current-user/system Inno install without importing winreg elsewhere."""
    if platform.system().lower() != "windows":
        return None
    try:
        import winreg
    except Exception:
        return None

    key_name = (
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\"
        + INNO_APP_ID
        + "_is1"
    )
    access_modes = (winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0), winreg.KEY_READ)
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for access in access_modes:
            try:
                with winreg.OpenKey(hive, key_name, 0, access) as key:
                    value, _kind = winreg.QueryValueEx(key, "InstallLocation")
            except OSError:
                continue
            location = Path(str(value).strip()).expanduser()
            if str(location):
                return location
    return None


def windows_direct_executable() -> Path | None:
    """Return the installed Inno executable path when it matches this build."""
    location = _windows_inno_install_location()
    if location is None:
        return None
    candidate = location / f"{APP_NAME}.exe"
    return candidate if candidate.exists() else None


def current_install_channel() -> InstallChannel:
    system = platform.system().lower()
    frozen = bool(getattr(sys, "frozen", False))

    if system == "windows":
        if is_store_packaged_install():
            return InstallChannel.WINDOWS_STORE
        if not frozen:
            return InstallChannel.SOURCE
        installed = windows_direct_executable()
        if installed is not None:
            try:
                if Path(sys.executable).resolve() == installed.resolve():
                    return InstallChannel.WINDOWS_DIRECT
            except OSError:
                pass
        return InstallChannel.WINDOWS_PORTABLE

    if system == "darwin":
        bundle = mac_app_bundle_path()
        if bundle is not None and (bundle / "Contents" / "_MASReceipt" / "receipt").exists():
            return InstallChannel.MAC_APP_STORE
        if frozen and bundle is not None:
            return InstallChannel.MAC_DIRECT
        return InstallChannel.SOURCE

    if frozen:
        return InstallChannel.OTHER
    return InstallChannel.SOURCE


def channel_label(channel: InstallChannel | None = None) -> str:
    value = channel or current_install_channel()
    return {
        InstallChannel.WINDOWS_STORE: "Microsoft Store",
        InstallChannel.WINDOWS_DIRECT: "Windows Direct",
        InstallChannel.WINDOWS_PORTABLE: "Windows portable build",
        InstallChannel.MAC_DIRECT: "macOS Direct",
        InstallChannel.MAC_APP_STORE: "Mac App Store",
        InstallChannel.SOURCE: "development/source",
        InstallChannel.OTHER: "other",
    }[value]


def direct_update_supported(channel: InstallChannel | None = None) -> bool:
    return (channel or current_install_channel()) in {
        InstallChannel.WINDOWS_DIRECT,
        InstallChannel.MAC_DIRECT,
    }
