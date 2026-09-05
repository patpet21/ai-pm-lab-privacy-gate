from __future__ import annotations

import multiprocessing
import re
import threading
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from concurrent.futures.process import BrokenProcessPool
from typing import Any

from .browser_file_worker_v2 import run_browser_file_worker_v2


DEFAULT_FILE_WORKER_TIMEOUT_SECONDS = 55
DEFAULT_FILE_WORKERS = 1


class BrowserFileWorkerUnavailable(RuntimeError):
    pass


def _safe_error_detail(error: BaseException) -> str:
    text = re.sub(r"\s+", " ", str(error or "")).strip()
    if not text:
        return type(error).__name__
    return text[:220]


class BrowserFileProcessExecutorV2:
    """One persistent isolated browser-file worker with queued requests.

    The previous two-worker warmup could start two full spaCy/Presidio stacks at
    once on Windows and poison the ProcessPool before the first real upload. One
    persistent worker keeps the desktop process isolated, avoids duplicate NLP
    memory, and lets ThreadingHTTPServer queue requests from multiple AI tabs
    without rejecting them through a global lock. The worker remains warm after
    its first successful file operation.
    """

    def __init__(
        self,
        *,
        timeout_seconds: int = DEFAULT_FILE_WORKER_TIMEOUT_SECONDS,
        max_workers: int = DEFAULT_FILE_WORKERS,
    ) -> None:
        self.timeout_seconds = max(15, int(timeout_seconds))
        # Deliberately clamp production execution to one heavy NLP worker. This is
        # isolation, not a throughput pool: concurrent HTTP requests queue safely.
        self.max_workers = 1
        self._pool_lock = threading.RLock()
        self._pool: ProcessPoolExecutor | None = None

    def _ensure_pool(self) -> ProcessPoolExecutor:
        with self._pool_lock:
            if self._pool is None:
                self._pool = ProcessPoolExecutor(
                    max_workers=1,
                    mp_context=multiprocessing.get_context("spawn"),
                )
            return self._pool

    def warm_async(self) -> None:
        # No eager spaCy/Presidio warmup. On Windows an eager ProcessPool warmup
        # was able to poison the pool before a real file arrived. The first file
        # starts the worker; subsequent requests reuse the same warm process.
        return

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        pool = self._ensure_pool()
        future = None
        try:
            future = pool.submit(run_browser_file_worker_v2, request)
            result = future.result(timeout=self.timeout_seconds)
        except TimeoutError as error:
            if future is not None:
                future.cancel()
            self._reset_pool(kill=True)
            raise BrowserFileWorkerUnavailable(
                "local file worker timed out"
            ) from error
        except BrokenProcessPool as error:
            self._reset_pool(kill=True)
            raise BrowserFileWorkerUnavailable(
                "local file worker exited unexpectedly"
            ) from error
        except (ValueError, KeyError):
            raise
        except Exception as error:
            # Preserve a short non-PII technical cause so development builds can
            # distinguish import/model/native-library failures from transport bugs.
            raise BrowserFileWorkerUnavailable(
                f"{type(error).__name__}: {_safe_error_detail(error)}"
            ) from error

        if not isinstance(result, dict):
            raise BrowserFileWorkerUnavailable("local file worker returned invalid data")
        return result

    def _reset_pool(self, *, kill: bool) -> None:
        with self._pool_lock:
            pool = self._pool
            self._pool = None
        if pool is None:
            return
        if kill:
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
        self._reset_pool(kill=True)
