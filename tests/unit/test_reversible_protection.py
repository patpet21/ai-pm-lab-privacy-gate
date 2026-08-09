from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding


def _finding(text: str, value: str, entity_type: str, occurrence: int = 0) -> Finding:
    start = -1
    cursor = 0
    for _ in range(occurrence + 1):
        start = text.index(value, cursor)
        cursor = start + len(value)
    return Finding(
        finding_id=f"{entity_type}-{start}",
        entity_type=entity_type,
        text=value,
        start=start,
        end=start + len(value),
        score=1.0,
        page_number=1,
        context=value,
    )


def test_reversible_tokens_are_stable_and_restore() -> None:
    text = "Jane Smith emailed jane@example.com. Jane Smith approved the lease."
    service = PrivacyGateService()
    document = service.document_from_text(text)
    findings = (
        _finding(text, "Jane Smith", "PERSON", 0),
        _finding(text, "jane@example.com", "EMAIL_ADDRESS"),
        _finding(text, "Jane Smith", "PERSON", 1),
    )

    result = service.protect(document, findings)

    assert result.combined_text.count("[[PG_PERSON_001]]") == 2
    assert "[[PG_EMAIL_ADDRESS_001]]" in result.combined_text
    assert service.restore_text(result.combined_text, result.mappings) == text


def test_generic_mode_does_not_persist_mapping() -> None:
    text = "Call Jane Smith."
    service = PrivacyGateService()
    result = service.protect(
        service.document_from_text(text),
        (_finding(text, "Jane Smith", "PERSON"),),
        replacement_mode="generic",
    )
    assert result.combined_text == "Call [[PERSON]]."
    assert result.mappings == ()
