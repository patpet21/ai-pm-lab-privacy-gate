from ai_pm_lab_privacy_gate.domain.plans import PlanCode
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.ui.team_page import _account_entitlement


def test_product_owner_receives_enterprise_entitlement():
    state = _account_entitlement(TeamState(plan=PlanCode.BASIC), "PETER@propertydex.xyz")

    assert state.plan is PlanCode.ENTERPRISE
    assert state.entitlement_status == "active"


def test_customer_entitlement_is_not_overridden():
    state = _account_entitlement(TeamState(plan=PlanCode.PRO), "customer@example.com")

    assert state.plan is PlanCode.PRO
