from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable, Mapping

from ai_pm_lab_privacy_gate.domain.plans import PlanCode, normalize_plan


class ProtectionDirective(StrEnum):
    REQUIRED_PROTECT = "required_protect"
    DEFAULT_PROTECT = "default_protect"
    USER_CHOICE = "user_choice"
    ALLOW = "allow"


def _normalize_bool_map(value: object) -> dict[str, bool]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key).strip().lower(): bool(enabled)
        for key, enabled in value.items()
        if str(key).strip()
    }


def _normalize_rules(value: object) -> dict[str, ProtectionDirective]:
    if not isinstance(value, Mapping):
        return {}
    rules: dict[str, ProtectionDirective] = {}
    for entity_type, raw_directive in value.items():
        key = str(entity_type).strip().upper()
        if not key:
            continue
        try:
            rules[key] = ProtectionDirective(str(raw_directive).strip().lower())
        except ValueError:
            continue
    return rules


@dataclass(frozen=True, slots=True)
class CompanyPolicy:
    organization_id: str
    organization_name: str
    version: int
    plan: PlanCode
    allowed_ai: dict[str, bool] = field(default_factory=dict)
    allowed_connectors: dict[str, bool] = field(default_factory=dict)
    protection_rules: dict[str, ProtectionDirective] = field(default_factory=dict)
    policy_name: str = "Company Privacy Policy"
    issued_at: str = ""

    def __post_init__(self) -> None:
        if self.plan not in {PlanCode.BUSINESS, PlanCode.ENTERPRISE}:
            raise ValueError("Company policies require a Business or Enterprise plan.")
        if not self.organization_id.strip():
            raise ValueError("Company policy requires an organization ID.")
        if self.version < 1:
            raise ValueError("Company policy version must be at least 1.")

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "CompanyPolicy":
        return cls(
            organization_id=str(payload.get("organization_id") or "").strip(),
            organization_name=str(payload.get("organization_name") or "Organization").strip(),
            version=int(payload.get("version") or 1),
            plan=normalize_plan(str(payload.get("plan") or PlanCode.BUSINESS.value)),
            allowed_ai=_normalize_bool_map(payload.get("allowed_ai")),
            allowed_connectors=_normalize_bool_map(payload.get("allowed_connectors")),
            protection_rules=_normalize_rules(payload.get("protection_rules")),
            policy_name=str(payload.get("policy_name") or "Company Privacy Policy").strip(),
            issued_at=str(payload.get("issued_at") or "").strip(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "organization_id": self.organization_id,
            "organization_name": self.organization_name,
            "version": self.version,
            "plan": self.plan.value,
            "allowed_ai": dict(self.allowed_ai),
            "allowed_connectors": dict(self.allowed_connectors),
            "protection_rules": {
                entity_type: directive.value
                for entity_type, directive in self.protection_rules.items()
            },
            "policy_name": self.policy_name,
            "issued_at": self.issued_at,
        }


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    allowed: bool
    destination_allowed: bool
    required_total: int
    required_protected: int
    required_residual: int
    violations: tuple[str, ...] = ()


class PolicyEngine:
    """Single source of truth for company privacy decisions.

    Basic/Pro users have no active company policy and keep today's behavior.
    Managed Business/Enterprise devices fail closed for AI/app handoff when the
    cached company policy is unavailable instead of silently falling back to Basic.
    """

    def __init__(
        self,
        policy: CompanyPolicy | None = None,
        *,
        unavailable_reason: str = "",
        managed_required: bool = False,
    ) -> None:
        self.policy = policy
        self.unavailable_reason = unavailable_reason.strip()
        self.managed_required = bool(managed_required)

    @property
    def active(self) -> bool:
        return self.policy is not None

    @property
    def organization_name(self) -> str:
        return self.policy.organization_name if self.policy else ""

    @classmethod
    def unavailable(cls, reason: str) -> "PolicyEngine":
        return cls(None, unavailable_reason=reason, managed_required=True)

    def directive_for(self, entity_type: str) -> ProtectionDirective:
        if not self.policy:
            return ProtectionDirective.USER_CHOICE
        return self.policy.protection_rules.get(
            str(entity_type).strip().upper(),
            ProtectionDirective.USER_CHOICE,
        )

    def must_protect(self, entity_type: str) -> bool:
        return self.directive_for(entity_type) is ProtectionDirective.REQUIRED_PROTECT

    def should_default_protect(self, entity_type: str) -> bool:
        return self.directive_for(entity_type) in {
            ProtectionDirective.REQUIRED_PROTECT,
            ProtectionDirective.DEFAULT_PROTECT,
        }

    def can_user_unprotect(self, entity_type: str) -> bool:
        return not self.must_protect(entity_type)

    def can_use_ai(self, destination: str) -> bool:
        if self.managed_required and not self.policy:
            return False
        if not self.policy:
            return True
        key = str(destination or "other").strip().lower()
        if key in self.policy.allowed_ai:
            return bool(self.policy.allowed_ai[key])
        return bool(self.policy.allowed_ai.get("other", False))

    def can_use_connector(self, connector: str) -> bool:
        if self.managed_required and not self.policy:
            return False
        if not self.policy:
            return True
        key = str(connector).strip().lower()
        return bool(self.policy.allowed_connectors.get(key, False))

    @staticmethod
    def _finding_id(finding: object) -> str:
        return str(getattr(finding, "finding_id", "") or "")

    @staticmethod
    def _entity_type(finding: object) -> str:
        return str(getattr(finding, "entity_type", "") or "").upper()

    def required_finding_ids(self, findings: Iterable[object]) -> frozenset[str]:
        if not self.policy:
            return frozenset()
        return frozenset(
            self._finding_id(finding)
            for finding in findings
            if self.must_protect(self._entity_type(finding)) and self._finding_id(finding)
        )

    def enforce_selected_ids(
        self,
        findings: Iterable[object],
        selected_ids: Iterable[str],
    ) -> frozenset[str]:
        selected = {str(item) for item in selected_ids if str(item)}
        selected.update(self.required_finding_ids(findings))
        return frozenset(selected)

    def evaluate(
        self,
        findings: Iterable[object],
        selected_ids: Iterable[str],
        *,
        destination: str,
        residual_findings: Iterable[object] = (),
    ) -> PolicyEvaluation:
        findings_tuple = tuple(findings)
        selected = {str(item) for item in selected_ids if str(item)}
        required = self.required_finding_ids(findings_tuple)
        protected = len(required & selected)
        residual_required = sum(
            1
            for finding in residual_findings
            if self.must_protect(self._entity_type(finding))
        )
        destination_allowed = self.can_use_ai(destination)
        violations: list[str] = []

        if self.managed_required and not self.policy:
            violations.append(
                self.unavailable_reason
                or "The managed company policy is unavailable on this device."
            )
        if not destination_allowed:
            label = destination or "AI destination"
            violations.append(f"{label} is blocked by company policy.")
        missing = len(required) - protected
        if missing > 0:
            violations.append(
                f"{missing} company-required sensitive item(s) are not protected."
            )
        if residual_required > 0:
            violations.append(
                f"{residual_required} company-required sensitive item(s) remain after the second scan."
            )

        return PolicyEvaluation(
            allowed=not violations,
            destination_allowed=destination_allowed,
            required_total=len(required),
            required_protected=protected,
            required_residual=residual_required,
            violations=tuple(violations),
        )
