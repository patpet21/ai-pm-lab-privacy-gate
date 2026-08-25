import json

import pytest

from ai_pm_lab_privacy_gate.domain.company_policy import (
    CompanyPolicy,
    ProtectionDirective,
)
from ai_pm_lab_privacy_gate.domain.plans import PlanCode
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import (
    MANAGED_MARKER_SECRET,
    STATE_SECRET,
    PolicyCacheError,
    SecureTeamStateStore,
    TeamState,
)
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore


def managed_state() -> TeamState:
    policy = CompanyPolicy(
        organization_id="org-1",
        organization_name="ABC Realty",
        version=3,
        plan=PlanCode.BUSINESS,
        allowed_ai={"chatgpt": True},
        allowed_connectors={"gmail": True},
        protection_rules={"US_SSN": ProtectionDirective.REQUIRED_PROTECT},
    )
    return TeamState(
        plan=PlanCode.BUSINESS,
        organization_id="org-1",
        organization_name="ABC Realty",
        role="member",
        membership_status="active",
        seat_limit=5,
        policy=policy,
        synced_at="2026-08-25T22:00:00+00:00",
    )


def test_team_state_round_trip_uses_secure_secret_store(tmp_path):
    secrets = MemorySecretStore()
    store = SecureTeamStateStore(tmp_path, secrets)
    state = managed_state()

    store.save(state)

    assert secrets.get(STATE_SECRET)
    assert secrets.get(MANAGED_MARKER_SECRET) == "1"
    restored = store.load()
    assert restored.plan is PlanCode.BUSINESS
    assert restored.policy is not None
    assert restored.policy.version == 3


def test_corrupt_managed_cache_does_not_silently_become_basic(tmp_path):
    secrets = MemorySecretStore()
    store = SecureTeamStateStore(tmp_path, secrets)
    secrets.set(MANAGED_MARKER_SECRET, "1")
    secrets.set(STATE_SECRET, "{broken json")

    with pytest.raises(PolicyCacheError):
        store.load()


def test_missing_state_with_managed_marker_fails_closed(tmp_path):
    secrets = MemorySecretStore()
    store = SecureTeamStateStore(tmp_path, secrets)
    secrets.set(MANAGED_MARKER_SECRET, "1")

    with pytest.raises(PolicyCacheError):
        store.load()


def test_basic_state_clears_managed_marker(tmp_path):
    secrets = MemorySecretStore()
    store = SecureTeamStateStore(tmp_path, secrets)
    store.save(managed_state())
    store.save(TeamState(plan=PlanCode.BASIC))

    assert secrets.get(MANAGED_MARKER_SECRET) is None
    assert json.loads(secrets.get(STATE_SECRET))["plan"] == "basic"
