from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.real_estate import (
    ContextRule,
    ContextValueRecognizer,
)


_SEP = r"\s*(?::|=|#|[-–—])?\s*"
_CAP_WORD = r"(?-i:[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ0-9'’.-]*)"
_NAME_WORD = r"(?-i:(?:[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'’-]{1,30}|[A-Z]\.?))"
_PERSON_NAME = rf"{_NAME_WORD}(?:\s+{_NAME_WORD}){{1,3}}(?:,\s*(?:Jr\.?|Sr\.?|II|III|IV))?"
_ORG_NAME = rf"{_CAP_WORD}(?:\s+(?:&\s+)?{_CAP_WORD}){{1,6}}"
_PLACE_NAME = rf"{_CAP_WORD}(?:\s+(?:(?:of|the)\s+)?{_CAP_WORD}){{0,4}}"


# Semantic recall additions are deliberately context-led. They recover named
# entities from explicit business/identity labels without replacing spaCy or
# introducing a second NLP engine.
CONTEXT_RULES = (
    ContextRule(
        "PERSON",
        rf"(?:prepared\s+by|site\s+contact|contact\s+person|primary\s+contact|requested\s+by|approved\s+by|assigned\s+to|submitted\s+by)\b{_SEP}(?P<value>{_PERSON_NAME})(?=$|[.;]|\r?$)",
        score=0.997,
    ),
    ContextRule(
        "PERSON",
        rf"\b(?:please\s+)?copy\s+(?P<value>{_PERSON_NAME})(?=\s+(?:on|at|for)\b|[.;]|$)",
        score=0.997,
    ),
    ContextRule(
        "ORGANIZATION",
        rf"(?:employer|service\s+provider|organization)\b{_SEP}(?P<value>{_ORG_NAME})(?=$|[.;]|\r?$)",
        score=0.997,
    ),
    ContextRule(
        "LOCATION",
        rf"(?:jurisdiction|meeting\s+location|office\s+location)\b{_SEP}(?P<value>{_PLACE_NAME})(?=$|[.;]|\r?$)",
        score=0.997,
    ),
    ContextRule(
        "LOCATION",
        rf"\b(?:relocated|moved)\s+from\s+(?P<value>{_PLACE_NAME})(?=\s+(?:last|this|in|on|during|after|before)\b|[.,;]|$)",
        score=0.997,
    ),
)


PATTERN_RECOGNIZERS = (
    PatternRecognizer(
        supported_entity="ORGANIZATION",
        supported_language="en",
        patterns=[
            Pattern(
                "legal_suffix_organization",
                r"(?<!\w)(?-i:[A-Z][A-Za-z0-9'’.-]*)(?:\s+(?:(?-i:[A-Z][A-Za-z0-9'’.-]*)|&)){0,6}\s*,?\s+(?:LLC|Inc\.?|Corp\.?|Corporation|Ltd\.?|Company|Co\.?)\b",
                0.996,
            )
        ],
    ),
)


def install_english_semantic_context_recognizers(registry) -> None:  # noqa: ANN001
    for rule in CONTEXT_RULES:
        registry.add_recognizer(ContextValueRecognizer(rule))
    for recognizer in PATTERN_RECOGNIZERS:
        registry.add_recognizer(recognizer)
