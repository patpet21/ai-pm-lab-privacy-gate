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

    # Advanced individual productivity / local-first automation.
    BATCH_PROTECTION = "batch_protection"
    LOCAL_OCR = "local_ocr"
    WATCHED_FOLDERS = "watched_folders"
    ADVANCED_FILE_ROUTING = "advanced_file_routing"
    ADVANCED_AUTOMATION = "advanced_automation"
    MULTI_ACCOUNT = "multi_account"
    ACTIVITY_CENTER = "activity_center"
    PRIVACY_PROFILES = "privacy_profiles"
    PRIVACY_PREFLIGHT = "privacy_preflight"
    ENCRYPTED_BACKUP = "encrypted_backup"

    # Team / organization controls.
    TEAM_WORKSPACE = "team_workspace"
    COMPANY_POLICY = "company_policy"
    TEAM_MEMBERS = "team_members"
    TEAM_DEVICES = "team_devices"
    POLICY_ENFORCEMENT = "policy_enforcement"
    WORKSPACE_RULES = "workspace_rules"

    # Enterprise-only controls.
    ENTERPRISE_IDENTITY = "enterprise_identity"
    ENTERPRISE_AUDIT = "enterprise_audit"


@dataclass(frozen=True, slots=True)
class PlanDefinition:
    code: PlanCode
    label: str
    description: str
    free: bool
    capabilities: frozenset[Capability]


_PRO_CAPABILITIES = frozenset(
    {
        Capability.LOCAL_PRIVACY_CORE,
        Capability.INDIVIDUAL_PREMIUM,
        Capability.BATCH_PROTECTION,
        Capability.LOCAL_OCR,
        Capability.WATCHED_FOLDERS,
        Capability.ADVANCED_FILE_ROUTING,
        Capability.ADVANCED_AUTOMATION,
        Capability.MULTI_ACCOUNT,
        Capability.ACTIVITY_CENTER,
        Capability.PRIVACY_PROFILES,
        Capability.PRIVACY_PREFLIGHT,
        Capability.ENCRYPTED_BACKUP,
    }
)

_BUSINESS_CAPABILITIES = frozenset(
    set(_PRO_CAPABILITIES)
    | {
        Capability.TEAM_WORKSPACE,
        Capability.COMPANY_POLICY,
        Capability.TEAM_MEMBERS,
        Capability.TEAM_DEVICES,
        Capability.POLICY_ENFORCEMENT,
        Capability.WORKSPACE_RULES,
    }
)

_PLAN_CATALOG: dict[PlanCode, PlanDefinition] = {
    PlanCode.BASIC: PlanDefinition(
        code=PlanCode.BASIC,
        label="Basic",
        description="Free individual PrivacyGate with the complete local-first protection core.",
        free=True,
        capabilities=frozenset({Capability.LOCAL_PRIVACY_CORE}),
    ),
    PlanCode.PRO: PlanDefinition(
        code=PlanCode.PRO,
        label="Pro",
        description="Advanced individual PrivacyGate with local automation, OCR, batch protection and productivity controls.",
        free=False,
        capabilities=_PRO_CAPABILITIES,
    ),
    PlanCode.BUSINESS: PlanDefinition(
        code=PlanCode.BUSINESS,
        label="Business",
        description="Pro controls plus company workspaces, seats, devices, approved destinations and centrally managed privacy policy.",
        free=False,
        capabilities=_BUSINESS_CAPABILITIES,
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
    raw = str(value or "").strip().lower()
    # Backward compatibility with the existing Supabase entitlement schema,
    # which historically stored the free tier as "free".
    if raw == "free":
        raw = PlanCode.BASIC.value
    try:
        return PlanCode(raw)
    except ValueError:
        return PlanCode.BASIC


def plan_definition(value: str | PlanCode | None) -> PlanDefinition:
    return _PLAN_CATALOG[normalize_plan(value)]


def supports(value: str | PlanCode | None, capability: Capability) -> bool:
    return capability in plan_definition(value).capabilities


def require_capability(value: str | PlanCode | None, capability: Capability) -> None:
    """Backend/service guard for premium functionality.

    UI gating is intentionally not sufficient: every advanced service calls this
    before doing work so direct invocation cannot bypass the current entitlement.
    """
    if supports(value, capability):
        return
    plan = normalize_plan(value)
    raise PermissionError(
        f"{capability.value} is not available on PrivacyGate {plan.label}."
    )


def minimum_plan_for(capability: Capability) -> PlanCode:
    """Return the first commercial tier that exposes a capability."""
    for code in (PlanCode.BASIC, PlanCode.PRO, PlanCode.BUSINESS, PlanCode.ENTERPRISE):
        if capability in _PLAN_CATALOG[code].capabilities:
            return code
    return PlanCode.ENTERPRISE


def all_plans() -> tuple[PlanDefinition, ...]:
    return tuple(_PLAN_CATALOG[code] for code in PlanCode)
