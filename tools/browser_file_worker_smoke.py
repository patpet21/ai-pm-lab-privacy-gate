from __future__ import annotations

import sys
import time

from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_file_executor_v2 import (
    BrowserFileProcessExecutorV2,
)


def main() -> int:
    executor = BrowserFileProcessExecutorV2(timeout_seconds=55)
    started = time.perf_counter()
    try:
        result = executor.execute({"operation": "warmup"})
    except Exception as error:
        print(f"WORKER_FAIL {type(error).__name__}: {error}", flush=True)
        return 1
    finally:
        executor.close()

    elapsed = time.perf_counter() - started
    pid = result.get("worker_pid") if isinstance(result, dict) else None
    status = result.get("status") if isinstance(result, dict) else None
    print(f"WORKER_OK status={status} pid={pid} elapsed={elapsed:.2f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
