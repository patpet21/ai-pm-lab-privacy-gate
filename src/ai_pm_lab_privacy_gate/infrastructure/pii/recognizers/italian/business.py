from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


_SEPARATOR = r"\s*(?:(?:n(?:umero)?\.?|no\.?)\s*)?[:#-]?\s*"


def build_business_recognizers() -> tuple[ItalianContextValueRecognizer, ...]:
    return (
        ItalianContextValueRecognizer(
            entity_type="IT_REA_NUMBER",
            pattern=rf"(?:\br\.?\s*e\.?\s*a\.?|\brepertorio\s+economico\s+amministrativo)(?=\s|:|#|-){_SEPARATOR}(?P<value>[A-Z]{{2}}\s*[-/]?\s*\d{{3,9}})\b",
            score=0.99,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_BUSINESS_REGISTER_NUMBER",
            pattern=rf"\b(?:numero\s+)?registro\s+(?:delle\s+)?imprese\b{_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9./-]{{5,20}})\b",
            score=0.975,
        ),
    )
