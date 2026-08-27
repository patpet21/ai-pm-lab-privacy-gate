from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable


class PrivacyRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def label(self) -> str:
        return self.value.upper()


@dataclass(frozen=True, slots=True)
class PrivacyRiskAssessment:
    level: PrivacyRiskLevel
    score: int
    reason: str
    hard_block: bool = False


@dataclass(frozen=True, slots=True)
class EnforcementDecision:
    allowed: bool
    reason: str
    source: str = "privacygate"


def evaluate_privacy_risk(
    *,
    detected: int = 0,
    protected: int = 0,
    allowed: int = 0,
    residual: int = 0,
    destination_allowed: bool = True,
    policy_required_total: int = 0,
    policy_required_protected: int = 0,
    policy_required_residual: int = 0,
) -> PrivacyRiskAssessment:
    """Return one deterministic local privacy-risk assessment.

    The score is explanatory product guidance, not a legal or regulatory
    certification. Hard blocking is reserved for explicit managed-policy
    violations; Personal users keep their existing review/continue behavior.
    """

    detected = max(0, int(detected))
    protected = max(0, int(protected))
    allowed = max(0, int(allowed))
    residual = max(0, int(residual))
    policy_required_total = max(0, int(policy_required_total))
    policy_required_protected = max(0, int(policy_required_protected))
    policy_required_residual = max(0, int(policy_required_residual))
    missing_required = max(0, policy_required_total - policy_required_protected)

    if not destination_allowed:
        return PrivacyRiskAssessment(
            PrivacyRiskLevel.HIGH,
            100,
            "Blocked: the selected destination is not approved by the active company policy.",
            True,
        )
    if missing_required:
        return PrivacyRiskAssessment(
            PrivacyRiskLevel.HIGH,
            100,
            f"Blocked: {missing_required} company-required sensitive item(s) are not protected.",
            True,
        )
    if policy_required_residual:
        return PrivacyRiskAssessment(
            PrivacyRiskLevel.HIGH,
            100,
            f"Blocked: {policy_required_residual} company-required sensitive item(s) remain after the second scan.",
            True,
        )
    if residual:
        return PrivacyRiskAssessment(
            PrivacyRiskLevel.HIGH,
            min(99, 72 + residual * 4 + min(12, allowed * 2)),
            f"{residual} possible sensitive item(s) remain after protection; review before AI use.",
        )
    if allowed:
        return PrivacyRiskAssessment(
            PrivacyRiskLevel.MEDIUM,
            min(69, 38 + allowed * 5),
            f"{allowed} detected sensitive item(s) are intentionally left visible.",
        )
    if detected == 0:
        return PrivacyRiskAssessment(
            PrivacyRiskLevel.LOW,
            5,
            "No sensitive items were detected in the current scan.",
        )
    if protected >= detected:
        return PrivacyRiskAssessment(
            PrivacyRiskLevel.LOW,
            10,
            "All detected sensitive items are protected and the second scan is clear.",
        )
    remaining = max(0, detected - protected)
    return PrivacyRiskAssessment(
        PrivacyRiskLevel.MEDIUM,
        min(69, 42 + remaining * 5),
        f"{remaining} detected item(s) are not protected yet.",
    )


class UnifiedEnforcementEngine:
    """Compose existing policy/rule/consent decisions into one explanation layer."""

    @staticmethod
    def ai(
        *,
        destination: str,
        workspace_key: str,
        policy_allows: Callable[[str], bool] | None = None,
        rule_allows: Callable[[str, str], bool] | None = None,
        managed_required: bool = False,
        policy_available: bool = True,
        organization_name: str = "",
        unavailable_reason: str = "",
    ) -> EnforcementDecision:
        label = destination or "AI destination"
        if managed_required and not policy_available:
            return EnforcementDecision(
                False,
                unavailable_reason
                or "The managed company policy is unavailable on this device.",
                "company-policy",
            )
        if policy_allows is not None and not policy_allows(destination):
            owner = organization_name or "company"
            return EnforcementDecision(
                False,
                f"{label} is blocked by {owner} policy.",
                "company-policy",
            )
        if rule_allows is not None and not rule_allows(workspace_key, destination):
            return EnforcementDecision(
                False,
                f"{label} is not approved by the local rules for this workspace.",
                "workspace-rule",
            )
        return EnforcementDecision(True, f"{label} is approved for this workspace.")

    @staticmethod
    def connector(
        *,
        provider: str,
        workspace_key: str,
        account_id: str = "",
        policy_allows: Callable[[str], bool] | None = None,
        account_available: Callable[[str, str, str], bool] | None = None,
        organization_name: str = "",
        unavailable_reason: str = "",
    ) -> EnforcementDecision:
        label = (provider or "Connector").replace("_", " ").title()
        if policy_allows is not None and not policy_allows(provider):
            return EnforcementDecision(
                False,
                unavailable_reason
                or f"{label} is blocked by {organization_name or 'company'} policy.",
                "company-policy",
            )
        if account_id and account_available is not None:
            if not account_available(provider, account_id, workspace_key):
                return EnforcementDecision(
                    False,
                    f"{label} account access has not been granted to this workspace.",
                    "workspace-consent",
                )
        return EnforcementDecision(True, f"{label} is approved for this workspace.")

    @staticmethod
    def automation(
        *,
        target: str,
        workspace_key: str,
        rule_allows: Callable[[str, str], bool] | None = None,
    ) -> EnforcementDecision:
        label = target or "Automation"
        if rule_allows is not None and not rule_allows(workspace_key, label):
            return EnforcementDecision(
                False,
                f"{label} is not approved by the local rules for this workspace.",
                "workspace-rule",
            )
        return EnforcementDecision(True, f"{label} is approved for this workspace.")


PROFILE_SPEC_VERSION = "2026.1"


def profile_fingerprint(profile: object) -> str:
    payload = {
        "key": str(getattr(profile, "key", "") or ""),
        "name": str(getattr(profile, "name", "") or ""),
        "threshold": float(getattr(profile, "threshold", 0.0) or 0.0),
        "entities": sorted(
            {str(item) for item in getattr(profile, "entities", ()) if str(item)}
        ),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12].upper()
