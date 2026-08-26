from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.policy.workspace_context import WorkspaceDescriptor
from ai_pm_lab_privacy_gate.ui.team_page import TeamPage

_INSTALLED = False


def install_workspace_action_follow() -> None:
    """Make a newly joined/created organization the active workspace."""
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

    TeamPage._apply_state = apply_state
