from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


_SEPARATOR = r"\s*(?:(?:n(?:umero)?\.?|no\.?)\s*)?[:#-]?\s*"

_ORGANIZATION_WITH_LEGAL_SUFFIX = (
    r"(?<![\wÀ-ÖØ-öø-ÿ])"
    r"(?-i:"
    r"(?:[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’&.-]*\s+){1,8}"
    r"(?:[Ss]\.?\s*[Rr]\.?\s*[Ll]\.?|[Ss]\.?\s*[Pp]\.?\s*[Aa]\.?|"
    r"[Ss][Nn][Cc]|[Ss][Aa][Ss])"
    r")"
    r"(?=\s|[,;:]|\.?$)"
)


def _looks_like_registry_number(value: str) -> bool:
    compact = "".join(char for char in value if char.isalnum())
    return len(compact) >= 6 and any(char.isdigit() for char in compact)


def build_business_recognizers() -> tuple[ItalianContextValueRecognizer, ...]:
    return (
        ItalianContextValueRecognizer(
            entity_type="ORGANIZATION",
            pattern=rf"(?P<value>{_ORGANIZATION_WITH_LEGAL_SUFFIX})",
            score=0.998,
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
            validator=_looks_like_registry_number,
        ),
    )
