from __future__ import annotations

"""Headless execution core for PrivacyGate Automation.

The runner only orchestrates existing ProtectSession and Policy behavior. It does
not know about Qt, Gmail polling, Library dialogs, or external AI destinations.
"""

from dataclasses import dataclass

from ai_pm_lab_privacy_gate.application.protect_session_service import (
    ProtectSessionAnalysis,
    ProtectSessionResult,
    ProtectSessionService,
)
from ai_pm_lab_privacy_gate.domain.automation import AutomationRunStatus
from ai_pm_lab_privacy_gate.domain.company_policy import PolicyEngine
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile
from ai_pm_lab_privacy_gate.domain.protect_package import ProtectPackage
from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService


@dataclass(frozen=True, slots=True)
class AutomationExecutionResult:
    status: AutomationRunStatus
    policy_status: str
    reason: str
    analysis: ProtectSessionAnalysis | None = None
    protected: ProtectSessionResult | None = None
    residual_by_source: dict[str, tuple[object, ...]] | None = None

    @property
    def detected_count(self) -> int:
        return len(self.analysis.findings) if self.analysis is not None else 0

    @property
    def protected_count(self) -> int:
        return self.protected.applied_findings_count if self.protected is not None else 0

    @property
    def residual_count(self) -> int:
        return sum(
            len(items)
            for items in (self.residual_by_source or {}).values()
        )

    @property
    def source_count(self) -> int:
        if self.protected is not None:
            return self.protected.source_count
        if self.analysis is not None:
            return len(self.analysis.sources)
        return 0


class AutomationRunner:
    """Run a local ProtectPackage with the same ProtectSession engine as manual UI."""

    def __init__(
        self,
        privacy_service: PrivacyGateService,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        self.protect = ProtectSessionService(privacy_service)
        self.policy = policy_engine or PolicyEngine()

    def run(
        self,
        package: ProtectPackage,
        profile: PrivacyProfile,
        *,
        replacement_mode: str = "reversible",
    ) -> AutomationExecutionResult:
        provider = str(
            package.metadata.get("provider")
            or package.origin
            or ""
        ).strip().lower()
        if provider and not self.policy.can_use_connector(provider):
            reason = (
                self.policy.unavailable_reason
                or f"{provider} is blocked by company policy."
            )
            return AutomationExecutionResult(
                status=AutomationRunStatus.BLOCKED,
                policy_status="blocked_connector",
                reason=reason,
            )

        analysis = self.protect.analyze(package, profile)
        selected_ids = {
            finding.finding_id
            for finding in analysis.findings
        }
        selected_ids = set(
            self.policy.enforce_selected_ids(analysis.findings, selected_ids)
        )
        protected = self.protect.protect(
            analysis,
            selected_ids,
            replacement_mode=replacement_mode,
        )
        residual = self.protect.verify(protected, profile)

        residual_findings = tuple(
            finding
            for findings in residual.values()
            for finding in findings
        )
        required_residual = tuple(
            finding
            for finding in residual_findings
            if self.policy.must_protect(
                str(getattr(finding, "entity_type", "") or "")
            )
        )

        if required_residual:
            return AutomationExecutionResult(
                status=AutomationRunStatus.BLOCKED,
                policy_status="blocked_required_residual",
                reason=(
                    f"{len(required_residual)} company-required sensitive item(s) "
                    "remain after the local residual check."
                ),
                analysis=analysis,
                protected=protected,
                residual_by_source=residual,
            )

        if residual_findings:
            return AutomationExecutionResult(
                status=AutomationRunStatus.NEEDS_REVIEW,
                policy_status="review_residual",
                reason=(
                    f"{len(residual_findings)} possible sensitive item(s) remain after protection."
                ),
                analysis=analysis,
                protected=protected,
                residual_by_source=residual,
            )

        return AutomationExecutionResult(
            status=AutomationRunStatus.SUCCESS,
            policy_status="allowed_local_library",
            reason="Protected locally with no residual sensitive findings.",
            analysis=analysis,
            protected=protected,
            residual_by_source=residual,
        )
