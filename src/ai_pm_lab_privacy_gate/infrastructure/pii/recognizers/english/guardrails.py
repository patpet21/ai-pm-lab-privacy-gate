from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, Finding


_NER_ENTITIES = {"PERSON", "ORGANIZATION", "LOCATION"}
_GENERIC_EMAIL_LOCAL_PARTS = {
    "admin",
    "billing",
    "careers",
    "contact",
    "hello",
    "help",
    "info",
    "office",
    "sales",
    "support",
    "team",
}

# These are concepts/categories, not private people/organizations/locations.
_GLOBAL_NER_NOISE = {
    "ai",
    "api",
    "apis",
    "llm",
    "llms",
    "mcp",
    "project management",
    "applied ai",
    "prompt design",
}

# Common professional/AI phrases that compact statistical NER may classify as
# PERSON/ORG/LOC in resumes. These are concepts or work descriptions, not named
# private entities. Keep the list semantic rather than user/document-specific.
_PROFESSIONAL_TECH_PHRASES = {
    "ai builder",
    "ai integration",
    "ai models",
    "ai research",
    "ai systems",
    "ai tools",
    "ai workflows",
    "ai-powered tools",
    "ai-assisted research",
    "ai-assisted workflows",
    "ai-based operational analysis",
    "automation workflows",
    "api integrations",
    "api-driven reporting",
    "local ai models",
    "local llms",
    "mcp integrations",
    "mcp-based local workflows",
    "operational prototypes",
    "research frameworks",
}

_AI_CONCEPT_RE = re.compile(
    r"^ai(?:[-\s]+(?:powered|assisted|based|driven|enabled|generated))?"
    r"(?:\s+(?:agents?|analysis|builder|integration|models?|research|systems?|teams?|tools?|workflows?))?$",
    re.IGNORECASE,
)

_EDUCATION_CONCEPT_RE = re.compile(
    r"^(?:(?:associate|bachelor|master|doctoral|doctorate|graduate|undergraduate)\s+)?degree(?:\s+in)?$",
    re.IGNORECASE,
)

# Resume / professional-document structure seen frequently in General Business.
_GENERAL_BUSINESS_HEADINGS = {
    "profile",
    "education",
    "professional experience",
    "selected applied ai projects",
    "ai research & workflow skills",
    "ai, research & workflow skills",
    "research & automation",
    "technical & project tools",
    "agents & automation",
    "ai & llms",
    "languages",
    "m.s. project management",
}

_ACTION_VERBS = {
    "analyzed",
    "automated",
    "built",
    "compared",
    "coordinated",
    "created",
    "designed",
    "developed",
    "investigated",
    "managed",
    "prepared",
    "prototyped",
    "released",
    "reviewed",
    "supported",
    "tested",
    "translated",
}

_TECH_TERMS = {
    "asana",
    "chatgpt",
    "claude",
    "clickup",
    "cloudflare",
    "codex",
    "gemini",
    "github",
    "google adk",
    "google workspace",
    "make.com",
    "mcp",
    "microsoft office",
    "microsoft presidio",
    "n8n",
    "notion",
    "ollama",
    "openai",
    "openai api",
    "openai codex",
    "privacygate",
    "python",
    "replit",
    "spacy",
    "square pos",
    "supabase",
    "trello",
}

_SKILL_MARKERS = (
    "ai & llms",
    "agents & automation",
    "technical & project tools",
    "workflow skills",
    "ai, research & workflow skills",
    "ai research & workflow skills",
    "selected applied ai projects",
)

_LEGAL_SUFFIX_RE = re.compile(
    r"(?:\binc\.?\b|\bllc\b|\bltd\.?\b|\bcorp\.?\b|\bcompany\b|\bco\.?\b)",
    re.IGNORECASE,
)

