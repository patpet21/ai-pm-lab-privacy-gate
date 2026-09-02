from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer


# English/US address V2 remains deterministic and local. It extends the existing
# generic address recognizer with common US house-number and unit/directional
# forms that the baseline proved were being truncated or missed.
_HOUSE_NUMBER = r"(?:\d{1,6}(?:-\d{1,6})?[A-Z]?|\d{1,6}[¼½¾])"
_STREET_WORD = r"[A-Z0-9][A-Z0-9.'’/-]*"
_STREET_SUFFIX = (
    r"(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Lane|Ln\.?|"
    r"Drive|Dr\.?|Court|Ct\.?|Parkway|Pkwy\.?|Highway|Hwy\.?|Place|Pl\.?|"
    r"Terrace|Ter\.?|Way|Circle|Cir\.?)"
)
_DIRECTIONAL = r"(?:NE|NW|SE|SW|N|S|E|W)"
_UNIT_LABEL = r"(?:Apt\.?|Apartment|Unit|Suite|Floor|Fl\.?|Building|Bldg\.?)"
_UNIT_TAIL = (
    rf"(?:\s*,?\s*(?:{_UNIT_LABEL}\s*#?\s*[A-Z0-9-]+|#\s*[A-Z0-9-]+))?"
)
_CITY_TAIL = r"(?:\s*,\s*[A-Z][A-Za-z.'’ -]{1,40})?"
_STATE_ZIP_TAIL = r"(?:\s*,\s*[A-Z]{2}(?:\s+\d{5}(?:-\d{4})?)?)?"

_NORTH_AMERICAN_STREET_V2 = (
    rf"(?i)\b{_HOUSE_NUMBER}\s+"
    rf"(?:{_STREET_WORD}\s+){{1,8}}"
    rf"{_STREET_SUFFIX}(?=\s|,|#|$)"
    rf"(?:\s+{_DIRECTIONAL}\.?)?"
    rf"{_UNIT_TAIL}{_CITY_TAIL}{_STATE_ZIP_TAIL}"
)


PATTERN_RECOGNIZERS = (
    PatternRecognizer(
        supported_entity="STREET_ADDRESS",
        supported_language="en",
        patterns=[
            Pattern("north_american_street_v2", _NORTH_AMERICAN_STREET_V2, 0.999),
            Pattern(
                "po_box_v2",
                r"(?i)\bP\.?\s*O\.?\s+Box\s+\d{1,10}[A-Z]?\b",
                0.995,
            ),
            Pattern(
                "rural_route_v2",
                r"(?i)\b(?:RR|Rural\s+Route)\s+\d{1,4}\s+(?:Box\s+)?\d{1,10}[A-Z]?\b",
                0.995,
            ),
        ],
    ),
)


def install_english_address_v2_recognizers(registry) -> None:  # noqa: ANN001
    for recognizer in PATTERN_RECOGNIZERS:
        registry.add_recognizer(recognizer)
