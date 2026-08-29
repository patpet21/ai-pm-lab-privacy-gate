from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


_ID_VALUE = r"[A-Z0-9][A-Z0-9./-]{4,15}"
_SEPARATOR = r"\s*(?:(?:n(?:umero)?\.?|no\.?)\s*)?[:#-]?\s*"


def build_identity_document_recognizers() -> tuple[ItalianContextValueRecognizer, ...]:
    return (
        ItalianContextValueRecognizer(
            entity_type="IT_ID_CARD",
            pattern=rf"\b(?:carta\s+d['’]?identit[aà]|carta\s+identit[aà]|cie)\b{_SEPARATOR}(?P<value>{_ID_VALUE})\b",
            score=0.99,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_PASSPORT",
            pattern=rf"\bpassaporto\b{_SEPARATOR}(?P<value>{_ID_VALUE})\b",
            score=0.99,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_DRIVER_LICENSE",
            pattern=rf"\bpatente(?:\s+di\s+guida)?\b{_SEPARATOR}(?P<value>{_ID_VALUE})\b",
            score=0.99,
        ),
    )
