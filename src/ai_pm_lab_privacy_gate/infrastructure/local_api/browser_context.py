from __future__ import annotations

import re

from ai_pm_lab_privacy_gate.domain.models import Finding


# Browser chat is often short and informal, which makes statistical NER less
# reliable than on documents. These narrow patterns only cover explicit
# self/name labels; they are not a general "capitalized word = person" rule.
_CONTEXTUAL_PERSON_PATTERN = re.compile(
    r"\b(?i:my\s+name\s+is|name(?:\s+is)?|nome(?:\s+(?:è|e'))?|mi\s+chiamo)"
    r"\s*[:\-]?\s*"
    r"(?P<person>[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,39}"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,39}){0,2})"
)


def augment_browser_findings(text: str, findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    """Add high-confidence PERSON findings for explicit EN/IT name phrases.

    This is intentionally browser-only. It improves short chat prompts such as
    ``name pietro`` or ``mi chiamo Pietro`` without changing document analysis.
    If the statistical NER labeled the same span as ORGANIZATION, the explicit
    name context wins to avoid duplicate/conflicting review rows.
    """

    merged = list(findings)

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
                and item.start < end
                and start < item.end
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

    return tuple(
        sorted(
            merged,
            key=lambda item: (item.page_number, item.start, item.end, item.entity_type),
        )
    )
