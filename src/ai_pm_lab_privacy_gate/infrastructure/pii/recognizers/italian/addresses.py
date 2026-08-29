from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


_STREET_PATTERN = r"(?i)\b(?:via|viale|piazza|piazzale|corso|largo|vicolo|strada|lungomare|contrada|frazione)\s+(?:[A-ZÀ-ÖØ-öø-ÿ0-9][\wÀ-ÖØ-öø-ÿ'’.-]*\s+){1,8}\d{1,5}[A-Z]?(?:[/\-][A-Z0-9]{1,4})?\b"


def build_address_recognizers() -> tuple[object, ...]:
    return (
        PatternRecognizer(
            supported_entity="STREET_ADDRESS",
            supported_language="it",
            patterns=[Pattern("italian_street_address", _STREET_PATTERN, 0.95)],
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_POSTAL_CODE",
            pattern=r"(?:\bcap\b|codice\s+di\s+avviamento\s+postale)\s*[:#-]?\s*(?P<value>\d{5})(?!\d)",
            score=0.985,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_POSTAL_CODE",
            pattern=r"^\s*(?P<value>\d{5})\s+[A-ZÀ-ÖØ-öø-ÿ][^\r\n,;]{1,50}(?:\s+\([A-Z]{2}\))?\s*$",
            score=0.94,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_PROVINCE",
            pattern=r"\b(?:provincia|prov\.?)\s*[:#-]?\s*(?P<value>[A-Z]{2})\b",
            score=0.98,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_PROVINCE",
            pattern=r"\b\d{5}\s+[A-ZÀ-ÖØ-öø-ÿ][^\r\n,;]{1,40}\s+\((?P<value>[A-Z]{2})\)",
            score=0.95,
        ),
    )
