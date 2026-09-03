from __future__ import annotations

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile


def _maximum_profile():
    base = get_profile("general_business")
    return type(base)(
        key=base.key,
        name=base.name,
        description=base.description,
        entities=entities_for_scope(base, "maximum"),
        threshold=base.threshold,
    )


def _findings(text: str) -> set[tuple[str, str]]:
    service = PrivacyGateService()
    findings = service.analyze(
        service.document_from_text(text),
        _maximum_profile(),
        language="en",
    )
    return {(item.entity_type, item.text) for item in findings}


def test_password_placeholder_is_not_treated_as_real_credential() -> None:
    found = _findings("password = <redacted>")
    assert not any(entity == "PASSWORD_CREDENTIAL" for entity, _ in found)


def test_real_password_value_remains_protected() -> None:
    found = _findings("password = ActualSecret44!")
    assert ("PASSWORD_CREDENTIAL", "ActualSecret44!") in found


def test_remaining_capital_budget_keeps_more_specific_category() -> None:
    found = _findings("Remaining capital budget: 84,500")
    assert ("REMAINING_CAPITAL_BUDGET", "84,500") in found
    assert ("PROJECT_BUDGET_AMOUNT", "84,500") not in found


def test_project_budget_equals_form_remains_supported() -> None:
    found = _findings("Project budget = $245,000")
    assert ("PROJECT_BUDGET_AMOUNT", "$245,000") in found
