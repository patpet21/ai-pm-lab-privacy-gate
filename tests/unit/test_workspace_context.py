from __future__ import annotations

from ai_pm_lab_privacy_gate.domain.company_policy import CompanyPolicy, ProtectionDirective
from ai_pm_lab_privacy_gate.domain.plans import PlanCode
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.infrastructure.policy.workspace_context import WorkspaceContextStore, WorkspaceDescriptor
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore


def _store(tmp_path):
    return WorkspaceContextStore(tmp_path, MemorySecretStore())


def test_personal_workspace_always_exists(tmp_path):
    store = _store(tmp_path)
    context = store.load()
    assert context.active_key == "personal"
    assert context.workspaces["personal"].personal is True


def test_one_connector_account_can_bind_to_multiple_workspaces(tmp_path):
    store = _store(tmp_path)
    abc = WorkspaceDescriptor(key="org:abc", name="ABC Realty", plan=PlanCode.BUSINESS, role="member", organization_id="abc")
    xyz = WorkspaceDescriptor(key="org:xyz", name="XYZ Consulting", plan=PlanCode.ENTERPRISE, role="member", organization_id="xyz")
    store.cache_workspaces((abc, xyz), personal_plan=PlanCode.PRO)
    store.bind_account("gmail", "peter@gmail.com", ("personal", "org:abc", "org:xyz"))
    assert store.is_account_available("gmail", "peter@gmail.com", "personal")
    assert store.is_account_available("gmail", "peter@gmail.com", "org:abc")
    assert store.is_account_available("gmail", "peter@gmail.com", "org:xyz")


def test_unbound_legacy_connector_remains_available(tmp_path):
    store = _store(tmp_path)
    assert store.is_account_available("google_drive", "legacy-account", "personal")


def test_workspace_policy_state_is_cached_separately(tmp_path):
    store = _store(tmp_path)
    abc = WorkspaceDescriptor(key="org:abc", name="ABC Realty", plan=PlanCode.BUSINESS, role="member", organization_id="abc")
    store.cache_workspaces((abc,))
    policy = CompanyPolicy(
        organization_id="abc",
        organization_name="ABC Realty",
        version=7,
        plan=PlanCode.BUSINESS,
        allowed_ai={"chatgpt": True},
        protection_rules={"US_SSN": ProtectionDirective.REQUIRED_PROTECT},
    )
    state = TeamState(plan=PlanCode.BUSINESS, organization_id="abc", organization_name="ABC Realty", role="member", membership_status="active", policy=policy)
    store.cache_state("org:abc", state)
    cached = store.cached_state("org:abc")
    assert cached is not None
    assert cached.policy is not None
    assert cached.policy.version == 7
    assert cached.policy.protection_rules["US_SSN"] is ProtectionDirective.REQUIRED_PROTECT
