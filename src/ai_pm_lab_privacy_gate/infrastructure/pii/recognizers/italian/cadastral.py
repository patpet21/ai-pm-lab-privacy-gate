from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


_SEPARATOR = r"\s*(?:(?:n(?:umero)?\.?)\s*)?[:#-]?\s*"


def build_cadastral_recognizers() -> tuple[ItalianContextValueRecognizer, ...]:
    return (
        ItalianContextValueRecognizer(
            entity_type="IT_CADASTRAL_MUNICIPAL_CODE",
            pattern=rf"\b(?:codice\s+(?:comune|catastale)|comune\s+catastale)\b{_SEPARATOR}(?P<value>[A-Z0-9]{{4,5}})\b",
            score=0.99,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_CADASTRAL_SECTION",
            pattern=rf"\bsezione(?:\s+(?:urbana|catastale))?\b{_SEPARATOR}(?P<value>[A-Z0-9]{{1,4}})\b",
            score=0.98,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_CADASTRAL_SHEET",
            pattern=rf"\bfoglio(?:\s+catastale)?\b{_SEPARATOR}(?P<value>\d{{1,5}})\b",
            score=0.99,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_CADASTRAL_PARCEL",
            pattern=rf"\b(?:particella|mappale)\b{_SEPARATOR}(?P<value>\d{{1,5}}(?:\s*/\s*\d{{1,4}})?)\b",
            score=0.99,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_CADASTRAL_SUBALTERN",
            pattern=rf"\b(?:subalterno|sub\.)\b{_SEPARATOR}(?P<value>[A-Z0-9]{{1,6}})\b",
            score=0.99,
        ),
    )
