from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, Finding


_NER_ENTITIES = {"PERSON", "ORGANIZATION", "LOCATION"}

# xx_ent_wiki_sm is intentionally a compact multilingual baseline. It is useful
# for natural names and places, but it is not precise enough to trust every raw
# PER/ORG/LOC prediction in form-like Italian business documents. The rules below
# are therefore precision-first: deterministic Italian recognizers keep priority,
# while obvious headings, field labels and UI/instruction language are suppressed.
_BLOCKED_EXACT = {
    "appendice a",
    "campo",
    "cap",
    "cart",
    "carta",
    "categorie",
    "centralino",
    "codice fiscale",
    "completamente fittizi",
    "dati",
    "dati catastali",
    "documenti di identità",
    "documento sintetico di test",
    "enable editing",
    "foglio",
    "iban",
    "imprese",
    "italiano",
    "location",
    "mappale",
    "organization",
    "particella",
    "pec",
    "person",
    "privacy check",
    "procedura consigliata di test",
    "protected view",
    "provincia",
    "rea",
    "registro imprese",
    "sezione",
    "sezione catastale",
    "subalterno",
    "synthetic",
    "synthetic test data only",
    "targa",
    "targa veicolo",
    "telefono",
    "test",
    "valore sintetico",
}
_BLOCKED_PREFIXES = (
    "appendice ",
    "categorie che ",
    "document language",
    "procedura consigliata",
    "synthetic test ",
)
# Generic NER sometimes returns a wider span than the exact checklist label, for
# example ``REA/Registro Imprese`` or ``provincia. Dati``. These are still schema
# language, not private values. Deterministic recognizers own real identifiers.
_BLOCKED_STRUCTURAL_FRAGMENTS = (
    "carta identità",
    "carta d'identità",
    "codice fiscale",
    "dati catastali",
    "documenti di identità",
    "partita iva",
    "passaporto",
    "patente",
    "postal_code",
    "provincia",
    "registro imprese",
    "street_address",
    "targa veicolo",
)
_INSTRUCTION_FIRST_WORDS = {
    "aprire",
    "caricare",
    "controllare",
    "eseguire",
    "generare",
    "lasciare",
    "salvare",
    "scaricare",
    "selezionare",
    "usare",
    "verificare",
}
_LEGAL_SUFFIX_RE = re.compile(
    r"(?:\bs\.?\s*r\.?\s*l\.?\b|\bs\.?\s*p\.?\s*a\.?\b|\bsnc\b|\bsas\b)",
    re.IGNORECASE,
)
_SCHEMA_TOKEN_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")


def _normalise_label(value: str) -> str:
    value = " ".join(value.split()).casefold()
    return value.strip(" \t\r\n:;,.()[]{}–—-")


