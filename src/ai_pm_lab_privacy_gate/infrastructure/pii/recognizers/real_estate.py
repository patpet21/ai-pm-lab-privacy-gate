from __future__ import annotations

import re
from dataclasses import dataclass

from presidio_analyzer import EntityRecognizer, Pattern, PatternRecognizer, RecognizerResult


@dataclass(frozen=True, slots=True)
class ContextRule:
    entity_type: str
    pattern: str
    score: float = 0.97


class ContextValueRecognizer(EntityRecognizer):
    """Recognize the value following an explicit business label.

    Presidio's generic numeric recognizers deliberately reject some synthetic
    identifiers and can confuse account numbers with dates or phone numbers.
    These rules only fire when a clear label is present, and return the span of
    the value (not the label), keeping false positives low.
    """

    def __init__(self, rule: ContextRule) -> None:
        super().__init__(supported_entities=[rule.entity_type], supported_language="en")
        self._rule = rule
        self._regex = re.compile(rule.pattern, re.IGNORECASE | re.MULTILINE)

    def load(self) -> None:
        return None

    def analyze(self, text, entities, nlp_artifacts=None):  # noqa: ANN001
        if self._rule.entity_type not in entities:
            return []
        results: list[RecognizerResult] = []
        for match in self._regex.finditer(text):
            start, end = match.span("value")
            results.append(
                RecognizerResult(
                    entity_type=self._rule.entity_type,
                    start=start,
                    end=end,
                    score=self._rule.score,
                    recognition_metadata={
                        RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                    },
                )
            )
        return results


_LABEL_SEPARATOR = r"\s*(?::|#|number\b|no\.?\b)?\s*"


CONTEXT_RULES = (
    ContextRule(
        "US_SSN",
        rf"(?:ssn|social\s+security(?:\s+number)?)\b{_LABEL_SEPARATOR}(?P<value>\d{{3}}-\d{{2}}-\d{{4}})\b",
    ),
    ContextRule(
        "US_DRIVER_LICENSE",
        rf"(?:driver(?:'s|s)?\s+licen[cs]e|driver\s+licen[cs]e|dl)\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9 -]{{5,17}}[A-Z0-9])\b",
    ),
    ContextRule(
        "US_PASSPORT",
        rf"passport(?:\s+(?:number|no\.?))?(?=\s|:|#){_LABEL_SEPARATOR}(?P<value>[A-Z0-9]{{6,12}})\b",
    ),
    ContextRule(
        "US_ROUTING_NUMBER",
        rf"(?:(?:aba\s+)?routing(?:\s+number)?)\b{_LABEL_SEPARATOR}(?P<value>\d{{9}})\b",
    ),
    ContextRule(
        "US_BANK_NUMBER",
        rf"(?:bank|checking|savings)\s+account(?:\s+(?:number|no\.?))?\b{_LABEL_SEPARATOR}(?P<value>\d{{6,17}})\b",
    ),
    ContextRule(
        "TENANT_ID",
        rf"tenant\s+(?:id|identifier)\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
    ),
    ContextRule(
        "LEASE_ID",
        rf"lease\s+(?:id|identifier|number|no\.?)\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
    ),
    ContextRule(
        "NYC_BBL",
        rf"(?:nyc\s+)?bbl\b{_LABEL_SEPARATOR}(?P<value>[1-5]-?\d{{5}}-?\d{{4}})\b",
    ),
    ContextRule(
        "NYC_BIN",
        rf"(?:nyc\s+)?bin\b{_LABEL_SEPARATOR}(?P<value>\d{{7}})\b",
    ),
    ContextRule(
        "VENDOR_ACCOUNT_ID",
        rf"vendor\s+(?:(?:account)(?:\s+(?:id|identifier|number|no\.?))?|(?:id|identifier|number|no\.?))\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
    ),
    ContextRule(
        "WORK_ORDER_ID",
        rf"work\s+order(?:\s+(?:id|number|no\.?))?\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
    ),
    ContextRule(
        "PROPOSAL_ID",
        rf"proposal(?:\s+(?:id|number|no\.?))?\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
    ),
    ContextRule(
        "INSURANCE_POLICY_ID",
        rf"(?:insurance\s+)?policy(?:\s+(?:id|number|no\.?))?\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
    ),
    ContextRule(
        "PREAPPROVAL_ID",
        rf"pre-?approval(?:\s+(?:id|reference|number|no\.?))?\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
    ),
    ContextRule(
        "MORTGAGE_REFERENCE",
        rf"mortgage(?:\s+(?:id|reference|number|no\.?))?\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
    ),
)


def install_real_estate_recognizers(registry) -> None:  # noqa: ANN001
    for rule in CONTEXT_RULES:
        registry.add_recognizer(ContextValueRecognizer(rule))

    # PDF text extraction can insert line breaks inside a telephone number.
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            supported_language="en",
            patterns=[
                Pattern(
                    name="us_phone_with_pdf_whitespace",
                    regex=r"(?<!\d)(?:\+?1[\s.()-]*)?(?:\(\s*\d{3}\s*\)|\d{3})[\s.()-]+\d{3}[\s.-]+\d{4}(?!\d)",
                    score=0.88,
                )
            ],
        )
    )

    # Stable sector prefixes remain safe to recognize when an identifier is
    # repeated in narrative text without its original label.
    prefixed_patterns = {
        "TENANT_ID": r"\bTEN-[A-Z0-9-]{4,30}\b",
        "LEASE_ID": r"\bLEASE-[A-Z0-9-]{4,30}\b",
        "VENDOR_ACCOUNT_ID": r"\bVND-[A-Z0-9-]{4,30}\b",
        "WORK_ORDER_ID": r"\bWO-[A-Z0-9-]{4,30}\b",
        "PROPOSAL_ID": r"\bPROP-[A-Z0-9-]{4,30}\b",
        "INSURANCE_POLICY_ID": r"\bCGL-[A-Z0-9-]{4,30}\b",
        "PREAPPROVAL_ID": r"\bPA-[A-Z0-9-]{4,30}\b",
        "MORTGAGE_REFERENCE": r"\bMTG-[A-Z0-9-]{4,30}\b",
        "NYC_BBL": r"\b[1-5]-\d{5}-\d{4}\b",
    }
    for entity_type, regex in prefixed_patterns.items():
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity=entity_type,
                supported_language="en",
                patterns=[Pattern(name=f"structured_{entity_type.lower()}", regex=regex, score=0.93)],
            )
        )
