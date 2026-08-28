from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_pm_lab_privacy_gate.domain.company_policy import PolicyEngine
from ai_pm_lab_privacy_gate.domain.plans import PlanCode, normalize_plan
from ai_pm_lab_privacy_gate.infrastructure.storage.document_workspace_metadata import (
    DocumentWorkspaceMetadata,
    DocumentWorkspaceMetadataRepository,
)


@dataclass(frozen=True, slots=True)
class LibraryWorkspaceContext:
    key: str
    name: str
    personal: bool
    plan: PlanCode
    role: str = ""
    organization_id: str = ""
    policy: Any | None = None

    @property
    def plan_label(self) -> str:
        return self.plan.label

    @property
    def managed(self) -> bool:
        return not self.personal


def _workspace_store(page):
    try:
        main_window = page.window()
    except Exception:
        return None
    team_page = getattr(main_window, "team_page", None)
    return getattr(team_page, "_privacygate_workspace_store", None) if team_page else None


def _workspace_context(page):
    try:
        main_window = page.window()
    except Exception:
        return None

    controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    if controller is not None:
        try:
            context = controller._workspace_context()
            if context is not None:
                return context
        except Exception:
            pass

    store = _workspace_store(page)
    if store is not None:
        try:
            return store.load()
        except Exception:
            pass
    return None


def resolve_library_workspace(page) -> LibraryWorkspaceContext:
    context = _workspace_context(page)
    if context is None:
        return LibraryWorkspaceContext(
            key="personal",
            name="Personal",
            personal=True,
            plan=PlanCode.BASIC,
        )

    descriptor = context.workspaces.get(context.active_key)
    if descriptor is None:
        return LibraryWorkspaceContext(
            key=str(context.active_key or "personal"),
            name="Personal",
            personal=True,
            plan=PlanCode.BASIC,
        )

    personal = bool(getattr(descriptor, "personal", False))
    key = str(context.active_key or ("personal" if personal else ""))
    name = "Personal" if personal else str(getattr(descriptor, "name", "") or "Organization")
    plan = normalize_plan(getattr(descriptor, "plan", None))
    role = str(getattr(descriptor, "role", "") or "")
    organization_id = str(getattr(descriptor, "organization_id", "") or "")
    policy = None

    if not personal:
        try:
            main_window = page.window()
            team_page = getattr(main_window, "team_page", None)
            state = getattr(team_page, "state", None) if team_page is not None else None
            if (
                state is not None
                and str(getattr(state, "organization_id", "") or "") == organization_id
            ):
                policy = getattr(state, "policy", None)
            if policy is None:
                store = _workspace_store(page)
                cached = store.cached_state(key) if store is not None else None
                policy = getattr(cached, "policy", None) if cached is not None else None
        except Exception:
            policy = None

    return LibraryWorkspaceContext(
        key=key,
        name=name,
        personal=personal,
        plan=plan,
        role=role,
        organization_id=organization_id,
        policy=policy,
    )


def load_document_workspace_map(page, documents) -> dict[str, DocumentWorkspaceMetadata]:
    ids = [str(document.document_id) for document in documents]
    try:
        repository = DocumentWorkspaceMetadataRepository(page.library.db_path)
        return repository.list_for_documents(ids)
    except Exception:
        return {}


def document_in_workspace(
    context: LibraryWorkspaceContext,
    metadata: DocumentWorkspaceMetadata | None,
) -> bool:
    # Historical documents deliberately remain unassigned. They are visible only
    # from Personal as "Legacy local" and are never auto-attached to an organization.
    if context.personal:
        return metadata is None or bool(metadata.personal)
    return bool(
        metadata is not None
        and not metadata.personal
        and metadata.workspace_key == context.key
    )


def document_workspace_label(
    context: LibraryWorkspaceContext,
    metadata: DocumentWorkspaceMetadata | None,
) -> str:
    if metadata is None:
        return "Legacy local"
    if metadata.personal:
        return "Personal"
    return metadata.workspace_name or context.name or "Organization"


def scoped_documents(page, documents):
    context = resolve_library_workspace(page)
    metadata_map = load_document_workspace_map(page, documents)
    scoped = tuple(
        document
        for document in documents
        if document_in_workspace(context, metadata_map.get(document.document_id))
    )
    return context, metadata_map, scoped


def ai_destination_allowed(
    context: LibraryWorkspaceContext,
    destination_key: str,
) -> bool | None:
    if context.personal:
        return True
    if context.policy is None:
        return None
    # Reuse the same CompanyPolicy semantics as managed Protect, including the
    # existing fallback from a specific destination to the policy's "other" rule.
    return PolicyEngine(context.policy).can_use_ai(destination_key)


def policy_status_text(context: LibraryWorkspaceContext) -> str:
    if context.personal:
        return "Personal policy"
    policy = context.policy
    if policy is None:
        return "Policy unavailable"
    version = getattr(policy, "version", None)
    if version not in (None, ""):
        return f"Policy v{version} active"
    return "Organization policy active"
