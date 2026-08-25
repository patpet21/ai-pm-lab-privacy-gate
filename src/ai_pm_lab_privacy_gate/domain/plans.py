from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlanCode(StrEnum):
    BASIC = "basic"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"

    @property
    def label(self) -> str:
        return {
            PlanCode.BASIC: "Basic",
            PlanCode.PRO: "Pro",
            PlanCode.BUSINESS: "Business",
            PlanCode.ENTERPRISE: "Enterprise",
        }[self]

    @property
    def is_team_plan(self) -> bool:
        return self in {PlanCode.BUSINESS, PlanCode.ENTERPRISE}


class Capability(StrEnum):
    LOCAL_PRIVACY_CORE = "local_privacy_core"
    INDIVIDUAL_PREMIUM = "individual_premium"
    TEAM_WORKSPACE = "team_workspace"
    COMPANY_POLICY = "company_policy"
    TEAM_MEMBERS = "team_members"
    TEAM_DEVICES = "team_devices"
    POLICY_ENFORCEMENT = "policy_enforcement"
    ENTERPRISE_IDENTITY = "enterprise_identity"
    ENTERPRISE_AUDIT = "enterprise_audit"


@dataclass(frozen=True, slots=True)
class PlanDefinition:
    code: PlanCode
    label: str
    description: str
    free: bool
    capabilities: frozenset[Capability]


_PLAN_CATALOG: dict[PlanCode, PlanDefinition] = {
    PlanCode.BASIC: PlanDefinition(
        code=PlanCode.BASIC,
        label="Basic",
        description="Free individual PrivacyGate with the local-first protection core.",
        free=True,
        capabilities=frozenset({Capability.LOCAL_PRIVACY_CORE}),
    ),
    PlanCode.PRO: PlanDefinition(
        code=PlanCode.PRO,
        label="Pro",
        description="Individual premium tier, reserved for advanced personal workflows.",
        free=False,
        capabilities=frozenset(
            {Capability.LOCAL_PRIVACY_CORE, Capability.INDIVIDUAL_PREMIUM}
        ),
    ),
    PlanCode.BUSINESS: PlanDefinition(
        code=PlanCode.BUSINESS,
        label="Business",
        description="Company workspace, seats, devices and centrally managed privacy policy.",
        free=False,
        capabilities=frozenset(
            {
                Capability.LOCAL_PRIVACY_CORE,
                Capability.INDIVIDUAL_PREMIUM,
                Capability.TEAM_WORKSPACE,
                Capability.COMPANY_POLICY,
                Capability.TEAM_MEMBERS,
                Capability.TEAM_DEVICES,
                Capability.POLICY_ENFORCEMENT,
            }
        ),
    ),
    PlanCode.ENTERPRISE: PlanDefinition(
        code=PlanCode.ENTERPRISE,
        label="Enterprise",
        description="Business controls plus enterprise identity and audit integrations.",
        free=False,
        capabilities=frozenset(Capability),
    ),
}


def normalize_plan(value: str | PlanCode | None) -> PlanCode:
    if isinstance(value, PlanCode):
        return value
    try:
        return PlanCode(str(value or "").strip().lower())
    except ValueError:
        return PlanCode.BASIC


def plan_definition(value: str | PlanCode | None) -> PlanDefinition:
    return _PLAN_CATALOG[normalize_plan(value)]


def supports(value: str | PlanCode | None, capability: Capability) -> bool:
    return capability in plan_definition(value).capabilities


def all_plans() -> tuple[PlanDefinition, ...]:
    return tuple(_PLAN_CATALOG[code] for code in PlanCode)
