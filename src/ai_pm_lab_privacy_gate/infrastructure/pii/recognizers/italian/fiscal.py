from __future__ import annotations

import re

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)
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

# A checksum-invalid but CF-shaped value is still sensitive when an explicit
# fiscal-code label is present. Natural business text commonly inserts a role
# between the label and value ("codice fiscale del cliente", "CF intestatario").
_CF_CONTEXT_ROLE = (
    r"(?:cliente|intestatario|proprietario|locatore|conduttore|richiedente|"
    r"beneficiario|soggetto|persona|dipendente|fornitore)"
)
_CF_CONTEXT_QUALIFIER = (
    rf"(?:\s+(?:(?:del|della|dello|di)\s+{_CF_CONTEXT_ROLE}|"
    rf"dell['’]\s*{_CF_CONTEXT_ROLE}|{_CF_CONTEXT_ROLE}))?"
)


def is_structurally_plausible_codice_fiscale(value: str) -> bool:
    """Accept CF-shaped values when explicit context already proves sensitivity."""
    candidate = re.sub(r"\s+", "", value).upper()
    return bool(_CF_STRUCTURE.fullmatch(candidate))


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


def build_fiscal_recognizers() -> tuple[
    ValidatedRegexRecognizer | ItalianContextValueRecognizer, ...
]:
    return (
        # Strong generic detector: checksum-valid CF values are sensitive even
        # without a nearby label.
        ValidatedRegexRecognizer(
            entity_type="IT_FISCAL_CODE",
            pattern=r"(?<![A-Z0-9])[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z](?![A-Z0-9])",
            validator=is_valid_codice_fiscale,
        ),
        # Privacy-first contextual fallback. Keep the context explicit, but
        # accept ordinary wording around the label instead of requiring the
        # value to follow "codice fiscale" immediately.
        ItalianContextValueRecognizer(
            entity_type="IT_FISCAL_CODE",
            pattern=(
                r"(?<!\w)(?:codice\s+fiscale|c\.?\s*f\.?|cf)(?!\w)"
                + _CF_CONTEXT_QUALIFIER
                + r"\s*(?:n(?:umero)?\.?\s*)?(?:è|e|:|#|-)?\s*"
                + r"(?P<value>[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z]"
                + r"[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z])"
                + r"(?![A-Z0-9])"
            ),
            score=0.985,
            validator=is_structurally_plausible_codice_fiscale,
        ),
        ValidatedRegexRecognizer(
            entity_type="IT_VAT_NUMBER",
            pattern=r"(?<![A-Z0-9])(?:IT\s*)?\d{11}(?!\d)",
            validator=is_valid_partita_iva,
        ),
    )
