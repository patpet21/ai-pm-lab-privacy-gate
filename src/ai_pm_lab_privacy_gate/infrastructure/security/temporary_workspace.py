from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path


_ROOT = Path(tempfile.gettempdir()) / "AI_PM_LAB_Privacy_Gate" / "managed"
_SESSION_ID = f"session-{os.getpid()}-{uuid.uuid4().hex[:10]}"
_SESSION_DIR = _ROOT / _SESSION_ID
_PENDING: set[Path] = set()
_PathBase = type(Path())


class ManagedReadOncePath(_PathBase):
    """Path that deletes itself after its text payload is consumed once."""

    def read_text(self, *args, **kwargs):  # type: ignore[override]
        try:
            return super().read_text(*args, **kwargs)
        finally:
            delete_managed_path(self)


def managed_root() -> Path:
    """Root used exclusively by PrivacyGate-managed temporary working copies."""
    return _ROOT


def current_session_dir() -> Path:
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return _SESSION_DIR


def _safe_component(value: str, fallback: str = "working-file") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in value).strip(" ._")
    return cleaned or fallback


def new_working_path(provider: str, filename: str) -> Path:
    """Return a unique path owned by this PrivacyGate process.

    This function never points at a user-selected source file. Only connector
    downloads/exports created by PrivacyGate should use these paths.
    """
    provider_dir = current_session_dir() / _safe_component(provider, "source")
    provider_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_component(filename)
    return provider_dir / f"{uuid.uuid4().hex[:10]}-{safe_name}"


def as_read_once_path(path: str | Path) -> Path:
    """Wrap a managed text file so the first successful/failed read removes it."""
    if not is_managed_path(path):
        return Path(path)
    return ManagedReadOncePath(str(path))


def is_managed_path(path: str | Path | None) -> bool:
    if not path:
        return False
    try:
        candidate = Path(path).resolve(strict=False)
        root = _ROOT.resolve(strict=False)
        return candidate == root or root in candidate.parents
    except Exception:
        return False


def _prune_empty_parents(start: Path) -> None:
    current = start
    root = _ROOT.resolve(strict=False)
    while True:
        try:
            resolved = current.resolve(strict=False)
        except Exception:
            return
        if resolved == root or root not in resolved.parents:
            return
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def delete_managed_path(path: str | Path | None) -> bool:
    """Delete one PrivacyGate-owned temporary file/directory, never user files.

    Returns True when the target is gone. If Windows still has the file open,
    the path is queued and retried automatically later.
    """
    if not is_managed_path(path):
        return False
    target = Path(path)
    try:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=False)
        else:
            target.unlink(missing_ok=True)
        _PENDING.discard(target)
        _prune_empty_parents(target.parent)
        return True
    except OSError:
        _PENDING.add(target)
        return False


def mark_for_cleanup(path: str | Path | None) -> None:
    if is_managed_path(path):
        _PENDING.add(Path(path))
        retry_pending_cleanup()


def retry_pending_cleanup() -> None:
    for path in tuple(_PENDING):
        delete_managed_path(path)


def cleanup_current_session() -> None:
    """Best-effort cleanup when PrivacyGate really exits."""
    retry_pending_cleanup()
    if _SESSION_DIR.exists():
        try:
            shutil.rmtree(_SESSION_DIR)
        except OSError:
            # Do not touch anything outside the managed session. A later startup
            # will remove an old managed session after the safety age threshold.
            return


def cleanup_stale_managed_sessions(max_age_seconds: int = 12 * 60 * 60) -> int:
    """Remove abandoned *new managed* sessions only.

    Legacy PrivacyGate temp folders are intentionally excluded so existing user
    test artifacts are not silently deleted during rollout of this cleanup.
    """
    if not _ROOT.exists():
        return 0
    cutoff = time.time() - max_age_seconds
    removed = 0
    for child in _ROOT.iterdir():
        if not child.is_dir() or child == _SESSION_DIR:
            continue
        try:
            modified = child.stat().st_mtime
        except OSError:
            continue
        if modified > cutoff:
            continue
        try:
            shutil.rmtree(child)
            removed += 1
        except OSError:
            continue
    return removed


atexit.register(cleanup_current_session)
