from dataclasses import dataclass

from ai_pm_lab_privacy_gate.domain.company_policy import (
    CompanyPolicy,
    PolicyEngine,
    ProtectionDirective,
)
from ai_pm_lab_privacy_gate.domain.plans import PlanCode


@dataclass(frozen=True)
class StubFinding:
    finding_id: str
    entity_type: str


def policy() -> CompanyPolicy:
    return CompanyPolicy(
        organization_id="org-1",
        organization_name="ABC Realty",
        version=7,
        plan=PlanCode.BUSINESS,
        allowed_ai={"chatgpt": True, "claude": False, "other": False},
        allowed_connectors={"gmail": True, "notion": False},
        protection_rules={
            "US_SSN": ProtectionDirective.REQUIRED_PROTECT,
            "EMAIL_ADDRESS": ProtectionDirective.DEFAULT_PROTECT,
            "PERSON": ProtectionDirective.USER_CHOICE,
            "MONEY_AMOUNT": ProtectionDirective.ALLOW,
        },
    )


def test_required_findings_are_enforced_beyond_ui_selection():
    findings = (
        StubFinding("ssn", "US_SSN"),
        StubFinding("person", "PERSON"),
    )
    engine = PolicyEngine(policy())
    assert engine.enforce_selected_ids(findings, {"person"}) == {"person", "ssn"}
    assert not engine.can_user_unprotect("US_SSN")
    assert engine.can_user_unprotect("PERSON")


def test_company_ai_and_connector_allowlists_fail_closed_for_unknown_entries():
    engine = PolicyEngine(policy())
    assert engine.can_use_ai("chatgpt")
    assert not engine.can_use_ai("claude")
    assert not engine.can_use_ai("gemini")
    assert engine.can_use_connector("gmail")
    assert not engine.can_use_connector("notion")
    assert not engine.can_use_connector("dropbox")


def test_preflight_blocks_missing_or_residual_required_values():
    findings = (StubFinding("ssn", "US_SSN"), StubFinding("person", "PERSON"))
    engine = PolicyEngine(policy())

    missing = engine.evaluate(findings, {"person"}, destination="chatgpt")
    assert not missing.allowed
    assert missing.required_total == 1
    assert missing.required_protected == 0

    residual = engine.evaluate(
        findings,
        {"ssn", "person"},
        destination="chatgpt",
        residual_findings=(StubFinding("residual", "US_SSN"),),
    )
    assert not residual.allowed
    assert residual.required_residual == 1

    passed = engine.evaluate(
        findings,
        {"ssn"},
        destination="chatgpt",
        residual_findings=(StubFinding("visible", "PERSON"),),
    )
    assert passed.allowed


def test_unmanaged_basic_behavior_remains_permissive():
    engine = PolicyEngine()
    assert engine.can_use_ai("anything")
    assert engine.can_use_connector("anything")
    assert engine.directive_for("US_SSN") is ProtectionDirective.USER_CHOICE


def test_managed_cache_failure_blocks_handoff_instead_of_downgrading():
    engine = PolicyEngine.unavailable("Policy cache unavailable")
    assert not engine.can_use_ai("chatgpt")
    assert not engine.can_use_connector("gmail")
    evaluation = engine.evaluate((), (), destination="chatgpt")
    assert not evaluation.allowed
    assert "Policy cache unavailable" in evaluation.violations
