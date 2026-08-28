from pathlib import Path

from ai_pm_lab_privacy_gate.application.automation_runner import AutomationRunner
from ai_pm_lab_privacy_gate.application.protect_completion_service import ProtectCompletionService
from ai_pm_lab_privacy_gate.domain.automation import AutomationRunStatus
from ai_pm_lab_privacy_gate.domain.company_policy import (
    CompanyPolicy,
    PolicyEngine,
    ProtectionDirective,
)
from ai_pm_lab_privacy_gate.domain.models import (
    AnalysisDocument,
    Finding,
    PageContent,
    ProtectionResult,
    ReplacementMapping,
)
from ai_pm_lab_privacy_gate.domain.plans import PlanCode
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile
from ai_pm_lab_privacy_gate.domain.protect_package import ProtectPackage, ProtectSource


PROFILE = PrivacyProfile(
    key="test",
    name="Test",
    description="Test profile",
    entities=("PERSON",),
)


class StubPrivacyService:
    def __init__(self, *, residual: bool = False) -> None:
        self.residual = residual

    def document_from_text(self, text: str) -> AnalysisDocument:
        return AnalysisDocument("text", (PageContent(1, text),))

    def document_from_file(self, path: str) -> AnalysisDocument:
        value = Path(path).read_text(encoding="utf-8")
        return AnalysisDocument("txt", (PageContent(1, value),), Path(path))

    def analyze(self, document: AnalysisDocument, _profile: PrivacyProfile):
        text = document.pages[0].text
        if "John Smith" not in text:
            return ()
        start = text.index("John Smith")
        return (
            Finding(
                finding_id="person-1",
                entity_type="PERSON",
                text="John Smith",
                start=start,
                end=start + len("John Smith"),
                score=0.99,
                page_number=1,
                context=text,
            ),
        )

    def protect(self, document: AnalysisDocument, findings, *, replacement_mode: str):
        selected = tuple(findings)
        text = document.pages[0].text
        mappings = []
        for index, finding in enumerate(selected, start=1):
            token = f"[[PG_PERSON_{index:03d}]]"
            text = text.replace(finding.text, token)
            mappings.append(ReplacementMapping(token, finding.entity_type, finding.text))
        return ProtectionResult(
            protected_pages=(PageContent(1, text),),
            applied_findings=selected,
            mappings=tuple(mappings),
            replacement_mode=replacement_mode,
        )

    def verify_protected(self, _result: ProtectionResult, _profile: PrivacyProfile):
        if not self.residual:
            return ()
        return (
            Finding(
                finding_id="residual-1",
                entity_type="PERSON",
                text="Residual Person",
                start=0,
                end=15,
                score=0.9,
                page_number=1,
                context="Residual Person",
            ),
        )


class StubLibrary:
    def __init__(self) -> None:
        self.saved = []

    def save(self, **kwargs):
        self.saved.append(kwargs)
        return kwargs


def gmail_package() -> ProtectPackage:
    return ProtectPackage(
        origin="gmail",
        label="Lease request",
        metadata={"provider": "gmail", "item_id": "message-1"},
        sources=(
            ProtectSource.text_source(
                key="gmail_body",
                label="Email body",
                text="Please review John Smith's lease.",
                metadata={"provider": "gmail"},
            ),
        ),
    )


def test_runner_uses_existing_protect_session_and_protects_all_findings():
    runner = AutomationRunner(StubPrivacyService())
    result = runner.run(gmail_package(), PROFILE)

    assert result.status is AutomationRunStatus.SUCCESS
    assert result.detected_count == 1
    assert result.protected_count == 1
    assert result.residual_count == 0
    assert result.protected is not None
    assert "John Smith" not in result.protected.combined_text
    assert "[[PG_PERSON_001]]" in result.protected.combined_text


def test_non_required_residual_routes_to_human_review():
    runner = AutomationRunner(StubPrivacyService(residual=True))
    result = runner.run(gmail_package(), PROFILE)

    assert result.status is AutomationRunStatus.NEEDS_REVIEW
    assert result.residual_count == 1
    assert result.policy_status == "review_residual"


def test_required_residual_is_blocked_by_company_policy():
    policy = CompanyPolicy(
        organization_id="org-1",
        organization_name="Test Org",
        version=1,
        plan=PlanCode.BUSINESS,
        allowed_connectors={"gmail": True},
        protection_rules={"PERSON": ProtectionDirective.REQUIRED_PROTECT},
    )
    runner = AutomationRunner(
        StubPrivacyService(residual=True),
        PolicyEngine(policy),
    )
    result = runner.run(gmail_package(), PROFILE)

    assert result.status is AutomationRunStatus.BLOCKED
    assert result.policy_status == "blocked_required_residual"


def test_managed_policy_unavailable_blocks_connector_before_processing():
    runner = AutomationRunner(
        StubPrivacyService(),
        PolicyEngine.unavailable("Managed policy unavailable"),
    )
    result = runner.run(gmail_package(), PROFILE)

    assert result.status is AutomationRunStatus.BLOCKED
    assert result.analysis is None
    assert result.policy_status == "blocked_connector"


def test_completion_service_reuses_library_save_contract():
    runner = AutomationRunner(StubPrivacyService())
    execution = runner.run(gmail_package(), PROFILE)
    assert execution.protected is not None

    library = StubLibrary()
    completion = ProtectCompletionService(library)  # type: ignore[arg-type]
    saved = completion.save_session(
        execution.protected,
        title="Automated lease",
        profile_key=PROFILE.key,
        labels=("automation", "gmail"),
    )

    assert saved.primary is library.saved[0]
    assert library.saved[0]["title"] == "Automated lease"
    assert library.saved[0]["source_name"] == "Email body"
    assert library.saved[0]["profile_key"] == "test"
    assert library.saved[0]["labels"] == ("automation", "gmail")
