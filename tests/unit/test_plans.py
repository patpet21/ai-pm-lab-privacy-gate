from ai_pm_lab_privacy_gate.domain.plans import (
    Capability,
    PlanCode,
    all_plans,
    normalize_plan,
    supports,
)


def test_plan_catalog_has_exact_four_canonical_tiers():
    assert [plan.code for plan in all_plans()] == [
        PlanCode.BASIC,
        PlanCode.PRO,
        PlanCode.BUSINESS,
        PlanCode.ENTERPRISE,
    ]
    assert PlanCode.BASIC.label == "Basic"
    assert normalize_plan("unknown") is PlanCode.BASIC
    assert normalize_plan("free") is PlanCode.BASIC


def test_basic_is_free_core_and_team_starts_at_business():
    basic = all_plans()[0]
    assert basic.free is True
    assert supports(PlanCode.BASIC, Capability.LOCAL_PRIVACY_CORE)
    assert not supports(PlanCode.BASIC, Capability.COMPANY_POLICY)
    assert not supports(PlanCode.PRO, Capability.COMPANY_POLICY)
    assert supports(PlanCode.BUSINESS, Capability.COMPANY_POLICY)
    assert supports(PlanCode.ENTERPRISE, Capability.COMPANY_POLICY)
    assert supports(PlanCode.ENTERPRISE, Capability.ENTERPRISE_IDENTITY)
