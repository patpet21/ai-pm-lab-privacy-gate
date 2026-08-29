from __future__ import annotations

import re
from datetime import date, datetime

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}
_MONTH_NAME = "(?:" + "|".join(_MONTHS) + ")"
_DATE_VALUE = rf"(?:\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{4}}|\d{{1,2}}\s+{_MONTH_NAME}\s+\d{{4}})"


def is_valid_italian_birth_date(value: str) -> bool:
    candidate = " ".join(value.strip().lower().split())
    try:
        if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", candidate):
            day_text, month_text, year_text = re.split(r"[/-]", candidate)
            parsed = date(int(year_text), int(month_text), int(day_text))
        else:
            match = re.fullmatch(
                rf"(?P<day>\d{{1,2}})\s+(?P<month>{_MONTH_NAME})\s+(?P<year>\d{{4}})",
                candidate,
            )
            if match is None:
                return False
            parsed = date(
                int(match.group("year")),
                _MONTHS[match.group("month")],
                int(match.group("day")),
            )
    except ValueError:
        return False

    # A birth date cannot be in the future. Keep the lower bound broad enough for
    # historical/property/legal records while rejecting obviously malformed years.
    return 1900 <= parsed.year <= datetime.now().year and parsed <= date.today()


def build_date_recognizers() -> tuple[ItalianContextValueRecognizer, ...]:
    return (
        ItalianContextValueRecognizer(
            entity_type="DATE_OF_BIRTH",
            pattern=(
                rf"\b(?:data\s+di\s+nascita|nato|nata)\b"
                rf"\s*[:#-]?\s*"
                rf"(?:\b(?:a|in)\s+[^\r\n,;.]+?\s+)?"
                rf"(?:il\s+)?(?P<value>{_DATE_VALUE})\b"
            ),
            score=0.995,
            validator=is_valid_italian_birth_date,
        ),
    )
