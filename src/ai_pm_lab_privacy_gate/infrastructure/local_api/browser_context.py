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

_ITALIAN_STREET_PATTERN = re.compile(
    r"\b(?i:via|viale|piazza|corso|largo|vicolo)\s+"
    r"(?P<street>[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,49}"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,49}){0,3})"
)

# Short conversational words are occasionally mislabeled as organizations by
# multilingual/statistical NER. Keep this deliberately small and explicit.
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


def _normalized_chat_value(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _overlaps(item: Finding, start: int, end: int) -> bool:
    return item.start < end and start < item.end


def augment_browser_findings(
    text: str,
    findings: tuple[Finding, ...],
    *,
    language: str | None = None,
) -> tuple[Finding, ...]:
    """Refine NER findings for short EN/IT browser-chat prompts.

    The browser layer intentionally fixes only high-confidence conversational
    cases. Document analysis is left untouched.
    """

    merged = [
        item
        for item in findings
        if not (
            item.entity_type == "ORGANIZATION"
            and _normalized_chat_value(item.text) in _ORGANIZATION_CHAT_NOISE
        )
    ]

    for match in _CONTEXTUAL_PERSON_PATTERN.finditer(text):
        start, end = match.span("person")
        value = match.group("person")

        if any(
            item.entity_type == "PERSON"
            and item.start <= start
            and item.end >= end
            for item in merged
        ):
            continue

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

    if language == "it":
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
