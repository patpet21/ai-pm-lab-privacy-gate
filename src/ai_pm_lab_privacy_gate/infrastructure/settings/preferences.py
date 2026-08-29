from __future__ import annotations

import json
import socket
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(slots=True)
class AppPreferences:
    close_behavior: str = "ask"  # ask | background | quit
    port_mode: str = "automatic"  # automatic | manual (MCP)
    manual_port: int = 8766
    local_api_enabled: bool = False
    local_api_port: int = 8765


class PreferencesStore:
    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / "preferences.json"

    def load(self) -> AppPreferences:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return AppPreferences()
        prefs = AppPreferences()
        if payload.get("close_behavior") in {"ask", "background", "quit"}:
            prefs.close_behavior = payload["close_behavior"]
        if payload.get("port_mode") in {"automatic", "manual"}:
            prefs.port_mode = payload["port_mode"]
        try:
            port = int(payload.get("manual_port", 8766))
            if 1024 <= port <= 65535:
                prefs.manual_port = port
        except (TypeError, ValueError):
            pass
        if isinstance(payload.get("local_api_enabled"), bool):
            prefs.local_api_enabled = payload["local_api_enabled"]
        try:
            local_api_port = int(payload.get("local_api_port", 8765))
            if 1024 <= local_api_port <= 65535:
                prefs.local_api_port = local_api_port
        except (TypeError, ValueError):
            pass
        return prefs

    def save(self, prefs: AppPreferences) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(prefs), indent=2), encoding="utf-8")


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    if not 1024 <= int(port) <= 65535:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, int(port)))
        except OSError:
            return False
    return True
