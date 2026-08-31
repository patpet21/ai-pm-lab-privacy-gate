from __future__ import annotations

import re

from ai_pm_lab_privacy_gate.domain.models import Finding


# Browser chat is often short and informal, which makes statistical NER less
# reliable than on documents. These narrow patterns only cover explicit
# browser-chat context; they are not general "capitalized word = person" rules.
_CONTEXTUAL_PERSON_PATTERN = re.compile(
    r"\b(?i:my\s+name\s+is|name(?:\s+is)?|nome(?:\s+(?:è|e'))?|mi\s+chiamo)"
    r"\s*[:\-]?\s*"
    r"(?P<person>[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,39}"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,39}){0,2})"
)

_ITALIAN_RELATION_ROLE = (
    r"socio|socia|collega|amico|amica|fratello|sorella|marito|moglie|"
    r"padre|madre|figlio|figlia|capo|supervisore|supervisora"
)

_ITALIAN_RELATIONAL_PERSON_PATTERN = re.compile(
    r"\b(?P<person>[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,39}"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,39}){0,2})"
    r"\s+(?i:è|e')\s+"
    r"(?:(?i:il|la|un|una)\s+)?"
    r"(?:(?i:mio|mia|nostro|nostra)\s+)?"
    rf"(?i:{_ITALIAN_RELATION_ROLE})\b"
)

_ITALIAN_RELATIONAL_PERSON_REVERSE_PATTERN = re.compile(
    r"\b(?:(?i:il|la|un|una)\s+)?"
    r"(?:(?i:mio|mia|nostro|nostra)\s+)?"
    rf"(?i:{_ITALIAN_RELATION_ROLE})\s+"
    r"(?i:è|e')\s+"
    r"(?P<person>[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,39}"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,39}){0,2})\b"
)

_ITALIAN_STREET_PATTERN = re.compile(
    r"\b(?i:via|viale|piazza|corso|largo|vicolo)\s+"
    r"(?P<street>[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,49}"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,49}){0,3})"
)

# Short conversational words are occasionally mislabeled as organizations or
# people by multilingual/statistical NER. Keep this deliberately browser-only.
_ORGANIZATION_CHAT_NOISE = {
    "ah",
    "allora",
    "bene",
    "ciao",
    "dai",
    "grazie",
    "hello",
    "hi",
    "ok",
    "okay",
    "perfetto",
    "please",
    "thanks",
    "va bene",
}

_PERSON_CHAT_NOISE = {
    "ah",
    "allora",
    "bene",
    "ciao",
    "ciao finalmente",
    "finalmente",
    "grazie",
    "hello",
    "hi",
    "ok",
    "okay",
    "perfetto",
    "please",
    "thanks",
    "va bene",
}

_ORGANIZATION_SUFFIXES = (
    " inc",
    " inc.",
    " llc",
    " ltd",
    " ltd.",
    " corp",
    " corp.",
    " company",
    " co.",
    " srl",
    " s.r.l.",
    " spa",
    " s.p.a.",
)


def _normalized_chat_value(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _overlaps(item: Finding, start: int, end: int) -> bool:
    return item.start < end and start < item.end


def _has_uppercase_signal(value: str) -> bool:
    return any(char.isupper() for char in value)


def _keep_statistical_person(item: Finding) -> bool:
    normalized = _normalized_chat_value(item.text)
    if not normalized or normalized in _PERSON_CHAT_NOISE:
        return False

    # In short browser chat, an all-lowercase statistical PERSON is too weak a
    # signal by itself. Explicit name context is added back below with a stable
    # browser-person finding, while title-cased names remain protected.
    return _has_uppercase_signal(item.text)


def _keep_statistical_organization(item: Finding) -> bool:
    normalized = _normalized_chat_value(item.text)
    if not normalized or normalized in _ORGANIZATION_CHAT_NOISE:
        return False

    if _has_uppercase_signal(item.text):
        return True

    padded = f" {normalized}"
    return any(padded.endswith(suffix) for suffix in _ORGANIZATION_SUFFIXES)


def _add_contextual_person(
    text: str,
    merged: list[Finding],
    *,
    start: int,
    end: int,
    value: str,
) -> list[Finding]:
    if any(
        item.entity_type == "PERSON"
        and item.start <= start
        and item.end >= end
        for item in merged
    ):
        return merged

    merged = [
        item
        for item in merged
        if not (
            item.entity_type == "ORGANIZATION"
            and _overlaps(item, start, end)
        )
    ]

    context_start = max(0, start - 32)
    context_end = min(len(text), end + 32)
    merged.append(
        Finding(
            finding_id=f"browser-person-{start}-{end}",
            entity_type="PERSON",
            text=value,
            start=start,
            end=end,
            score=0.98,
            page_number=1,
            context=text[context_start:context_end],
        )
    )
    return merged


def augment_browser_findings(
    text: str,
    findings: tuple[Finding, ...],
    *,
    language: str | None = None,
) -> tuple[Finding, ...]:
    """Refine NER findings for short EN/IT browser-chat prompts.

    Browser chat uses a conservative interruption policy for statistical
    PERSON/ORGANIZATION findings: weak lowercase NER guesses are allowed to
    pass, while explicit name/address/relationship context and stronger
    name/company shapes still trigger review. Document analysis is left
    untouched.
    """

    merged = []
    for item in findings:
        if item.entity_type == "PERSON" and not _keep_statistical_person(item):
            continue
        if item.entity_type == "ORGANIZATION" and not _keep_statistical_organization(item):
            continue
        merged.append(item)

    for match in _CONTEXTUAL_PERSON_PATTERN.finditer(text):
        start, end = match.span("person")
        merged = _add_contextual_person(
            text,
            merged,
            start=start,
            end=end,
            value=match.group("person"),
        )

    if language == "it":
        for pattern in (
            _ITALIAN_RELATIONAL_PERSON_PATTERN,
            _ITALIAN_RELATIONAL_PERSON_REVERSE_PATTERN,
        ):
            for match in pattern.finditer(text):
                start, end = match.span("person")
                merged = _add_contextual_person(
                    text,
                    merged,
                    start=start,
                    end=end,
                    value=match.group("person"),
                )

        for match in _ITALIAN_STREET_PATTERN.finditer(text):
            start, end = match.span(0)
            value = match.group(0)

            if any(
                item.entity_type == "STREET_ADDRESS"
                and item.start <= start
                and item.end >= end
                for item in merged
            ):
                continue

            merged = [
                item
                for item in merged
                if not (
                    item.entity_type in {"PERSON", "ORGANIZATION", "LOCATION"}
                    and _overlaps(item, start, end)
                )
            ]

            context_start = max(0, start - 32)
            context_end = min(len(text), end + 32)
            merged.append(
                Finding(
                    finding_id=f"browser-street-{start}-{end}",
                    entity_type="STREET_ADDRESS",
                    text=value,
                    start=start,
                    end=end,
                    score=0.97,
                    page_number=1,
                    context=text[context_start:context_end],
                )
            )

    return tuple(
        sorted(
            merged,
            key=lambda item: (item.page_number, item.start, item.end, item.entity_type),
        )
    )
