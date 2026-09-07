from __future__ import annotations

import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_accounts import (
    GmailAccountRegistry,
)
from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_transport import (
    GmailAddonMessage,
    GmailAddonTransport,
)


POLL_INTERVAL_SECONDS = 3.0
ERROR_BACKOFF_SECONDS = 6.0


class GmailAddonBackgroundReceiver(QObject):
    """Receive explicit Gmail add-on sends whenever PrivacyGate is running.

    The add-on relay is intentionally pull-based: Gmail deposits only the message
    the user explicitly chose, and the desktop app retrieves it using the paired
    channel. Previously that polling existed only inside GmailImportDialog, which
    meant Gmail -> PrivacyGate failed unless the user opened Import from Gmail
    first. This receiver owns the polling at app level and surfaces the existing
    review dialog only after an explicit Gmail send arrives.
    """

    def __init__(self, main_window):
        super().__init__(main_window)
        from ai_pm_lab_privacy_gate.ui.gmail_addon_import import _data_dir

        self.window = main_window
        self.registry = GmailAccountRegistry(_data_dir(main_window))
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.futures: dict[str, Future] = {}
        self.last_poll: dict[str, float] = {}
        self.pending: deque[tuple[str, GmailAddonMessage]] = deque()
        self.delivery_active = False
        self.stopped = False

        self.timer = QTimer(self)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def stop(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        self.timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _paired_accounts(self) -> list[dict]:
        try:
            return [
                account
                for account in self.registry.accounts()
                if account.get("paired") and account.get("endpoint")
            ]
        except Exception:
            return []

    @staticmethod
    def _gmail_import_dialog_open() -> bool:
        widget = QApplication.activeModalWidget()
        return bool(widget is not None and widget.objectName() == "GmailImportDialog")

    def _collect_finished(self) -> None:
        for account_id, future in tuple(self.futures.items()):
            if not future.done():
                continue
            self.futures.pop(account_id, None)
            try:
                message = future.result()
            except Exception:
                self.last_poll[account_id] = time.monotonic() + (
                    ERROR_BACKOFF_SECONDS - POLL_INTERVAL_SECONDS
                )
                continue
            self.last_poll[account_id] = time.monotonic()
            if message is not None:
                self.pending.append((account_id, message))

    def _schedule_polls(self) -> None:
        # The manual Gmail import dialog has its own receiver. Never race it for
        # the same one-time relay payload.
        if self.delivery_active or self._gmail_import_dialog_open():
            return

        now = time.monotonic()
        for account in self._paired_accounts():
            account_id = str(account.get("id") or "").strip()
            if not account_id or account_id in self.futures:
                continue
            if now - self.last_poll.get(account_id, 0.0) < POLL_INTERVAL_SECONDS:
                continue
            try:
                transport = GmailAddonTransport(
                    self.registry.data_dir,
                    account_id=account_id,
                    registry=self.registry,
                )
            except Exception:
                self.last_poll[account_id] = now
                continue
            self.futures[account_id] = self.executor.submit(transport.poll, 4.0)

    def _deliver_pending(self) -> None:
        if self.delivery_active or not self.pending:
            return

        # Do not place the Gmail review on top of another application modal. The
        # relay payload has already been copied into local memory, so it is safe to
        # wait until the current dialog closes.
        if QApplication.activeModalWidget() is not None:
            return

        account_id, message = self.pending.popleft()
        try:
            transport = GmailAddonTransport(
                self.registry.data_dir,
                account_id=account_id,
                registry=self.registry,
            )
        except Exception:
            return

        self.delivery_active = True
        try:
            from ai_pm_lab_privacy_gate.ui.gmail_addon_import import GmailImportDialog

            dialog = GmailImportDialog(self.window)
            index = dialog.accounts.findData(account_id)
            if index >= 0 and dialog.accounts.currentIndex() != index:
                dialog.accounts.setCurrentIndex(index)
            dialog.transport = transport
            dialog.render_message(message)
            dialog.exec()
        finally:
            self.delivery_active = False
            self.last_poll[account_id] = time.monotonic()

    def tick(self) -> None:
        if self.stopped:
            return
        self._collect_finished()
        self._deliver_pending()
        self._schedule_polls()


def install_gmail_addon_background_receiver() -> None:
    """Attach one receiver to every MainWindow created by the normal app entrypoint."""

    from ai_pm_lab_privacy_gate.ui.main_window import MainWindow

    if getattr(MainWindow, "_gmail_addon_background_receiver_installed", False):
        return

    original_init = MainWindow.__init__

    def init_with_gmail_receiver(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        receiver = GmailAddonBackgroundReceiver(self)
        self._gmail_addon_background_receiver = receiver
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(receiver.stop)

    MainWindow.__init__ = init_with_gmail_receiver
    MainWindow._gmail_addon_background_receiver_installed = True
