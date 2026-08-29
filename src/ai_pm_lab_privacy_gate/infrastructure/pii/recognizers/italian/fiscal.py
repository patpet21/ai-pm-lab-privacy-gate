from __future__ import annotations

import re

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.validated_pattern import (
    ValidatedRegexRecognizer,
)


_CF_STRUCTURE = re.compile(
    r"^[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]$"
)
_PIVA_STRUCTURE = re.compile(r"^(?:IT)?\d{11}$")

_CF_ODD_VALUES = {
    **dict(zip("0123456789", (1, 0, 5, 7, 9, 13, 15, 17, 19, 21), strict=True)),
    **dict(
        zip(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            (1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23),
            strict=True,
        )
    ),
}
_CF_EVEN_VALUES = {
    **{str(index): index for index in range(10)},
    **{chr(ord("A") + index): index for index in range(26)},
}


def is_valid_codice_fiscale(value: str) -> bool:
    candidate = re.sub(r"\s+", "", value).upper()
    if not _CF_STRUCTURE.fullmatch(candidate):
        return False
    total = 0
    for position, char in enumerate(candidate[:15], start=1):
        values = _CF_ODD_VALUES if position % 2 else _CF_EVEN_VALUES
        total += values[char]
    expected = chr(ord("A") + total % 26)
    return candidate[-1] == expected


def is_valid_partita_iva(value: str) -> bool:
    candidate = re.sub(r"[^0-9]", "", value.upper().removeprefix("IT"))
    if len(candidate) != 11 or not candidate.isdigit():
        return False
    total = 0
    for index, char in enumerate(candidate):
        digit = int(char)
        if index % 2 == 0:
            total += digit
        else:
            doubled = digit * 2
            total += doubled - 9 if doubled > 9 else doubled
    return total % 10 == 0


def build_fiscal_recognizers() -> tuple[ValidatedRegexRecognizer, ...]:
    return (
        ValidatedRegexRecognizer(
            entity_type="IT_FISCAL_CODE",
            pattern=r"(?<![A-Z0-9])[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z](?![A-Z0-9])",
            validator=is_valid_codice_fiscale,
        ),
        ValidatedRegexRecognizer(
            entity_type="IT_VAT_NUMBER",
            pattern=r"(?<![A-Z0-9])(?:IT\s*)?\d{11}(?!\d)",
            validator=is_valid_partita_iva,
        ),
    )
