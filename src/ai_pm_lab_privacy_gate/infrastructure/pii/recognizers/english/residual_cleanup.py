from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.real_estate import (
    ContextRule,
    ContextValueRecognizer,
)


_SEP = r"[ \t]*(?::|=|#|[-–—])?[ \t]*(?:\r?\n[ \t]*)?"
_DATE_VALUE = (
    r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"\d{4}-\d{1,2}-\d{1,2}|"
    r"[A-Z][a-z]+[ \t]+\d{1,2},?[ \t]+\d{4})"
)
_DL_VALUE = r"(?=[A-Z0-9 -]{6,20}(?:$|[.,;\r\n]))(?=[A-Z0-9 -]*\d)[A-Z0-9][A-Z0-9 -]{4,18}[A-Z0-9]"


# Small precision-first cleanup for residual benchmark/document formats. Every
# contextual rule requires an explicit identity/transaction label.
CONTEXT_RULES = (
    ContextRule(
        "US_DRIVER_LICENSE",
        rf"(?:dl(?:[ \t]+(?:number|no\.?))?|license[ \t]+no\.?|driver(?:'s|s)?[ \t]+licen[cs]e(?:[ \t]+(?:number|no\.?))?){_SEP}(?P<value>{_DL_VALUE})",
        score=0.999,
    ),
    ContextRule(
        "US_PASSPORT",
        rf"(?:u\.s\.[ \t]+)?passport(?:[ \t]*\(us\))?(?:[ \t]+(?:number|no\.?))?{_SEP}(?P<value>[A-Z0-9]{{6,12}})\b",
        score=0.999,
    ),
    ContextRule(
        "DATE_OF_BIRTH",
        rf"(?:dob|date[ \t]+of[ \t]+birth|birth[ \t]+date)\b{_SEP}(?P<value>{_DATE_VALUE})\b",
        score=0.999,
    ),
    ContextRule(
        "MERCHANT",
        r"(?im)^[ \t]*merchant[ \t]*[:=#-][ \t]*(?P<value>[A-Z][^\r\n]{1,99}?)[ \t]*$",
        score=0.999,
    ),
)


PATTERN_RECOGNIZERS = (
    PatternRecognizer(
        supported_entity="PHONE_NUMBER",
        supported_language="en",
        patterns=[
            Pattern(
                "us_phone_with_extension",
                r"(?<!\d)\d{3}-\d{3}-\d{4}[ \t]+(?:ext(?:ension)?\.?|x)[ \t]*\d{1,6}(?!\d)",
                0.999,
            )
        ],
    ),
)


def install_english_residual_cleanup_recognizers(registry) -> None:  # noqa: ANN001
    for rule in CONTEXT_RULES:
        registry.add_recognizer(ContextValueRecognizer(rule))
    for recognizer in PATTERN_RECOGNIZERS:
        registry.add_recognizer(recognizer)