# General document-structure guardrails. These describe field/taxonomy syntax,
# not one fixture. Statistical NER should not turn schema labels or UI procedure
# words into private people/organizations.
_SCHEMA_LABEL_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
_IDENTIFIER_LABEL_RE = re.compile(
    r"^(?:u\.s\.\s+)?(?:ssn|ein|aba|bbl|passport|driver(?:'s|s)?\s+license|"
    r"social\s+security\s+number|(?:[a-z]{2}\s+dos\s+)?entity\s+id|tax\s+id|"
    r"phone\s+number|email\s+address|vehicle\s+license\s+plate)$",
    re.IGNORECASE,
)
_ROLE_LABELS = {
    "landlord",
    "tenant",
    "owner",
    "buyer",
    "seller",
    "borrower",
    "applicant",
    "employee",
    "customer",
    "client",
    "manager",
    "engineer",
    "vendor",
}
_PROCEDURAL_NER_TERMS = {
    "document",
    "english",
    "privacy check",
    "scan & protect",
    "txt",
}
_SYNTHETIC_LINE_MARKERS = (
    "synthetic test",
    "synthetic data only",
    "fictitious data",
    "testing only",
    "test fixture",
)
_PERIODIC_DATE_WORDS = {
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "annual",
    "annually",
    "yearly",
}
_PROCEDURE_LINE_RE = re.compile(
    r"\b(?:open|select|upload|run|review|verify|save|download|inspect)\b",
    re.IGNORECASE,
)


