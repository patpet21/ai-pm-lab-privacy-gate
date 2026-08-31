from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_pdf_review import (
    add_local_review_values,
)


def test_browser_pdf_review_exposes_value_only_in_local_review_payload() -> None:
    response: dict[str, object] = {
        "analysis_id": "a" * 32,
        "findings": [
            {
                "finding_id": "PERSON_001",
                "entity_type": "PERSON",
                "page_number": 1,
                "score": 0.99,
            }
        ],
    }
    findings = (
        Finding(
            finding_id="PERSON_001",
            entity_type="PERSON",
            text="Pietro Forestieri",
            start=10,
            end=27,
            score=0.99,
            page_number=1,
            context="",
        ),
    )

    updated = add_local_review_values(
        response,
        findings,
        profile_key="general_business",
        language="en",
    )

    row = updated["findings"][0]
    assert row["display_value"] == "Pietro Forestieri"
    assert row["start"] == 10
    assert row["end"] == 27
    assert updated["profile_key"] == "general_business"
    assert updated["language"] == "en"
    assert updated["review_values_local_only"] is True
