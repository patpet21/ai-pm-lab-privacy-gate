from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from dataclasses import dataclass

from ai_pm_lab_privacy_gate.infrastructure.mcp.config import mcp_launch_spec
from ai_pm_lab_privacy_gate.infrastructure.mcp.identity import ConnectionIdentityStore
from ai_pm_lab_privacy_gate.infrastructure.mcp.modes import ConnectionMode
from ai_pm_lab_privacy_gate.infrastructure.mcp.provisioning import ProvisioningStore
from ai_pm_lab_privacy_gate.infrastructure.mcp.tunnels import (
    CloudflaredRuntime,
    NamedTunnelProvider,
    QuickTunnelProvider,
    TunnelProvider,
)
from ai_pm_lab_privacy_gate.infrastructure.auth.supabase_account import (
    SUPABASE_ISSUER,
    SUPABASE_JWKS_URL,
    SUPABASE_TOKEN_AUDIENCE,
    USER_ID_SECRET,
)


@dataclass(frozen=True)
class RemoteMcpStatus:
    state: str = "stopped"
    mode: str = ConnectionMode.LOCAL.value
    public_url: str = ""
    error: str = ""
    local_port: int | None = None


class RemoteMcpManager:
    """Supervise the loopback MCP process and one explicit tunnel mode."""

    def __init__(self, identity_store: ConnectionIdentityStore | None = None) -> None:
        self.identity_store = identity_store or ConnectionIdentityStore()
        self.provisioning_store = ProvisioningStore(
            self.identity_store.data_dir, self.identity_store.secrets
        )
        self._lock = threading.Lock()
        self._status = RemoteMcpStatus()
        self._server_process: subprocess.Popen[str] | None = None
        self._tunnel_process: subprocess.Popen[str] | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def status(self) -> RemoteMcpStatus:
        with self._lock:
            return self._status

    def start(self, mode: ConnectionMode | None = None) -> None:
        selected_mode = mode or self.identity_store.connection_mode()
        if selected_mode is ConnectionMode.LOCAL:
            raise ValueError("Local-only mode does not create a remote tunnel")
        if self.status.state in {"starting", "online", "reconnecting"}:
            return
        self.stop()
        self._stop_event = threading.Event()
        self._set_status(RemoteMcpStatus(state="starting", mode=selected_mode.value))
        self._monitor_thread = threading.Thread(
            target=self._supervise, args=(selected_mode, self._stop_event), daemon=True
        )
        self._monitor_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for process in (self._tunnel_process, self._server_process):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
        self._tunnel_process = None
        self._server_process = None
        monitor = self._monitor_thread
        if monitor and monitor.is_alive() and monitor is not threading.current_thread():
            monitor.join(timeout=5)
        self._monitor_thread = None
        self._set_status(RemoteMcpStatus(state="stopped"))

    def _supervise(self, mode: ConnectionMode, stop_event: threading.Event) -> None:
        retry_delay = 1.0
        while not stop_event.is_set():
            try:
                self._run_once(mode, stop_event)
                if stop_event.is_set():
                    return
                raise RuntimeError("The secure connection stopped unexpectedly.")
            except Exception as error:
                self._terminate_children()
                if stop_event.is_set():
                    return
                if mode is ConnectionMode.DEV_QUICK:
                    self._set_status(
                        RemoteMcpStatus(state="error", mode=mode.value, error=str(error))
                    )
                    return
                self._set_status(
                    RemoteMcpStatus(
                        state="reconnecting",
                        mode=mode.value,
                        error=f"Connection interrupted. Reconnecting automatically: {error}",
                    )
                )
                if stop_event.wait(retry_delay):
                    return
                retry_delay = min(retry_delay * 2, 30.0)

    def _run_once(self, mode: ConnectionMode, stop_event: threading.Event) -> None:
        port, path, provider, auth_args = self._runtime(mode)
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
            path,
            *auth_args,
        ]
        self._server_process = self._popen_server([command, *server_args])
        self._wait_for_port(port, self._server_process)
        session = provider.start(port)
        self._tunnel_process = session.process
        public_url = session.public_url + (path if mode is ConnectionMode.DEV_QUICK else "")
        self._set_status(
            RemoteMcpStatus(
                state="online",
                mode=mode.value,
                public_url=public_url,
                local_port=port,
            )
        )
        while not stop_event.wait(0.5):
            server_code = self._server_process.poll()
            tunnel_code = self._tunnel_process.poll()
            if server_code is not None:
                raise RuntimeError(f"Local protected-library service stopped ({server_code}).")
            if tunnel_code is not None:
                raise RuntimeError(f"Secure tunnel stopped ({tunnel_code}).")

    def _runtime(
        self, mode: ConnectionMode
    ) -> tuple[int, str, TunnelProvider, list[str]]:
        if mode is ConnectionMode.DEV_QUICK:
            return self._available_port(), self.identity_store.dev_mcp_path(), QuickTunnelProvider(), []
        configuration = self.provisioning_store.load()
        if configuration is None:
            raise RuntimeError("This installation has not been provisioned for a stable connection.")
        configuration.validate()
        account_user_id = self.identity_store.secrets.get(USER_ID_SECRET)
        if not account_user_id:
            raise RuntimeError("Sign in to your Privacy Gate account before starting remote MCP.")
        auth_args = [
            "--auth-mode",
            "jwt",
            "--resource",
            f"https://{configuration.hostname}/mcp",
            "--issuer",
            SUPABASE_ISSUER,
            "--jwks-url",
            SUPABASE_JWKS_URL,
            "--token-audience",
            SUPABASE_TOKEN_AUDIENCE,
            "--expected-subject",
            account_user_id,
        ]
        return 8766, "/mcp", NamedTunnelProvider(configuration, self.provisioning_store), auth_args

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
    def _popen_server(command: list[str]) -> subprocess.Popen[str]:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        return subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