def _alpha_words(value: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ'’]+", value)


def is_italian_ner_false_positive(entity_type: str, value: str) -> bool:
    """Return True for high-confidence structural mistakes from generic NER."""
    if entity_type not in _NER_ENTITIES:
        return False
    raw = value.strip().strip(" :;,.()[]{}")
    if _SCHEMA_TOKEN_RE.fullmatch(raw):
        # PrivacyGate/category schema names such as IT_FISCAL_CODE,
        # STREET_ADDRESS or POSTAL_CODE are labels, never document values.
        return True
    clean = _normalise_label(value)
    if not clean:
        return True
    if clean in _BLOCKED_EXACT or clean.startswith(_BLOCKED_PREFIXES):
        return True
    if any(fragment in clean for fragment in _BLOCKED_STRUCTURAL_FRAGMENTS):
        return True
    if "privacygate" in clean or "documento sintetico" in clean:
        return True

    # A legal company suffix is strong deterministic evidence that the span is a
    # business entity, never a person's name. The dedicated organization
    # recognizer owns these values with higher confidence.
    if entity_type == "PERSON" and _LEGAL_SUFFIX_RE.search(value):
        return True

    words = _alpha_words(value)
    if entity_type in {"PERSON", "ORGANIZATION"} and len(words) < 2:
        # Single-word PER/ORG predictions are the dominant source of damage from
        # xx_ent_wiki_sm on forms. Explicit Italian role/company recognizers
        # recover the important contextual cases.
        return True

    if entity_type == "ORGANIZATION":
        first = clean.split(" ", 1)[0]
        if first in _INSTRUCTION_FIRST_WORDS:
            return True
        letters = "".join(char for char in value if char.isalpha())
        if letters and letters.isupper() and not _LEGAL_SUFFIX_RE.search(value):
            return True
        if clean.startswith(("privacy check", "scan & protect", "scan and protect")):
            return True

    if entity_type == "LOCATION" and re.fullmatch(
        r"[A-Z]?\d+[A-Z0-9]*", value.strip(), re.IGNORECASE
    ):
        # Cadastral/reference codes are handled by deterministic recognizers.
        return True
    return False


def _is_compact_ner_result(result: Any) -> bool:
    """Distinguish spaCy NER output from PrivacyGate deterministic recognizers."""
    metadata = getattr(result, "recognition_metadata", None) or {}
    recognizer_name = str(
        metadata.get("recognizer_name")
        or metadata.get("recognizer_identifier")
        or ""
    ).casefold()
    return not recognizer_name or "spacy" in recognizer_name or "nlp" in recognizer_name


def filter_italian_ner_results(text: str, results: Iterable[Any]) -> list[Any]:
    """Filter compact-model mistakes while leaving deterministic results intact."""
    filtered: list[Any] = []
    for result in results:
        if not _is_compact_ner_result(result):
            filtered.append(result)
            continue
        value = text[result.start : result.end]
        if is_italian_ner_false_positive(str(result.entity_type), value):
            continue
        filtered.append(result)
    return filtered


_ADJACENT_FIELDS: tuple[tuple[str, frozenset[str], re.Pattern[str], float], ...] = (
    (
        "IT_CADASTRAL_MUNICIPAL_CODE",
        frozenset({"comune catastale", "codice catastale", "codice comune"}),
        re.compile(r"[A-Z0-9]{4,5}", re.IGNORECASE),
        0.995,
    ),
    (
        "IT_CADASTRAL_SECTION",
        frozenset({"sezione", "sezione catastale", "sezione urbana"}),
        re.compile(r"[A-Z0-9]{1,4}", re.IGNORECASE),
        0.99,
    ),
    (
        "IT_CADASTRAL_SHEET",
        frozenset({"foglio", "foglio catastale"}),
        re.compile(r"\d{1,5}"),
        0.995,
    ),
    (
        "IT_CADASTRAL_PARCEL",
        frozenset({"particella", "mappale", "particella / mappale", "particella/mappale"}),
        re.compile(r"\d{1,5}(?:\s*/\s*\d{1,4})?"),
        0.995,
    ),
    (
        "IT_CADASTRAL_SUBALTERN",
        frozenset({"subalterno", "sub"}),
        re.compile(r"[A-Z0-9]{1,6}", re.IGNORECASE),
        0.995,
    ),
    (
        "IT_POSTAL_CODE",
        frozenset({"cap", "codice di avviamento postale"}),
        re.compile(r"\d{5}"),
        0.99,
    ),
    (
        "IT_PROVINCE",
        frozenset({"provincia", "prov"}),
        re.compile(r"[A-Z]{2}"),
        0.99,
    ),
)


def adjacent_segment_findings(document: AnalysisDocument) -> tuple[Finding, ...]:
    """Recognize label/value pairs split across adjacent Word/Excel segments."""
    pages = tuple(document.pages)
    additions: list[Finding] = []
    for index in range(1, len(pages)):
        previous = pages[index - 1]
        current = pages[index]
        label = _normalise_label(previous.text).replace(".", "")
        value = current.text.strip()
        if not value:
            continue
        for entity_type, labels, pattern, score in _ADJACENT_FIELDS:
            if label not in labels or pattern.fullmatch(value) is None:
                continue
            start = current.text.find(value)
            end = start + len(value)
            additions.append(
                Finding(
                    finding_id=(
                        f"it-adjacent-{current.page_number}-{start}-{end}-{entity_type}"
                    ),
                    entity_type=entity_type,
                    text=current.text[start:end],
                    start=start,
                    end=end,
                    score=score,
                    page_number=current.page_number,
                    context=f"{previous.text} {current.text}",
                )
            )
            break
    return tuple(additions)


def propagate_known_ner_values(
    document: AnalysisDocument,
    findings: Iterable[Finding],
) -> tuple[Finding, ...]:
    """Protect repeated PERSON/ORG/LOCATION values consistently across segments."""
    base = list(findings)
    existing = {(item.page_number, item.start, item.end) for item in base}
    seeds: dict[tuple[str, str], Finding] = {}
    for item in base:
        if item.entity_type not in _NER_ENTITIES:
            continue
        value = " ".join(item.text.split()).strip()
        if len(value) < 3 or not any(char.isalpha() for char in value):
            continue
        if is_italian_ner_false_positive(item.entity_type, value):
            continue
        key = (item.entity_type, value.casefold())
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
                radius = 34
                additions.append(
                    Finding(
                        finding_id=(
                            f"it-repeat-{page.page_number}-{match.start()}-"
                            f"{match.end()}-{entity_type}"
                        ),
                        entity_type=entity_type,
                        text=page.text[match.start() : match.end()],
                        start=match.start(),
                        end=match.end(),
                        score=max(float(seed.score), 0.86),
                        page_number=page.page_number,
                        context=page.text[
                            max(0, match.start() - radius) : min(
                                len(page.text), match.end() + radius
                            )
                        ],
                    )
                )
    return tuple(base + additions)
