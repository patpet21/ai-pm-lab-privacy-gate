from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


# A trailing full stop is normal sentence punctuation and must not invalidate an
# otherwise complete email/PEC. Domain labels are consumed greedily, so allowing
# punctuation after the final TLD does not truncate a longer valid domain.
_EMAIL_PATTERN = r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+(?![\w-])"
_PHONE_VALUE = r"(?:(?:\+39|0039)\s*)?(?:3\d{2}|0\d{1,3})(?:[\s./-]?\d){6,8}"


def build_contact_recognizers() -> tuple[object, ...]:
    return (
        PatternRecognizer(
            supported_entity="EMAIL_ADDRESS",
            supported_language="it",
            patterns=[Pattern("italian_email", _EMAIL_PATTERN, 0.97)],
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_PEC_ADDRESS",
            pattern=rf"\bpec(?:\s+address|\s+email|\s+mail)?\s*[:#-]?\s*(?P<value>{_EMAIL_PATTERN})",
            score=0.995,
        ),
        PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            supported_language="it",
            patterns=[
                Pattern(
                    "italian_international_phone",
                    r"(?<!\d)(?:\+39|0039)[\s.-]?(?:3\d{2}|0\d{1,3})(?:[\s.-]?\d){6,8}(?!\d)",
                    0.97,
                )
            ],
        ),
        ItalianContextValueRecognizer(
            entity_type="PHONE_NUMBER",
            pattern=rf"\b(?:telefono|tel\.?|cellulare|cell\.?|mobile|centralino)\s*(?:(?:n(?:umero)?\.?)\s*)?[:#-]?\s*(?P<value>{_PHONE_VALUE})(?!\d)",
            score=0.985,
        ),
    )
