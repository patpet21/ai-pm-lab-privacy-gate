from __future__ import annotations

"""One visible loading experience for long-running PrivacyGate operations.

This runtime does not replace business logic. It provides one modal, non-blocking
operation surface and adapts the existing Protect, Restore and connected-source
workflows to it. The important rule is lifetime: the surface stays visible until
the real worker/operation completes, rather than disappearing after a button
handler returns.
"""

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from types import MethodType
from typing import Any

from PySide6.QtCore import (
    QEventLoop,
    QObject,
    QRunnable,
    QThreadPool,
    QTimer,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon


@dataclass(slots=True)
class _Operation:
    title: str
    message: str


class UnifiedLoadingDialog(QDialog):
    """Reusable application-modal progress surface with a live Qt event loop."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("UnifiedLoadingDialog")
        self.setWindowTitle("PrivacyGate is working")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(470)
        self.setMaximumWidth(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(13)

        top = QHBoxLayout()
        top.setSpacing(12)
        badge = QLabel()
        badge.setFixedSize(46, 46)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(icon("protect", color="#0B7F89", size=25).pixmap(25, 25))
        badge.setStyleSheet(
            "background:#E8F7F7;border:1px solid #B8E1E4;border-radius:23px;"
        )
        top.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(3)
        self.title_label = QLabel("Working locally…")
        self.title_label.setStyleSheet("color:#062B4F;font-size:16px;font-weight:900;")
        self.message_label = QLabel("Please wait while PrivacyGate completes this operation.")
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("color:#4F687A;font-size:10px;font-weight:600;")
        copy.addWidget(self.title_label)
        copy.addWidget(self.message_label)
        top.addLayout(copy, 1)

        self.spinner = QLabel("◐")
        self.spinner.setFixedSize(34, 34)
        self.spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner.setStyleSheet("color:#0B7F89;font-size:24px;font-weight:900;")
        top.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(top)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#E6EDF1;border:none;")
        root.addWidget(line)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(9)
        self.progress.setStyleSheet(
            "QProgressBar{background:#EDF3F5;border:0;border-radius:4px;}"
            "QProgressBar::chunk{background:#0B858A;border-radius:4px;}"
        )
        root.addWidget(self.progress)

        self.note = QLabel("Keep PrivacyGate open. This window closes automatically when the operation is finished.")
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color:#78909F;font-size:8px;")
        root.addWidget(self.note)

        self.setStyleSheet(
            "QDialog#UnifiedLoadingDialog{background:#FFFFFF;border:1px solid #C9D8E1;}"
        )

        self._frames = ("◐", "◓", "◑", "◒")
        self._frame = 0
        self._timer = QTimer(self)
        self._timer.setInterval(110)
        self._timer.timeout.connect(self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(self._frames)
        self.spinner.setText(self._frames[self._frame])

    def present(self, title: str, message: str) -> None:
        self.title_label.setText(title or "PrivacyGate is working")
        self.message_label.setText(message or "Completing the requested operation…")
        self._frame = 0
        self.spinner.setText(self._frames[0])
        if not self._timer.isActive():
            self._timer.start()
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

    def dismiss(self) -> None:
        self._timer.stop()
        self.hide()

    def reject(self) -> None:
        # Long-running operations own the lifetime of this dialog.
        return


class UnifiedLoadingController(QObject):
    """Tracks overlapping operations and displays the most recently updated one."""

    def __init__(self, main_window: QWidget) -> None:
        super().__init__(main_window)
        self.main_window = main_window
        self.dialog = UnifiedLoadingDialog(main_window)
        self._operations: OrderedDict[str, _Operation] = OrderedDict()

    def begin(self, key: str, title: str, message: str) -> None:
        key = str(key or "operation")
        self._operations.pop(key, None)
        self._operations[key] = _Operation(title=title, message=message)
        self._render()

    def update(self, key: str, title: str | None = None, message: str | None = None) -> None:
        key = str(key or "operation")
        current = self._operations.get(key)
        if current is None:
            self.begin(
                key,
                title or "PrivacyGate is working",
                message or "Completing the requested operation…",
            )
            return
        self._operations.pop(key, None)
        self._operations[key] = _Operation(
            title=title if title is not None else current.title,
            message=message if message is not None else current.message,
        )
        self._render()

    def end(self, key: str) -> None:
        self._operations.pop(str(key or "operation"), None)
        self._render()

    def clear(self) -> None:
        self._operations.clear()
        self._render()

    def active(self, key: str | None = None) -> bool:
        if key is None:
            return bool(self._operations)
        return str(key) in self._operations

    def _render(self) -> None:
        if not self._operations:
            self.dialog.dismiss()
            return
        operation = next(reversed(self._operations.values()))
        self.dialog.present(operation.title, operation.message)


def _controller_for(widget: QWidget | None) -> UnifiedLoadingController | None:
    current = widget
    while current is not None:
        controller = getattr(current, "_unified_loading", None)
        if isinstance(controller, UnifiedLoadingController):
            return controller
        current = current.parentWidget()
    app = QApplication.instance()
    if app is not None:
        for window in app.topLevelWidgets():
            controller = getattr(window, "_unified_loading", None)
            if isinstance(controller, UnifiedLoadingController):
                return controller
    return None


class _BlockingSignals(QObject):
    result = Signal(object)
    error = Signal(object)
    finished = Signal()


class _BlockingWorker(QRunnable):
    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = _BlockingSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.result.emit(self.operation())
        except Exception as exc:  # preserve the original exception type
            self.signals.error.emit(exc)
        finally:
            self.signals.finished.emit()


def run_with_unified_loading(
    parent: QWidget,
    title: str,
    message: str,
    operation: Callable[[], Any],
    *,
    key: str | None = None,
) -> Any:
    """Run legacy synchronous work off the UI thread while keeping Qt responsive."""

    controller = _controller_for(parent)
    if controller is None:
        return operation()

    state: dict[str, Any] = {"value": None, "error": None}
    loop = QEventLoop()
    worker = _BlockingWorker(operation)
    operation_key = key or f"blocking:{id(worker)}"

    worker.signals.result.connect(lambda value: state.__setitem__("value", value))
    worker.signals.error.connect(lambda error: state.__setitem__("error", error))
    worker.signals.finished.connect(loop.quit)

    controller.begin(operation_key, title, message)
    QThreadPool.globalInstance().start(worker)
    loop.exec()
    controller.end(operation_key)

    error = state["error"]
    if error is not None:
        raise error
    return state["value"]


def _protection_fingerprint(workflow_module, page) -> tuple[tuple[str, int, int], ...]:
    items = tuple(workflow_module._protection_sources(page) or ())
    return tuple(
        (
            str(item.get("key") or ""),
            id(item.get("result")),
            len(tuple(getattr(item.get("result"), "applied_findings", ()) or ())),
        )
        for item in items
    )


def _patch_privacy_check_runtime(main_window, controller: UnifiedLoadingController) -> None:
    from ai_pm_lab_privacy_gate.ui import protect_workflow_v2 as workflow

    if not getattr(workflow, "_unified_loading_patched", False):
        workflow._unified_loading_patched = True
        original_show_loading = workflow._show_loading
        original_render_summary = workflow._render_summary
        original_start = workflow._start_privacy_check

        def show_loading(page) -> None:
            original_show_loading(page)
            # Do not expose an unfinished Privacy Check tab. It becomes visible
            # only when a real summary (or a real error state) is ready.
            try:
                page.preview_tabs.setTabVisible(page._privacy_check_tab_index, False)
            except Exception:
                pass
            current = _controller_for(page)
            if current is not None:
                current.update(
                    "protect.workflow",
                    "Privacy Check",
                    "Running the local second scan on the protected result…",
                )

        def render_summary(page, summary) -> None:
            original_render_summary(page, summary)
            try:
                page.preview_tabs.setTabVisible(page._privacy_check_tab_index, True)
            except Exception:
                pass

        def start_privacy_check(page) -> None:
            fingerprint = _protection_fingerprint(workflow, page)
            if not fingerprint:
                return

            running = getattr(page, "_unified_privacy_running_fingerprint", None)
            completed = getattr(page, "_unified_privacy_completed_fingerprint", None)
            if fingerprint == running:
                return
            if fingerprint == completed and getattr(page, "_privacy_check_summary", None) is not None:
                try:
                    page.preview_tabs.setTabVisible(page._privacy_check_tab_index, True)
                    if getattr(page, "_privacy_check_open_on_ready", False):
                        page.preview_tabs.setCurrentIndex(page._privacy_check_tab_index)
                        page._privacy_check_open_on_ready = False
                except Exception:
                    pass
                current = _controller_for(page)
                if current is not None:
                    current.end("protect.workflow")
                return

            page._unified_privacy_running_fingerprint = fingerprint
            original_start(page)
            worker = getattr(page, "_privacy_check_worker", None)
            if worker is None:
                page._unified_privacy_running_fingerprint = None
                current = _controller_for(page)
                if current is not None:
                    current.end("protect.workflow")
                return

            def completed_result(_payload: object) -> None:
                page._unified_privacy_completed_fingerprint = fingerprint

            def failed(_message: str) -> None:
                try:
                    page.preview_tabs.setTabVisible(page._privacy_check_tab_index, True)
                    if getattr(page, "_privacy_check_open_on_ready", False):
                        page.preview_tabs.setCurrentIndex(page._privacy_check_tab_index)
                        page._privacy_check_open_on_ready = False
                except Exception:
                    pass

            def finished() -> None:
                if getattr(page, "_unified_privacy_running_fingerprint", None) != fingerprint:
                    return
                page._unified_privacy_running_fingerprint = None
                current = _controller_for(page)
                if current is not None:
                    current.end("protect.workflow")

            worker.signals.result.connect(completed_result)
            worker.signals.error.connect(failed)
            worker.signals.finished.connect(finished)

        workflow._show_loading = show_loading
        workflow._render_summary = render_summary
        workflow._start_privacy_check = start_privacy_check

    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_unified_protect_loading", False):
        return
    page._unified_protect_loading = True
    page._unified_privacy_running_fingerprint = None
    page._unified_privacy_completed_fingerprint = None

    previous_busy = page._set_busy

    def set_busy(self, busy: bool) -> None:
        previous_busy(busy)
        if busy:
            controller.begin(
                "protect.workflow",
                "Scan & Protect",
                "Scanning the selected source(s) locally…",
            )
            return

        def continue_after_scan() -> None:
            # The review/protect compatibility action is intentionally kept. If
            # it has not fired yet, trigger it once; otherwise continue directly
            # to the Privacy Check for the authoritative protected result.
            if workflow._protection_sources(self):
                workflow._start_privacy_check(self)
                return
            protect_button = getattr(self, "_redesign_protect_button", None)
            if (
                getattr(self, "current_findings", ())
                and protect_button is not None
                and protect_button.isEnabled()
            ):
                controller.update(
                    "protect.workflow",
                    "Scan & Protect",
                    "Applying the selected protection choices locally…",
                )
                protect_button.click()
                return
            # No protected result was produced (for example no findings). Do not
            # leave a modal loading surface stuck forever.
            controller.end("protect.workflow")

        QTimer.singleShot(0, continue_after_scan)

    page._set_busy = MethodType(set_busy, page)

    def scan_clicked(*_args) -> None:
        page._unified_privacy_completed_fingerprint = None
        controller.begin(
            "protect.workflow",
            "Scan & Protect",
            "Scanning the selected source(s) locally…",
        )

    page.scan_button.clicked.connect(scan_clicked)

    protect_button = getattr(page, "_redesign_protect_button", None)
    if protect_button is not None:
        def protection_clicked(*_args) -> None:
            controller.update(
                "protect.workflow",
                "Scan & Protect",
                "Creating the protected copy from your review choices…",
            )
            QTimer.singleShot(0, lambda: workflow._start_privacy_check(page))

        protect_button.clicked.connect(protection_clicked)

    clear_button = getattr(page, "clear_button", None)
    if clear_button is not None:
        def cleared(*_args) -> None:
            page._unified_privacy_running_fingerprint = None
            page._unified_privacy_completed_fingerprint = None
            controller.end("protect.workflow")

        clear_button.clicked.connect(cleared)


def _patch_restore_loading(main_window, controller: UnifiedLoadingController) -> None:
    page = getattr(main_window, "restore_page", None)
    if page is None or getattr(page, "_unified_restore_loading", False):
        return
    page._unified_restore_loading = True

    previous_busy = page._set_busy
    previous_finished = page._operation_finished

    def set_busy(self, busy: bool, message: str = "") -> None:
        previous_busy(busy, message)
        if busy:
            # Keep disabling controls through the existing implementation, but
            # use the application-wide popup instead of a second inline spinner.
            try:
                self.busy.hide()
            except Exception:
                pass
            controller.begin(
                "restore.workflow",
                "Restore locally",
                message or "Restoring original values on this device…",
            )
        else:
            controller.end("restore.workflow")

    def operation_finished(self) -> None:
        try:
            previous_finished()
        finally:
            controller.end("restore.workflow")

    page._set_busy = MethodType(set_busy, page)
    page._operation_finished = MethodType(operation_finished, page)


def _patch_connected_source_loading() -> None:
    from ai_pm_lab_privacy_gate.ui import connected_apps_browse_polish as browser

    if getattr(browser, "_unified_loading_patched", False):
        return
    browser._unified_loading_patched = True

    def run_busy(parent, title: str, message: str, operation):
        return run_with_unified_loading(
            parent,
            title,
            message,
            operation,
            key=f"connected-source:{id(parent)}",
        )

    browser._run_busy = run_busy


def _patch_contact_loading(main_window, controller: UnifiedLoadingController) -> None:
    page = getattr(main_window, "contact_page", None)
    if page is None or getattr(page, "_unified_contact_loading", False):
        return
    page._unified_contact_loading = True
    page._unified_silent_contact_operation = False

    previous_busy = page._busy
    previous_ready = page._ready
    previous_check_updates = page.check_updates

    def busy(self, button, text: str) -> None:
        previous_busy(button, text)
        if getattr(self, "_unified_silent_contact_operation", False):
            return
        controller.begin(
            "contact.workflow",
            "PrivacyGate online operation",
            text.rstrip("…") + "…",
        )

    def ready(self, button, text: str) -> None:
        previous_ready(button, text)
        if not getattr(self, "_unified_silent_contact_operation", False):
            controller.end("contact.workflow")
        self._unified_silent_contact_operation = False

    def check_updates(self, silent: bool = True) -> None:
        self._unified_silent_contact_operation = bool(silent)
        previous_check_updates(silent=silent)

    page._busy = MethodType(busy, page)
    page._ready = MethodType(ready, page)
    page.check_updates = MethodType(check_updates, page)


def _patch_library_backup_loading(main_window) -> None:
    page = getattr(main_window, "library_page", None)
    if page is None or getattr(page, "_unified_library_loading", False):
        return
    page._unified_library_loading = True

    try:
        page.backup_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    try:
        page.import_backup_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass

    def backup() -> None:
        path, _ = QFileDialog.getSaveFileName(
            page,
            "Create encrypted library backup",
            "AI_PM_LAB_Privacy_Gate_Library.pgbackup",
            "Privacy Gate backup (*.pgbackup)",
        )
        if not path:
            return
        destination_path = path if path.lower().endswith(".pgbackup") else path + ".pgbackup"
        try:
            destination = run_with_unified_loading(
                page,
                "Backing up Library",
                "Creating the encrypted local PrivacyGate backup…",
                lambda: page.library.create_backup(destination_path),
                key="library.backup",
            )
            QMessageBox.information(
                page,
                "Backup created",
                f"Encrypted backup saved to:\n{destination}\n\nIt can be restored only by the same Windows user account.",
            )
        except Exception as error:
            QMessageBox.critical(page, "Backup failed", str(error))

    def restore_backup() -> None:
        path, _ = QFileDialog.getOpenFileName(
            page,
            "Restore encrypted library backup",
            "",
            "Privacy Gate backup (*.pgbackup)",
        )
        if not path:
            return
        answer = QMessageBox.question(
            page,
            "Restore library backup",
            "PrivacyGate will first create a safety backup, then replace the current library. Continue?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            safety_backup = run_with_unified_loading(
                page,
                "Restoring Library",
                "Validating the backup and restoring the encrypted local Library…",
                lambda: page.library.restore_backup(path),
                key="library.restore-backup",
            )
            page.refresh()
            QMessageBox.information(
                page,
                "Library restored",
                f"The backup was restored. A safety copy of the previous library is at:\n{safety_backup}",
            )
        except Exception as error:
            QMessageBox.critical(page, "Restore failed", str(error))

    page.backup_button.clicked.connect(backup)
    page.import_backup_button.clicked.connect(restore_backup)


def _patch_standard_busy_pages(main_window, controller: UnifiedLoadingController) -> None:
    pages = getattr(main_window, "pages", None)
    if pages is None:
        return
    protected = {
        getattr(main_window, "protection_page", None),
        getattr(main_window, "restore_page", None),
    }
    for index in range(pages.count()):
        page = pages.widget(index)
        if page in protected or page is None:
            continue
        previous = getattr(page, "_set_busy", None)
        if not callable(previous) or getattr(page, "_unified_standard_busy", False):
            continue
        page._unified_standard_busy = True
        key = f"page.busy:{id(page)}"
        title = page.__class__.__name__.replace("Page", "").replace("_", " ") or "PrivacyGate"

        def wrapped(self, busy: bool, *args, __previous=previous, __key=key, __title=title, **kwargs):
            result = __previous(busy, *args, **kwargs)
            message = next((str(value) for value in args if isinstance(value, str) and value.strip()), "")
            if busy:
                controller.begin(
                    __key,
                    f"{__title} is working",
                    message or "Completing this operation…",
                )
            else:
                controller.end(__key)
            return result

        page._set_busy = MethodType(wrapped, page)


def apply_global_loading_runtime(main_window) -> None:
    """Install the unified, real-lifetime loading experience across the app."""

    if getattr(main_window, "_unified_loading_runtime", False):
        return
    main_window._unified_loading_runtime = True

    controller = UnifiedLoadingController(main_window)
    main_window._unified_loading = controller

    pages = getattr(main_window, "pages", None)
    if pages is not None:
        for index in range(pages.count()):
            page = pages.widget(index)
            if page is not None:
                page._unified_loading = controller

    _patch_connected_source_loading()
    _patch_privacy_check_runtime(main_window, controller)
    _patch_restore_loading(main_window, controller)
    _patch_contact_loading(main_window, controller)
    _patch_library_backup_loading(main_window)
    _patch_standard_busy_pages(main_window, controller)
