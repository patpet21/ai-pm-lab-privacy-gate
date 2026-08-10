from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ai_pm_lab_privacy_gate.infrastructure.mcp.config import mcp_launch_spec
from ai_pm_lab_privacy_gate.infrastructure.mcp.identity import ConnectionIdentityStore


PUBLIC_URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)


@dataclass(frozen=True)
class RemoteMcpStatus:
    state: str = "stopped"
    public_url: str = ""
    error: str = ""
    local_port: int | None = None


class RemoteMcpManager:
    """Run the local HTTP MCP server and an outbound-only HTTPS quick tunnel."""

    def __init__(self, identity_store: ConnectionIdentityStore | None = None) -> None:
        self.identity_store = identity_store or ConnectionIdentityStore()
        self._lock = threading.Lock()
        self._status = RemoteMcpStatus()
        self._server_process: subprocess.Popen[str] | None = None
        self._tunnel_process: subprocess.Popen[str] | None = None
        self._monitor_thread: threading.Thread | None = None

    @property
    def status(self) -> RemoteMcpStatus:
        with self._lock:
            return self._status

    def start(self) -> None:
        if self.status.state in {"starting", "online"}:
            return
        self.stop()
        self._set_status(RemoteMcpStatus(state="starting"))
        self._monitor_thread = threading.Thread(target=self._start_worker, daemon=True)
        self._monitor_thread.start()

    def stop(self) -> None:
        for process in (self._tunnel_process, self._server_process):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
        self._tunnel_process = None
        self._server_process = None
        self._set_status(RemoteMcpStatus(state="stopped"))

    def _start_worker(self) -> None:
        try:
            identity = self.identity_store.load_or_create()
            port = self._available_port()
            command, base_args = mcp_launch_spec()
            server_args = [
                *base_args,
                "--transport",
                "streamable-http",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--path",
                identity.mcp_path,
            ]
            self._server_process = self._popen([command, *server_args])
            self._wait_for_port(port, self._server_process)

            cloudflared = self._find_cloudflared()
            self._tunnel_process = self._popen(
                [
                    str(cloudflared),
                    "tunnel",
                    "--url",
                    f"http://127.0.0.1:{port}",
                    "--http-host-header",
                    "127.0.0.1",
                    "--no-autoupdate",
                ],
                merge_output=True,
            )
            public_base = self._read_public_url(self._tunnel_process)
            self._wait_for_public_dns(public_base, self._tunnel_process)
            public_url = f"{public_base}{identity.mcp_path}"
            self._set_status(
                RemoteMcpStatus(state="online", public_url=public_url, local_port=port)
            )
            return_code = self._tunnel_process.wait()
            if self.status.state != "stopped":
                raise RuntimeError(f"Secure tunnel stopped unexpectedly ({return_code}).")
        except Exception as error:
            self._terminate_children()
            self._set_status(RemoteMcpStatus(state="error", error=str(error)))

    def _terminate_children(self) -> None:
        for process in (self._tunnel_process, self._server_process):
            if process and process.poll() is None:
                process.terminate()

    def _set_status(self, status: RemoteMcpStatus) -> None:
        with self._lock:
            self._status = status

    @staticmethod
    def _available_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            return int(listener.getsockname()[1])

    @staticmethod
    def _wait_for_port(port: int, process: subprocess.Popen[str]) -> None:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("The local MCP service could not start.")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.25)
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    return
            time.sleep(0.15)
        raise TimeoutError("The local MCP service did not become ready in time.")

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
        details = " | ".join(recent_lines)
        raise RuntimeError(f"The secure HTTPS link could not be created. {details}")

    @staticmethod
    def _wait_for_public_dns(url: str, process: subprocess.Popen[str]) -> None:
        hostname = urlparse(url).hostname
        if not hostname:
            raise RuntimeError("The secure tunnel returned an invalid address.")
        deadline = time.monotonic() + 35
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("The secure tunnel stopped before its address became ready.")
            try:
                socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
                return
            except OSError as error:
                last_error = error
                time.sleep(0.5)
        raise RuntimeError(f"The secure tunnel address is not reachable yet: {last_error}")

    @staticmethod
    def _find_cloudflared() -> Path:
        override = os.environ.get("PRIVACY_GATE_CLOUDFLARED")
        candidates: list[Path] = []
        if override:
            candidates.append(Path(override))
        if getattr(sys, "frozen", False):
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
            "The secure-link component is missing. Reinstall Privacy Gate to restore cloudflared.exe."
        )

    @staticmethod
    def _popen(command: list[str], *, merge_output: bool = False) -> subprocess.Popen[str]:
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW
        return subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if merge_output else subprocess.DEVNULL,
            stderr=subprocess.STDOUT if merge_output else subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
