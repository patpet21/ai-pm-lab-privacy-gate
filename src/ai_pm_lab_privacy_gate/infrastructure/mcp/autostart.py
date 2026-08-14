from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path


WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_VALUE_NAME = "AI PM LAB Privacy Gate MCP"
MACOS_LABEL = "xyz.propertydex.privacygate"


def set_mcp_autostart(enabled: bool) -> None:
    """Keep an explicitly enabled MCP connection available after user sign-in."""
    if not getattr(sys, "frozen", False):
        return
    if sys.platform == "win32":
        _set_windows_autostart(enabled)
    elif sys.platform == "darwin":
        _set_macos_autostart(enabled)


def _set_windows_autostart(enabled: bool) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
        if enabled:
            command = subprocess.list2cmdline([sys.executable, "--background"])
            winreg.SetValueEx(key, WINDOWS_VALUE_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, WINDOWS_VALUE_NAME)
            except FileNotFoundError:
                pass


def _set_macos_autostart(enabled: bool) -> None:
    launch_agents = Path.home() / "Library" / "LaunchAgents"
    plist_path = launch_agents / f"{MACOS_LABEL}.plist"
    if not enabled:
        plist_path.unlink(missing_ok=True)
        return
    launch_agents.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": MACOS_LABEL,
        "ProgramArguments": [sys.executable, "--background"],
        "RunAtLoad": True,
        "KeepAlive": False,
    }
    temporary = plist_path.with_suffix(".tmp")
    with temporary.open("wb") as handle:
        plistlib.dump(payload, handle)
    temporary.replace(plist_path)
