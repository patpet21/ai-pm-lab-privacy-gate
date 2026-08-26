from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class FunctionWorker(QRunnable):
    def __init__(self, function: Callable[[], object]) -> None:
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.result.emit(self.function())
        except Exception as exc:
            # UI error surfaces should show the service message, not a Python
            # module/class prefix such as ``...TeamServiceError:``. Keep the
            # exception itself untouched for callers; only humanize the emitted
            # presentation string.
            detail = str(exc).strip() or type(exc).__name__
            try:
                self.signals.error.emit(detail)
            except RuntimeError:
                # The owning window may have closed while background I/O was
                # finishing. There is no UI left to receive this result.
                pass
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass
