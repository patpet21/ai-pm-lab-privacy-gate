from __future__ import annotations

import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from concurrent.futures.process import BrokenProcessPool
from typing import Any

from .browser_file_worker_v2 import run_browser_file_worker_v2


DEFAULT_FILE_WORKER_TIMEOUT_SECONDS = 75
DEFAULT_FILE_WORKERS = 2


class BrowserFileWorkerUnavailable(RuntimeError):
    pass


class BrowserFileProcessExecutorV2:
    """Concurrent isolated browser-file workers with no global request lock.

    Analyze/protect requests are stateless, so any worker can serve either step.
    This lets two AI tabs process files concurrently without coupling one browser
    provider to another. One worker is warmed in the background after bridge start.
    """

    def __init__(
        self,
        *,
        timeout_seconds: int = DEFAULT_FILE_WORKER_TIMEOUT_SECONDS,
        max_workers: int = DEFAULT_FILE_WORKERS,
    ) -> None:
        self.timeout_seconds = max(15, int(timeout_seconds))
        self.max_workers = max(1, int(max_workers))
        self._pool_lock = threading.RLock()
        self._pool: ProcessPoolExecutor | None = None
        self._warm_started = False

    def _ensure_pool(self) -> ProcessPoolExecutor:
        with self._pool_lock:
            if self._pool is None:
                self._pool = ProcessPoolExecutor(
                    max_workers=self.max_workers,
                    mp_context=multiprocessing.get_context("spawn"),
                )
            return self._pool

    def warm_async(self) -> None:
        with self._pool_lock:
            if self._warm_started:
                return
            self._warm_started = True
            pool = self._ensure_pool()
        try:
            future = pool.submit(run_browser_file_worker_v2, {"operation": "warmup"})
        except Exception:
            return

        def consume() -> None:
            try:
                future.result(timeout=self.timeout_seconds)
            except Exception:
                return

        threading.Thread(
            target=consume,
            name="PrivacyGateBrowserFileWarmup",
            daemon=True,
        ).start()

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        pool = self._ensure_pool()
        try:
            future = pool.submit(run_browser_file_worker_v2, request)
            result = future.result(timeout=self.timeout_seconds)
        except TimeoutError as error:
            future.cancel()
            raise BrowserFileWorkerUnavailable(
                "local file worker timed out"
            ) from error
        except BrokenProcessPool as error:
            self._reset_pool()
            raise BrowserFileWorkerUnavailable(
                "local file worker exited unexpectedly"
            ) from error
        except (ValueError, KeyError):
            raise
        except Exception as error:
            raise BrowserFileWorkerUnavailable(
                f"local file worker failed: {type(error).__name__}"
            ) from error

        if not isinstance(result, dict):
            raise BrowserFileWorkerUnavailable("local file worker returned invalid data")
        return result

    def _reset_pool(self) -> None:
        with self._pool_lock:
            pool = self._pool
            self._pool = None
            self._warm_started = False
        if pool is None:
            return
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    def close(self) -> None:
        with self._pool_lock:
            pool = self._pool
            self._pool = None
        if pool is None:
            return
        processes = list(getattr(pool, "_processes", {}).values())
        for process in processes:
            try:
                if process.is_alive():
                    process.terminate()
            except Exception:
                pass
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
