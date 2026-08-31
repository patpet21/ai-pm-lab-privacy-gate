from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


# Keep the value conservative: case/practice references must contain at least
# one digit and use identifier-style separators only. The explicit nearby label
# supplies the semantic meaning; this avoids treating arbitrary prose as an ID.
_REFERENCE_VALUE = r"(?=[A-Z0-9_/-]*\d)[A-Z0-9][A-Z0-9_/-]{2,39}"


def build_reference_recognizers() -> tuple[ItalianContextValueRecognizer, ...]:
    return (
        ItalianContextValueRecognizer(
            entity_type="CASE_REFERENCE",
            pattern=(
                r"\b(?:"
                r"pratica\s+di\s+riferimento|"
                r"numero\s+pratica|"
                r"riferimento\s+pratica|"
                r"riferimento\s+del\s+caso|"
                r"numero\s+caso|"
                r"case\s+reference"
                r")\b"
                r"\s*(?:è|e|:|#|-)?\s*"
                rf"(?P<value>{_REFERENCE_VALUE})"
                r"(?![A-Z0-9_/-])"
            ),
            score=0.985,
        ),
    )
