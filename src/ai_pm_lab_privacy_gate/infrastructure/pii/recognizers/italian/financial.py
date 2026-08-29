from __future__ import annotations

import re

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.validated_pattern import (
    ValidatedRegexRecognizer,
)


_IT_IBAN_STRUCTURE = re.compile(r"^IT\d{2}[A-Z]\d{10}[A-Z0-9]{12}$")


def is_valid_italian_iban(value: str) -> bool:
    candidate = re.sub(r"\s+", "", value).upper()
    if not _IT_IBAN_STRUCTURE.fullmatch(candidate):
        return False

    rearranged = candidate[4:] + candidate[:4]
    remainder = 0
    for char in rearranged:
        expanded = str(ord(char) - 55) if char.isalpha() else char
        for digit in expanded:
            remainder = (remainder * 10 + int(digit)) % 97
    return remainder == 1


def build_financial_recognizers() -> tuple[ValidatedRegexRecognizer, ...]:
    return (
        ValidatedRegexRecognizer(
            entity_type="IBAN_CODE",
            pattern=r"(?<![A-Z0-9])IT(?:\s?[A-Z0-9]){25}(?![A-Z0-9])",
            validator=is_valid_italian_iban,
        ),
    )
