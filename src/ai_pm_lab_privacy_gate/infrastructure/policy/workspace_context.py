from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Mapping

from ai_pm_lab_privacy_gate.domain.plans import PlanCode, normalize_plan
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import (
    SecretStore,
    platform_secret_store,
)

WORKSPACE_CONTEXT_SECRET = "workspace.context.v1"


@dataclass(frozen=True, slots=True)
class WorkspaceDescriptor:
    key: str
    name: str
    plan: PlanCode
    role: str = ""
    organization_id: str = ""
    personal: bool = False

    @classmethod
    def personal_workspace(cls, plan: PlanCode = PlanCode.BASIC) -> "WorkspaceDescriptor":
        return cls(
            key="personal",
            name="Personal",
            plan=plan,
            role="you",
            personal=True,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "WorkspaceDescriptor":
        return cls(
            key=str(payload.get("key") or ""),
            name=str(payload.get("name") or "Workspace"),
            plan=normalize_plan(str(payload.get("plan") or PlanCode.BASIC.value)),
            role=str(payload.get("role") or ""),
            organization_id=str(payload.get("organization_id") or ""),
            personal=bool(payload.get("personal", False)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "name": self.name,
            "plan": self.plan.value,
            "role": self.role,
            "organization_id": self.organization_id,
            "personal": self.personal,
        }


@dataclass(slots=True)
class WorkspaceContext:
    active_key: str = "personal"
    # Older installs did not record whether Personal was deliberately selected.
    # This flag lets us migrate those installs to their single managed workspace
    # without taking away the user's ability to choose Personal afterwards.
    active_selection_explicit: bool = False
    workspaces: dict[str, WorkspaceDescriptor] = field(default_factory=dict)
    connector_bindings: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    workspace_states: dict[str, dict[str, object]] = field(default_factory=dict)

    def ensure_personal(self, plan: PlanCode = PlanCode.BASIC) -> None:
        self.workspaces["personal"] = WorkspaceDescriptor.personal_workspace(plan)

    def to_dict(self) -> dict[str, object]:
        return {
            "active_key": self.active_key,
            "active_selection_explicit": self.active_selection_explicit,
            "workspaces": {key: value.to_dict() for key, value in self.workspaces.items()},
            "connector_bindings": self.connector_bindings,
            "workspace_states": self.workspace_states,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "WorkspaceContext":
        raw_workspaces = payload.get("workspaces")
        workspaces: dict[str, WorkspaceDescriptor] = {}
        if isinstance(raw_workspaces, Mapping):
            for key, value in raw_workspaces.items():
                if isinstance(value, Mapping):
                    descriptor = WorkspaceDescriptor.from_dict(value)
                    if descriptor.key:
                        workspaces[str(key)] = descriptor

        bindings: dict[str, dict[str, list[str]]] = {}
        raw_bindings = payload.get("connector_bindings")
        if isinstance(raw_bindings, Mapping):
            for provider, accounts in raw_bindings.items():
                if not isinstance(accounts, Mapping):
                    continue
                provider_bindings: dict[str, list[str]] = {}
                for account_id, workspace_keys in accounts.items():
                    if isinstance(workspace_keys, (list, tuple)):
                        provider_bindings[str(account_id)] = [
                            str(item) for item in workspace_keys if str(item)
                        ]
                bindings[str(provider)] = provider_bindings

        raw_states = payload.get("workspace_states")
        states: dict[str, dict[str, object]] = {}
        if isinstance(raw_states, Mapping):
            for key, value in raw_states.items():
                if isinstance(value, Mapping):
                    states[str(key)] = dict(value)

        context = cls(
            active_key=str(payload.get("active_key") or "personal"),
            active_selection_explicit=bool(payload.get("active_selection_explicit", False)),
            workspaces=workspaces,
            connector_bindings=bindings,
            workspace_states=states,
        )
        # Preserve the plan stored for Personal. A bare ensure_personal() here used
        # to overwrite it with Basic every time the secure context was loaded.
        personal = context.workspaces.get("personal")
        context.ensure_personal(personal.plan if personal is not None else PlanCode.BASIC)
        if context.active_key not in context.workspaces:
            context.active_key = "personal"
            context.active_selection_explicit = False
        return context


class WorkspaceContextStore:
    """OS-protected local workspace selector and connector bindings.

    Connector OAuth tokens remain in the existing connector vault. This store only
    records which local account may be used in which PrivacyGate workspace.
    """

    def __init__(self, data_dir, secret_store: SecretStore | None = None) -> None:
        self.data_dir = data_dir
        self.secrets = secret_store or platform_secret_store(data_dir)

    def load(self) -> WorkspaceContext:
        raw = self.secrets.get(WORKSPACE_CONTEXT_SECRET)
        if not raw:
            context = WorkspaceContext()
            context.ensure_personal()
            return context
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, Mapping):
            payload = {}
        return WorkspaceContext.from_dict(payload)

    def save(self, context: WorkspaceContext) -> None:
        self.secrets.set(
            WORKSPACE_CONTEXT_SECRET,
            json.dumps(context.to_dict(), separators=(",", ":"), sort_keys=True),
        )

    def cache_workspaces(
        self,
        descriptors: list[WorkspaceDescriptor] | tuple[WorkspaceDescriptor, ...],
        *,
        personal_plan: PlanCode = PlanCode.BASIC,
    ) -> WorkspaceContext:
        context = self.load()
        context.ensure_personal(personal_plan)
        live_keys = {"personal"}
        managed_keys: list[str] = []
        for descriptor in descriptors:
            if not descriptor.key:
                continue
            context.workspaces[descriptor.key] = descriptor
            live_keys.add(descriptor.key)
            if not descriptor.personal:
                managed_keys.append(descriptor.key)
        for key in tuple(context.workspaces):
            if key not in live_keys:
                context.workspaces.pop(key, None)
        if context.active_key not in context.workspaces:
            context.active_key = "personal"
            context.active_selection_explicit = False

        # Migration/default rule: an existing company user with exactly one live
        # organization opens in that managed workspace. Personal remains available
        # in the switcher. Once the user explicitly switches workspace, we respect
        # that choice on subsequent launches.
        if (
            not context.active_selection_explicit
            and context.active_key == "personal"
            and len(managed_keys) == 1
        ):
            context.active_key = managed_keys[0]

        self.save(context)
        return context

    def set_active(self, workspace_key: str) -> WorkspaceContext:
        context = self.load()
        if workspace_key not in context.workspaces:
            raise KeyError(f"Unknown workspace: {workspace_key}")
        context.active_key = workspace_key
        context.active_selection_explicit = True
        self.save(context)
        return context

    def bind_account(
        self,
        provider: str,
        account_id: str,
        workspace_keys: list[str] | tuple[str, ...],
    ) -> WorkspaceContext:
        context = self.load()
        valid = [
            key
            for key in dict.fromkeys(str(item) for item in workspace_keys)
            if key in context.workspaces
        ]
        context.connector_bindings.setdefault(provider, {})[account_id] = valid
        self.save(context)
        return context

    def cache_state(self, workspace_key: str, state: TeamState) -> WorkspaceContext:
        context = self.load()
        context.workspace_states[workspace_key] = state.to_dict()
        self.save(context)
        return context

    def cached_state(self, workspace_key: str) -> TeamState | None:
        context = self.load()
        raw = context.workspace_states.get(workspace_key)
        if not isinstance(raw, Mapping):
            return None
        try:
            return TeamState.from_dict(raw)
        except Exception:
            return None

    def bindings_for(self, provider: str, account_id: str) -> tuple[str, ...]:
        context = self.load()
        return tuple(context.connector_bindings.get(provider, {}).get(account_id, ()))

    def is_account_available(
        self,
        provider: str,
        account_id: str,
        workspace_key: str,
    ) -> bool:
        context = self.load()
        explicit = context.connector_bindings.get(provider, {}).get(account_id)
        if explicit is None:
            # Backward-compatible default: connected accounts remain usable until
            # the user explicitly restricts bindings.
            return True
        return workspace_key in explicit
