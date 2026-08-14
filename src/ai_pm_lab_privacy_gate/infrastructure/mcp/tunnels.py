from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO
from urllib.parse import urlparse

from ai_pm_lab_privacy_gate.infrastructure.mcp.provisioning import (
    NamedTunnelConfiguration,
    ProvisioningStore,
)


PUBLIC_URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)


@dataclass
class TunnelSession:
    process: subprocess.Popen[str]
    public_url: str


class TunnelProvider(Protocol):
    def start(self, local_port: int) -> TunnelSession: ...


class CloudflaredRuntime:
    @staticmethod
    def executable() -> Path:
        override = os.environ.get("PRIVACY_GATE_CLOUDFLARED")
        candidates: list[Path] = []
        if override:
            candidates.append(Path(override))
        if getattr(sys, "frozen", False):
            if sys.platform == "darwin":
                candidates.append(Path(sys.executable).parents[1] / "Resources" / "cloudflared")
            else:
                candidates.append(Path(sys.executable).with_name("cloudflared.exe"))
        discovered = shutil.which("cloudflared")
        if discovered:
            candidates.append(Path(discovered))
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(variable)
            if root:
                candidates.append(Path(root) / "cloudflared" / "cloudflared.exe")
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(
            "The secure-link component is missing. Reinstall Privacy Gate to restore cloudflared."
        )

    @staticmethod
    def popen(
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
        capture_output: bool = True,
        output: TextIO | None = None,
    ) -> subprocess.Popen[str]:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        stdout = subprocess.PIPE if capture_output else (output or subprocess.DEVNULL)
        stderr = subprocess.STDOUT if capture_output or output else subprocess.DEVNULL
        return subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            env=environment,
        )


class QuickTunnelProvider:
    """Temporary, session-based tunnel for explicit development/testing only."""

    def start(self, local_port: int) -> TunnelSession:
        process = CloudflaredRuntime.popen(
            [
                str(CloudflaredRuntime.executable()),
                "tunnel",
                "--url",
                f"http://127.0.0.1:{local_port}",
                "--http-host-header",
                "127.0.0.1",
                "--no-autoupdate",
            ]
        )
        public_url = self._read_public_url(process)
        self._wait_for_public_dns(public_url, process)
        return TunnelSession(process=process, public_url=public_url)

    @staticmethod
    def _read_public_url(process: subprocess.Popen[str]) -> str:
        if process.stdout is None:
            raise RuntimeError("Secure tunnel output is unavailable.")
        deadline = time.monotonic() + 50
        public_url = ""
        recent_lines: list[str] = []
        while time.monotonic() < deadline:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                recent_lines.append(line.strip())
                recent_lines = recent_lines[-8:]
            match = PUBLIC_URL_PATTERN.search(line)
            if match:
                public_url = match.group(0)
            if public_url and "Registered tunnel connection" in line:
                return public_url
        raise RuntimeError(
            "The temporary HTTPS link could not be created. " + " | ".join(recent_lines)
        )

    @staticmethod
    def _wait_for_public_dns(url: str, process: subprocess.Popen[str]) -> None:
        hostname = urlparse(url).hostname
        if not hostname:
            raise RuntimeError("The temporary tunnel returned an invalid address.")
        deadline = time.monotonic() + 35
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("The temporary tunnel stopped before becoming ready.")
            try:
                socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
                return
            except OSError as error:
                last_error = error
                time.sleep(0.5)
        raise RuntimeError(f"The temporary tunnel is not reachable yet: {last_error}")


class NamedTunnelProvider:
    """Run one already-provisioned remotely managed tunnel with its device token."""

    def __init__(
        self,
        configuration: NamedTunnelConfiguration,
        provisioning_store: ProvisioningStore,
        log_output: TextIO | None = None,
    ) -> None:
        self.configuration = configuration
        self.provisioning_store = provisioning_store
        self.log_output = log_output

    def start(self, local_port: int) -> TunnelSession:
        if local_port != 8766:
            raise ValueError("The production MCP origin must use loopback port 8766")
        token = self.provisioning_store.tunnel_token()
        if not token:
            raise RuntimeError("The device tunnel credential is missing or has been revoked.")
        environment = os.environ.copy()
        environment["TUNNEL_TOKEN"] = token
        process = CloudflaredRuntime.popen(
            [
                str(CloudflaredRuntime.executable()),
                "tunnel",
                "--no-autoupdate",
                "run",
            ],
            environment=environment,
            # A long-running named tunnel must not write into an unread pipe:
            # once the OS buffer fills cloudflared would otherwise stall.
            capture_output=False,
            output=self.log_output,
        )
        started = time.monotonic()
        deadline = started + 12
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("The production tunnel could not start.")
            time.sleep(0.2)
            if time.monotonic() - started >= 2:
                return TunnelSession(process=process, public_url=self.configuration.mcp_url)
        return TunnelSession(process=process, public_url=self.configuration.mcp_url)
