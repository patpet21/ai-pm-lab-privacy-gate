from __future__ import annotations

import re


_FALSE_PERSON_TERMS = {
    "landlord",
    "driver license",
    "ein",
    "phone_number",
    "english",
    "privacy check",
}

_LABEL_LINE_RE = re.compile(r"^[A-Z][A-Z0-9_ /-]{2,}$")


def is_nyc_real_estate_person_false_positive(value: str) -> bool:
    """Return True for obvious labels/checklist terms that are never people."""
    clean = " ".join((value or "").strip().split()).casefold()
    if not clean:
        return False
    if clean in _FALSE_PERSON_TERMS:
        return True
    if _LABEL_LINE_RE.fullmatch((value or "").strip()) and "_" in (value or ""):
        return True
    return False