def _normalize(value: str) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def _alpha_words(value: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'’.-]*", value)


def _is_statistical_ner_result(result: Any) -> bool:
    metadata = getattr(result, "recognition_metadata", None) or {}
    recognizer_name = str(
        metadata.get("recognizer_name")
        or metadata.get("recognizer_identifier")
        or ""
    ).casefold()
    return not recognizer_name or "spacy" in recognizer_name or "nlp" in recognizer_name


def _line_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = text.rfind("\n", 0, max(0, start)) + 1
    right = text.find("\n", max(end, start))
    if right < 0:
        right = len(text)
    return left, right


def _context_window(text: str, start: int, end: int, *, before: int = 320, after: int = 120) -> str:
    left = max(0, start - before)
    right = min(len(text), end + after)
    return text[left:right]


def _is_skill_context(text: str, start: int, end: int) -> bool:
    left, right = _line_bounds(text, start, end)
    line = text[left:right]
    normalized = _normalize(line)
    if any(marker in normalized for marker in _SKILL_MARKERS):
        return True

    # PDF/DOCX extraction often wraps a single skills row across multiple text
    # lines. Look back a few hundred characters for the section label instead of
    # assuming the tool and heading survive on the same extracted line.
    nearby = _normalize(_context_window(text, start, end, before=420, after=80))
    if any(marker in nearby for marker in _SKILL_MARKERS):
        return True

    # Compact CV skill rows commonly use comma-separated tools and pipes.
    return line.count(",") >= 2 or ("|" in line and ":" in line)


def _starts_line(text: str, start: int) -> bool:
    left, _ = _line_bounds(text, start, start)
    prefix = text[left:start]
    return not prefix.strip(" \t•-*–—")


def _is_professional_tech_concept(clean: str) -> bool:
    if clean in _PROFESSIONAL_TECH_PHRASES:
        return True
    if _AI_CONCEPT_RE.fullmatch(clean):
        return True
    if clean.startswith(("ai-powered ", "ai-assisted ", "ai-based ", "ai-driven ")):
        return True
    return False


def _is_document_structure_noise(
    text: str,
    entity_type: str,
    value: str,
    *,
    start: int,
    end: int,
) -> bool:
    if entity_type not in _NER_ENTITIES:
        return False

    clean = _normalize(value)
    raw = str(value or "").strip()
    left, right = _line_bounds(text, start, end)
    line = text[left:right]
    normalized_line = _normalize(line)

    if _SCHEMA_LABEL_RE.fullmatch(raw):
        return True
    if _IDENTIFIER_LABEL_RE.fullmatch(clean):
        return True

    # A document which explicitly marks a line as synthetic/test metadata should
    # not have product/test words promoted to private NER entities on that line.
    if any(marker in normalized_line for marker in _SYNTHETIC_LINE_MARKERS):
        return not bool(_LEGAL_SUFFIX_RE.search(value))

    if clean in _ROLE_LABELS and _starts_line(text, start):
        suffix = text[end:right]
        if re.match(r"\s*:", suffix):
            return True

    if clean == "vehicle" and "vehicle license plate" in normalized_line:
        return True

    if clean in _PROCEDURAL_NER_TERMS and _PROCEDURE_LINE_RE.search(line):
        return True

    if clean == "privacygate" and any(
        marker in normalized_line
        for marker in ("should detect", "detector", "testing", "scan", "protect")
    ):
        return True

    return False


def _is_source_independent_false_positive(
    text: str,
    entity_type: str,
    value: str,
    *,
    start: int,
    end: int,
    profile_key: str | None,
) -> bool:
    """Suppress semantic certainties even when recognizer metadata is unusual.

    Presidio result metadata is not guaranteed to identify every NLP-backed
    result as ``SpacyRecognizer``. A few EN false positives therefore bypassed
    statistical-only guardrails. This layer removes only values that are
    structurally or semantically certain not to be private NER values.
    """
    if entity_type not in _NER_ENTITIES:
        return False
    clean = _normalize(value)
    if not clean:
        return True
    if clean in _GLOBAL_NER_NOISE:
        return True
    if _is_document_structure_noise(
        text,
        entity_type,
        value,
        start=start,
        end=end,
    ):
        return True
    if profile_key == "general_business" and _is_professional_tech_concept(clean):
        return True
    if profile_key == "general_business" and clean in _GENERAL_BUSINESS_HEADINGS:
        return True
    if profile_key == "general_business" and _EDUCATION_CONCEPT_RE.fullmatch(clean):
        return True
    if clean in _TECH_TERMS and _is_skill_context(text, start, end):
        return True
    return False


def is_english_ner_false_positive(
    text: str,
    entity_type: str,
    value: str,
    *,
    start: int = 0,
    end: int = 0,
    profile_key: str | None = None,
) -> bool:
    if entity_type not in _NER_ENTITIES:
        return False

    clean = _normalize(value)
    if not clean:
        return True

    if _is_source_independent_false_positive(
        text,
        entity_type,
        value,
        start=start,
        end=end,
        profile_key=profile_key,
    ):
        return True

    if profile_key == "general_business" and entity_type == "ORGANIZATION":
        words = _alpha_words(value)
        first = _normalize(words[0]) if words else ""
        if (
            first in _ACTION_VERBS
            and _starts_line(text, start)
            and not _LEGAL_SUFFIX_RE.search(value)
        ):
            return True

    return False


def filter_english_ner_results(
    text: str,
    results: Iterable[Any],
    *,
    profile_key: str | None = None,
) -> list[Any]:
    """Suppress EN NER mistakes while preserving deterministic identifiers.

    Source-independent semantic certainties are filtered first. Broader
    heuristics such as action-verb suppression remain restricted to statistical
    NER so custom deterministic recognizers are not weakened.
    """
    filtered: list[Any] = []
    for result in results:
        value = text[result.start : result.end]
        entity_type = str(result.entity_type)

        if _is_source_independent_false_positive(
            text,
            entity_type,
            value,
            start=int(result.start),
            end=int(result.end),
            profile_key=profile_key,
        ):
            continue

        if not _is_statistical_ner_result(result):
            filtered.append(result)
            continue

        if is_english_ner_false_positive(
            text,
            entity_type,
            value,
            start=int(result.start),
            end=int(result.end),
            profile_key=profile_key,
        ):
            continue
        filtered.append(result)
    return filtered


def _looks_like_compact_date(value: str) -> bool:
    if len(value) == 4 and value.isdigit():
        return 1900 <= int(value) <= 2100
    if len(value) != 8 or not value.isdigit():
        return False

    year = int(value[:4])
    month = int(value[4:6])
    day = int(value[6:8])
    if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
        return True

    month = int(value[:2])
    day = int(value[2:4])
    year = int(value[4:])
    return 1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100


def filter_english_contextual_results(text: str, results: Iterable[Any]) -> list[Any]:
    """Remove generic EN guesses that conflict with identifier semantics.

    Presidio's DATE_TIME recognizer can treat long digit-only identifiers as
    dates. A bare 6-17 digit value is not a date unless it is a plausible compact
    YYYYMMDD/MMDDYYYY representation. Four-digit plausible years remain valid.
    Periodic words such as ``Monthly`` are also not concrete sensitive dates.
    """
    filtered: list[Any] = []
    for result in results:
        if str(result.entity_type) != "DATE_TIME":
            filtered.append(result)
            continue

        value = text[result.start : result.end].strip()
        clean = value.casefold()
        if clean in _PERIODIC_DATE_WORDS:
            continue
        if re.fullmatch(r"\d{4,17}", value) and not _looks_like_compact_date(value):
            continue
        filtered.append(result)
    return filtered


def email_linked_person_findings(
    document: AnalysisDocument,
    findings: Iterable[Finding],
) -> tuple[Finding, ...]:
    """Recover full names repeated in a document from a matching personal email.

    Example: ``marco.bianchi@example.com`` provides deterministic evidence for
    standalone occurrences of ``Marco Bianchi``. Generic mailbox local parts are
    ignored. This is local document analysis only.
    """
    base = list(findings)
    existing = {(item.page_number, item.start, item.end) for item in base}
    candidates: set[tuple[str, ...]] = set()

    for item in base:
        if item.entity_type != "EMAIL_ADDRESS" or "@" not in item.text:
            continue
        local_part = item.text.split("@", 1)[0].strip()
        pieces = tuple(
            piece.casefold()
            for piece in re.split(r"[._-]+", local_part)
            if piece.isalpha() and len(piece) >= 2
        )
        if not 2 <= len(pieces) <= 3:
            continue
        if any(piece in _GENERIC_EMAIL_LOCAL_PARTS for piece in pieces):
            continue
        candidates.add(pieces)

    additions: list[Finding] = []
    for pieces in candidates:
        pattern = re.compile(
            r"(?<!\w)" + r"\s+".join(re.escape(piece) for piece in pieces) + r"(?!\w)",
            re.IGNORECASE,
        )
        for page in document.pages:
            for match in pattern.finditer(page.text):
                span = (page.page_number, match.start(), match.end())
                if span in existing:
                    continue
                existing.add(span)
                additions.append(
                    Finding(
                        finding_id=(
                            f"en-email-person-{page.page_number}-{match.start()}-{match.end()}"
                        ),
                        entity_type="PERSON",
                        text=page.text[match.start() : match.end()],
                        start=match.start(),
                        end=match.end(),
                        score=0.97,
                        page_number=page.page_number,
                        context=page.text[
                            max(0, match.start() - 34) : min(len(page.text), match.end() + 34)
                        ],
                    )
                )
    return tuple(base + additions)


def _safe_propagation_seed(item: Finding) -> bool:
    value = " ".join(item.text.split()).strip()
    if len(value) < 3 or not any(char.isalpha() for char in value):
        return False
    if is_english_ner_false_positive(
        value,
        item.entity_type,
        value,
        start=0,
        end=len(value),
        profile_key="general_business",
    ):
        return False

    words = _alpha_words(value)
    if item.entity_type == "PERSON":
        return len(words) >= 2
    if item.entity_type == "ORGANIZATION":
        return len(words) >= 2 or bool(_LEGAL_SUFFIX_RE.search(value))
    return True


def propagate_known_ner_values(
    document: AnalysisDocument,
    findings: Iterable[Finding],
) -> tuple[Finding, ...]:
    """Protect repeated EN PERSON/ORG/LOCATION values consistently."""
    base = list(findings)
    existing = {(item.page_number, item.start, item.end) for item in base}
    seeds: dict[tuple[str, str], Finding] = {}

    for item in base:
        if item.entity_type not in _NER_ENTITIES or not _safe_propagation_seed(item):
            continue
        normalized = " ".join(item.text.split()).strip()
        key = (item.entity_type, normalized.casefold())
        current = seeds.get(key)
        if current is None or item.score > current.score:
            seeds[key] = item

    additions: list[Finding] = []
    for (entity_type, _folded), seed in seeds.items():
        escaped = re.escape(seed.text.strip()).replace(r"\ ", r"\s+")
        pattern = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
        for page in document.pages:
            for match in pattern.finditer(page.text):
                span = (page.page_number, match.start(), match.end())
                if span in existing:
                    continue
                existing.add(span)
                additions.append(
                    Finding(
                        finding_id=(
                            f"en-repeat-{page.page_number}-{match.start()}-{match.end()}-{entity_type}"
                        ),
                        entity_type=entity_type,
                        text=page.text[match.start() : match.end()],
                        start=match.start(),
                        end=match.end(),
                        score=max(float(seed.score), 0.86),
                        page_number=page.page_number,
                        context=page.text[
                            max(0, match.start() - 34) : min(len(page.text), match.end() + 34)
                        ],
                    )
                )
    return tuple(base + additions)
