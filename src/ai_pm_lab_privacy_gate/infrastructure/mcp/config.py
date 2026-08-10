from __future__ import annotations

import json
import sys
from pathlib import Path


MCP_EXECUTABLE_NAME = "AI PM LAB Privacy Gate MCP.exe"


def mcp_launch_spec() -> tuple[str, list[str]]:
    """Return the command and arguments for the installed or development server."""
    if getattr(sys, "frozen", False):
        server_dir = Path(sys.executable).with_name("AI PM LAB Privacy Gate MCP")
        return str(server_dir / MCP_EXECUTABLE_NAME), []
    return sys.executable, ["-m", "ai_pm_lab_privacy_gate.infrastructure.mcp.server"]


def client_config() -> dict[str, object]:
    command, args = mcp_launch_spec()
    server: dict[str, object] = {"command": command}
    if args:
        server["args"] = args
    return {"mcpServers": {"ai-pm-lab-privacy-gate": server}}


def client_config_json() -> str:
    return json.dumps(client_config(), indent=2)
