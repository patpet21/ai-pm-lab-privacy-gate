from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


_SEPARATOR = r"\s*(?:(?:n(?:umero)?\.?|no\.?)\s*)?[:#-]?\s*"
_ORGANIZATION_WITH_LEGAL_SUFFIX = (
    r"(?<![\wÀ-ÖØ-öø-ÿ])"
    r"(?:[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’&.-]*\s+){1,8}"
    r"(?:S\.?\s*[Rr]\.?\s*[Ll]\.?|S\.?\s*[Pp]\.?\s*[Aa]\.?|SNC|SAS)"
    r"(?=\s|[,;:]|\.?$)"
)


def build_business_recognizers() -> tuple[object, ...]:
    return (
        PatternRecognizer(
            supported_entity="ORGANIZATION",
            supported_language="it",
            patterns=[
                Pattern(
                    "italian_organization_legal_suffix",
                    _ORGANIZATION_WITH_LEGAL_SUFFIX,
                    0.985,
                )
            ],
        ),
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
