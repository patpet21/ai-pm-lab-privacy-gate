from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, Finding


_NER_ENTITIES = {"PERSON", "ORGANIZATION", "LOCATION"}

# xx_ent_wiki_sm is a deliberately small multilingual baseline. It is useful for
# names/places/organisations, but on form-like Italian documents it can classify
# field labels as entities. These are structural/privacy vocabulary, not values.
_BLOCKED_EXACT = {
    "appendice a",
    "campo",
    "cap",
    "categorie",
    "centralino",
    "codice fiscale",
    "documento sintetico di test",
    "foglio",
    "imprese",
    "italiano",
    "location",
    "mappale",
    "organization",
    "particella",
    "person",
    "provincia",
    "registro imprese",
    "sezione",
    "sezione catastale",
    "subalterno",
    "synthetic test data only",
    "targa",
    "targa veicolo",
    "telefono",
    "valore sintetico",
}
_BLOCKED_PREFIXES = (
    "appendice ",
    "categorie che ",
    "document language",
    "synthetic test ",
)


def _normalise_label(value: str) -> str:
    value = " ".join(value.split()).casefold()
    return value.strip(" \t\r\n:;,.()[]{}–—-")


def is_italian_ner_false_positive(entity_type: str, value: str) -> bool:
    """Reject obvious form/document labels produced by the compact NER model."""
    if entity_type not in _NER_ENTITIES:
        return False
    clean = _normalise_label(value)
    if not clean:
        return True
    if clean in _BLOCKED_EXACT or clean.startswith(_BLOCKED_PREFIXES):
        return True
    if "privacygate" in clean or "documento sintetico" in clean:
        return True
    if entity_type == "LOCATION" and re.fullmatch(r"[A-Z]?\d+[A-Z0-9]*", value.strip(), re.I):
        # Cadastral/reference codes are handled by deterministic recognizers.
        return True
    if entity_type == "PERSON" and clean in {
        "codice fiscale",
        "foglio",
        "telefono",
        "targa",
    }:
        return True
    return False


def filter_italian_ner_results(text: str, results: Iterable[Any]) -> list[Any]:
    """Filter only obvious generic-NER mistakes; deterministic entities are untouched."""
    filtered: list[Any] = []
    for result in results:
        value = text[result.start : result.end]
        if is_italian_ner_false_positive(str(result.entity_type), value):
            continue
        filtered.append(result)
    return filtered


_ADJACENT_FIELDS: tuple[tuple[str, frozenset[str], re.Pattern[str], float], ...] = (
    (
        "IT_CADASTRAL_MUNICIPAL_CODE",
        frozenset({"comune catastale", "codice catastale", "codice comune"}),
        re.compile(r"[A-Z0-9]{4,5}", re.I),
        0.995,
    ),
    (
        "IT_CADASTRAL_SECTION",
        frozenset({"sezione", "sezione catastale", "sezione urbana"}),
        re.compile(r"[A-Z0-9]{1,4}", re.I),
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
        re.compile(r"[A-Z0-9]{1,6}", re.I),
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
    """Recognize label/value pairs split across adjacent Word/Excel segments.

    OfficeDocumentService intentionally keeps each editable paragraph/cell as an
    independent segment so protected values can be written back without damaging
    layout. Tables therefore often expose ``Foglio`` and ``123`` as two adjacent
    segments. This helper adds deterministic context without merging those
    segments or changing their offsets.
    """
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
    """Protect repeated PERSON/ORG/LOCATION values consistently across segments.

    A compact NER model can recognize ``Milano`` in one sentence and miss the
    same city in a short causale. Once a value has been confidently recognized in
    this document, every exact standalone occurrence is privacy-equivalent and is
    therefore surfaced for review as well.
    """
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
