from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.infrastructure.policy.supabase_team import TeamServiceError
from ai_pm_lab_privacy_gate.ui.team_page import TeamPage
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


_INSTALLED = False


def install_team_action_recovery() -> None:
    """Make Team actions recover from a stale local organization snapshot.

    A user can be promoted or attached to an organization in the control plane
    while PrivacyGate is already open. If the stale page still shows the
    individual workspace, attempting to create another workspace must not leave
    the user with a misleading error. Instead, sync the existing organization
    immediately after the current worker finishes.
    """

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    def run_team_action(
        self: TeamPage,
        operation,
        *,
        success_message: str = "",
        result_handler=None,
    ) -> None:
        if self._active_worker is not None:
            return

        self._team_refresh_after_worker = False

        def task():
            session = self.account_client.restore_session()
            if session is None:
                raise TeamServiceError("Sign in to your PrivacyGate account first.")
            return operation(session)

        worker = FunctionWorker(task)
        self._active_worker = worker
        self._set_busy(True)

        def ready(result: object) -> None:
            if isinstance(result, TeamState):
                self._apply_state(result)
                # Load manager-visible member/device details after the action
                # worker has fully released the page's busy state.
                self._team_refresh_after_worker = True
            elif result_handler is not None:
                result_handler(result)
            if success_message:
                QMessageBox.information(self, "PrivacyGate Team", success_message)

        def failed(message: str) -> None:
            normalized = message.lower()
            if "already belongs to an active privacygate organization" in normalized:
                self._team_refresh_after_worker = True
                try:
                    self.alert.setVisible(True)
                    self.alert.setText("Existing company workspace found. Syncing your account…")
                    self.alert.setStyleSheet(
                        "background:#EAF6F6;color:#0B7180;border:1px solid #B8E1E4;"
                        "border-radius:9px;padding:9px;font-weight:800;"
                    )
                except Exception:
                    pass
                return
            QMessageBox.warning(self, "Team action failed", message)

        def finished() -> None:
            self._active_worker = None
            self._set_busy(False)
            if getattr(self, "_team_refresh_after_worker", False):
                self._team_refresh_after_worker = False
                QTimer.singleShot(0, self.refresh)

        worker.signals.result.connect(ready)
        worker.signals.error.connect(failed)
        worker.signals.finished.connect(finished)
        self.thread_pool.start(worker)

    TeamPage._run_team_action = run_team_action
