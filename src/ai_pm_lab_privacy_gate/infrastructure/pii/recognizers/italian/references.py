from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


# Keep the value conservative: case/practice references must contain at least
# one digit and use identifier-style separators only. The explicit nearby label
# supplies the semantic meaning; this avoids treating arbitrary prose as an ID.
_REFERENCE_VALUE = r"(?=[A-Z0-9_/-]*\d)[A-Z0-9][A-Z0-9_/-]{2,39}"

# Real documents vary the label much more than a synthetic fixture: "pratica",
# "pratica del cliente", "pratica n.", "numero pratica" and "case ID" all carry
# the same privacy meaning when followed by an identifier-shaped value.
_REFERENCE_LABEL = (
    r"(?:"
    r"pratica\s+di\s+riferimento|"
    r"pratica\s+(?:del|della)\s+(?:cliente|immobile|proprietario|conduttore)|"
    r"pratica(?:\s+n(?:umero)?\.?)?|"
    r"numero\s+(?:della\s+)?pratica|"
    r"riferimento\s+(?:della\s+)?pratica|"
    r"riferimento\s+(?:del\s+)?caso|"
    r"numero\s+(?:del\s+)?caso|"
    r"case\s+(?:reference|id|number)"
    r")"
)


def build_reference_recognizers() -> tuple[ItalianContextValueRecognizer, ...]:
    return (
        ItalianContextValueRecognizer(
            entity_type="CASE_REFERENCE",
            pattern=(
                rf"(?<!\w){_REFERENCE_LABEL}(?!\w)"
                r"\s*(?:n(?:umero)?\.?\s*)?(?:è|e|:|#|-)?\s*"
                rf"(?P<value>{_REFERENCE_VALUE})"
                r"(?![A-Z0-9_/-])"
            ),
            score=0.985,
        ),
    )
