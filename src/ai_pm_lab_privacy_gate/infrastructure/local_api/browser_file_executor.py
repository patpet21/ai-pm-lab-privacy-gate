from __future__ import annotations

import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from concurrent.futures.process import BrokenProcessPool
from typing import Any

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService

from .browser_file_worker import (
    BrowserFileWorkerRuntime,
    run_browser_file_worker_request,
)


DEFAULT_FILE_WORKER_TIMEOUT_SECONDS = 180


class BrowserFileWorkerUnavailable(RuntimeError):
    """Raised when the isolated browser file worker cannot complete safely."""


class BrowserFileProcessExecutor:
    """Single warm spawned process for browser document analysis/protection.

    Keeping this work out of the desktop process prevents PDF parsing, OCR, spaCy
    model loading and Office rewriting from starving or crashing the Qt event loop.
    The pool is created lazily on the first browser file operation.
    """

    def __init__(self, *, timeout_seconds: int = DEFAULT_FILE_WORKER_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = max(10, int(timeout_seconds))
        self._lock = threading.Lock()
        self._pool: ProcessPoolExecutor | None = None

    def _ensure_pool(self) -> ProcessPoolExecutor:
        if self._pool is None:
            self._pool = ProcessPoolExecutor(
                max_workers=1,
                mp_context=multiprocessing.get_context("spawn"),
            )
        return self._pool

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            pool = self._ensure_pool()
            try:
                future = pool.submit(run_browser_file_worker_request, request)
                result = future.result(timeout=self.timeout_seconds)
            except TimeoutError as error:
                self._reset_pool(kill=True)
                raise BrowserFileWorkerUnavailable(
                    "browser file worker timed out; the desktop stayed isolated"
                ) from error
            except BrokenProcessPool as error:
                self._reset_pool(kill=True)
                raise BrowserFileWorkerUnavailable(
                    "browser file worker exited unexpectedly; the desktop stayed isolated"
                ) from error
            except (ValueError, KeyError):
                # Validation errors are expected request outcomes and do not poison
                # the worker. Preserve them for the HTTP layer's normal handling.
                raise
            except Exception as error:
                # A normal Python exception from the child is transported back by
                # ProcessPoolExecutor. Keep the pool reusable, but surface a stable
                # local error rather than letting it affect the GUI process.
                raise BrowserFileWorkerUnavailable(
                    f"browser file worker failed: {type(error).__name__}"
                ) from error

            if not isinstance(result, dict):
                raise BrowserFileWorkerUnavailable(
                    "browser file worker returned an invalid response"
                )
            return result

    def _reset_pool(self, *, kill: bool) -> None:
        pool = self._pool
        self._pool = None
        if pool is None:
            return

        if kill:
            # ProcessPoolExecutor does not expose a portable terminate-running-task
            # API on all supported Python versions. Terminate its one private worker
            # before shutdown so a stuck native PDF/OCR call cannot linger after the
            # bridge has already failed closed.
            processes = list(getattr(pool, "_processes", {}).values())
            for process in processes:
                try:
                    if process.is_alive():
                        process.terminate()
                except Exception:
                    pass
            for process in processes:
                try:
                    process.join(timeout=0.75)
                except Exception:
                    pass

        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    def close(self) -> None:
        with self._lock:
            self._reset_pool(kill=True)


class InlineBrowserFileExecutor:
    """Deterministic in-process executor for unit tests only."""

    def __init__(self, service: PrivacyGateService) -> None:
        self.runtime = BrowserFileWorkerRuntime(service=service)

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.runtime.execute(request)

    def close(self) -> None:
        return
