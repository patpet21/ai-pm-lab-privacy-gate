from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.infrastructure.policy.workspace_context import WorkspaceDescriptor
from ai_pm_lab_privacy_gate.ui.team_page import TeamPage
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker

_INSTALLED = False


def install_workspace_action_follow() -> None:
    """Keep workspace actions and workspace switching deterministic and fail-safe."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_apply_state = TeamPage._apply_state

    def apply_state(self: TeamPage, state, members=None, devices=None) -> None:
        previous_apply_state(self, state, members, devices)
        if not getattr(state, "organization_id", ""):
            return
        store = getattr(self, "_privacygate_workspace_store", None)
        if store is None:
            return
        context = store.load()
        key = f"org:{state.organization_id}"
        context.workspaces[key] = WorkspaceDescriptor(
            key=key,
            name=state.organization_name or "Organization",
            plan=state.plan,
            role=state.role or "member",
            organization_id=state.organization_id,
            personal=False,
        )
        context.active_key = key
        context.workspace_states[key] = state.to_dict()
        store.save(context)

    def switch_workspace(self: TeamPage, _index: int) -> None:
        store = self._privacygate_workspace_store
        context = store.load()
        key = str(self.workspace_selector.currentData() or "")
        if not key or key == context.active_key:
            return
        descriptor = context.workspaces.get(key)
        if descriptor is None:
            return

        cached = store.cached_state(key)
        if descriptor.personal:
            state = cached or TeamState(plan=descriptor.plan)
            store.set_active(key)
            store.cache_state(key, state)
            self.state_store.save(state)
            self.state = state
            self.policy_changed.emit(None)
            self.state_changed.emit(state)
            self._render()
            self.refresh_silent()
            return

        if cached is not None and cached.managed:
            store.set_active(key)
            self.state_store.save(cached)
            self.state = cached
            self.policy_changed.emit(cached.policy)
            self.state_changed.emit(cached)
            self._render()
            self.refresh_silent()
            return

        # Never briefly fall back to Personal rules while a managed workspace has
        # no verified cached policy. Keep the previous workspace active until the
        # target organization policy is fetched successfully.
        previous_key = context.active_key
        previous_index = self.workspace_selector.findData(previous_key)
        self.workspace_selector.blockSignals(True)
        self.workspace_selector.setCurrentIndex(max(0, previous_index))
        self.workspace_selector.blockSignals(False)
        self.workspace_context_note.setText(
            f"Syncing {descriptor.name} policy before activation…"
        )
        if self._active_worker is not None:
            return

        def task():
            session = self.account_client.restore_session()
            if session is None:
                raise RuntimeError("Sign in to sync the selected workspace.")
            return self.team_client.fetch_workspace_state(
                session, descriptor.organization_id
            )

        worker = FunctionWorker(task)
        self._active_worker = worker
        self._set_busy(True)

        def ready(state):
            store.set_active(key)
            store.cache_state(key, state)
            self._apply_state(state)

        def failed(message: str):
            QMessageBox.warning(self, "Workspace policy unavailable", message)

        def finished():
            self._active_worker = None
            self._set_busy(False)
            self._render()
            self.refresh_silent()

        worker.signals.result.connect(ready)
        worker.signals.error.connect(failed)
        worker.signals.finished.connect(finished)
        self.thread_pool.start(worker)

    TeamPage._apply_state = apply_state
    TeamPage._privacygate_workspace_selected = switch_workspace
