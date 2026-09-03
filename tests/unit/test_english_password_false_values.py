from __future__ import annotations

from presidio_analyzer import RecognizerResult

from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine


def test_password_requirement_words_are_not_credentials() -> None:
    text = "Wi-Fi password requirements are documented separately."
    start = text.index("requirements")
    result = RecognizerResult(
        entity_type="PASSWORD_CREDENTIAL",
        start=start,
        end=start + len("requirements"),
        score=0.998,
    )

    filtered = PresidioPrivacyEngine._filter_context_value_false_positives(text, [result])

    assert filtered == []
