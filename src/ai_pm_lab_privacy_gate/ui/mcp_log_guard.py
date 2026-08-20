from __future__ import annotations

import os

from ai_pm_lab_privacy_gate.infrastructure.mcp.remote import RemoteMcpManager


_INSTALLED = False


def install_mcp_log_guard() -> None:
    """Keep a stale/locked MCP log from preventing the desktop UI from starting.

    Windows can keep the runtime log open briefly after an MCP/background process
    exits. Log rotation is diagnostic housekeeping and must never be fatal to the
    privacy application itself. If rotation is blocked, continue with the current
    log; if even that file cannot be opened, use a per-process fallback log.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    def guarded_open_log(self: RemoteMcpManager) -> None:
        log_path = getattr(self, "log_path", None)
        if log_path is None:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if log_path.exists() and log_path.stat().st_size > 5_000_000:
            previous = log_path.with_suffix(".previous.log")
            try:
                previous.unlink(missing_ok=True)
                log_path.replace(previous)
            except OSError:
                # A previous MCP/background process may still hold the file on
                # Windows. Rotation is optional; startup is not.
                pass

        try:
            self._log_handle = log_path.open("a", encoding="utf-8", buffering=1)
        except OSError:
            fallback = log_path.with_name(f"mcp-runtime-{os.getpid()}.log")
            self._log_handle = fallback.open("a", encoding="utf-8", buffering=1)

    RemoteMcpManager._open_log = guarded_open_log
