from __future__ import annotations

from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_context import augment_browser_findings


def _finding(text: str, value: str, entity_type: str = "ORGANIZATION") -> Finding:
    start = text.index(value)
    return Finding(
        finding_id=f"{entity_type.lower()}-1",
        entity_type=entity_type,
        text=value,
        start=start,
        end=start + len(value),
        score=0.72,
        page_number=1,
        context=text,
    )


def test_explicit_short_name_becomes_person() -> None:
    text = "name pietro"
    findings = augment_browser_findings(text, ())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.entity_type == "PERSON"
    assert finding.text == "pietro"
    assert text[finding.start:finding.end] == "pietro"


def test_italian_self_introduction_becomes_person() -> None:
    text = "mi chiamo Pietro"
    findings = augment_browser_findings(text, (), language="it")

    assert len(findings) == 1
    assert findings[0].entity_type == "PERSON"
    assert findings[0].text == "Pietro"


def test_contextual_person_replaces_overlapping_organization() -> None:
    text = "name pietro"
    findings = augment_browser_findings(text, (_finding(text, "pietro"),))

    assert len(findings) == 1
    assert findings[0].entity_type == "PERSON"
    assert findings[0].text == "pietro"


def test_normal_chat_does_not_create_person() -> None:
    assert augment_browser_findings("ma allora possiamo chattare?", (), language="it") == ()


def test_short_chat_noise_is_not_an_organization() -> None:
    text = "ok dai"
    findings = augment_browser_findings(
        text,
        (_finding(text, "dai"),),
        language="it",
    )

    assert findings == ()


def test_italian_street_context_becomes_street_address() -> None:
    text = "quindi se scrivo via Mazzini"
    findings = augment_browser_findings(
        text,
        (
            _finding(text, "Mazzini", "PERSON"),
            _finding(text, "Mazzini", "ORGANIZATION"),
        ),
        language="it",
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.entity_type == "STREET_ADDRESS"
    assert finding.text == "via Mazzini"
    assert text[finding.start:finding.end] == "via Mazzini"
