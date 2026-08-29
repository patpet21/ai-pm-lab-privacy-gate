from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


def build_vehicle_recognizers() -> tuple[ItalianContextValueRecognizer, ...]:
    return (
        ItalianContextValueRecognizer(
            entity_type="IT_VEHICLE_PLATE",
            pattern=r"\b(?:numero\s+)?targa\b\s*(?:(?:n(?:umero)?\.?)\s*)?[:#-]?\s*(?P<value>[A-Z]{2}\s*\d{3}\s*[A-Z]{2})\b",
            score=0.99,
        ),
    )
