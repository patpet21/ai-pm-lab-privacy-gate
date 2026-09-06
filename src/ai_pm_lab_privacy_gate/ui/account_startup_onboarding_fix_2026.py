from __future__ import annotations

from PySide6.QtCore import QThreadPool, QTimer

from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


ONBOARDING_VERSION = 2


def install_account_startup_onboarding_fix_2026(main_window, controller) -> None:
    """Ensure first-run Account onboarding is decided at app startup, not MCP entry.

    The original Account UX treated the mere presence of a locally stored user id as
    proof of a valid session. A stale refresh token could therefore suppress startup
    onboarding, only for Remote MCP to discover the expired session later and show
    the Account dialog there. This fix validates a remembered session asynchronously
    after the main window is ready and forces one corrected onboarding decision for
    version 2 installations.
    """
    if controller is None or bool(getattr(controller, "_privacygate_startup_onboarding_fix_2026", False)):
        return

    controller._privacygate_startup_onboarding_fix_2026 = True
    controller.ONBOARDING_VERSION = ONBOARDING_VERSION

    # Disable the legacy singleShot callback already queued by the base Account UX.
    # The corrected flow below owns startup onboarding from this point forward.
    controller._onboarding_started = True
    controller._startup_fix_started = False
    controller._startup_validation_worker = None
    controller._startup_thread_pool = QThreadPool.globalInstance()

    def show_startup_prompt() -> None:
        if bool(getattr(controller, "_startup_fix_started", False)):
            return
        if controller._read_onboarding_state():
            return
        controller._startup_fix_started = True
        controller.open_account(context="startup", initial_mode="choose")

    def validation_result(session) -> None:
        if session is None:
            controller.refresh_surfaces()
            show_startup_prompt()
            return
        controller._session_accepted(session)

    def validation_error(_message: str) -> None:
        # A temporary network failure is not evidence that the account is invalid.
        # Keep local features available and retry the validation on a future launch.
        controller.refresh_surfaces()

    def validation_finished() -> None:
        controller._startup_validation_worker = None

    def validate_remembered_session() -> None:
        if controller._startup_validation_worker is not None:
            return

        worker = FunctionWorker(controller.account_client.restore_session)
        controller._startup_validation_worker = worker
        worker.signals.result.connect(validation_result)
        worker.signals.error.connect(validation_error)
        worker.signals.finished.connect(validation_finished)
        controller._startup_thread_pool.start(worker)

    def maybe_start() -> None:
        if bool(getattr(controller, "_startup_fix_started", False)):
            return
        if controller._read_onboarding_state():
            return
        if not main_window.isVisible() or not bool(
            getattr(main_window, "_privacygate_startup_ready", False)
        ):
            QTimer.singleShot(120, maybe_start)
            return

        # No remembered account: onboarding belongs here, immediately after the
        # first real app paint, before the user has to discover it through MCP.
        if not controller.account_client.current_user_id:
            show_startup_prompt()
            return

        # A remembered account may be stale. Validate it off the UI thread; an
        # invalid refresh token clears the local session and then shows onboarding.
        validate_remembered_session()

    QTimer.singleShot(0, maybe_start)
