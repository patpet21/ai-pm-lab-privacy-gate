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


_LABEL_SEPARATOR = r"[ \t]*(?::|=|#|number\b|no\.?\b)?[ \t]*"


# Privacy Gate Real Estate expansion helpers.
# Keep these patterns contextual: the goal is higher recall without turning
# ordinary numbers, words or public real-estate facts into sensitive findings.
_PERSON_TOKEN = r"(?!(?:LLC|L\.L\.C\.?|Inc\.?|Corp\.?|Corporation|Company|Co\.?|Holdings|Management|Solutions|Services|Group|Bank|Realty|Properties)\b)[A-Z][A-Za-z'’.-]{1,30}"
_PERSON_NAME = rf"(?-i:{_PERSON_TOKEN}(?:[ \t]+(?:{_PERSON_TOKEN}|[A-Z]\.)){{1,3}})"
_ACCOUNT_VALUE = r"\d(?:[\s-]?\d){5,16}"
_CODE_VALUE = r"(?=[A-Z0-9#*.-]*\d)[A-Z0-9#*.-]{3,24}"
_CODE_END = r"(?=$|[\s,;.)\]\}])"
_STREET_VALUE = r"\d{1,6}\s+(?:[A-Z0-9.'’#-]+\s+){1,8}(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Lane|Ln\.?|Drive|Dr\.?|Court|Ct\.?|Parkway|Pkwy\.?|Place|Pl\.?|Terrace|Ter\.?|Way)\b[^\r\n,;]{0,40}"


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
        "US_PASSPORT",
        r"passport(?:[ \t]+(?:number|no\.?))?[ \t]*(?::|#)?[ \t]*\r?\n[ \t]*(?P<value>(?=[A-Z0-9]{0,11}\d)[A-Z0-9]{6,12})\b",
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
        "TENANT_ID",
        rf"(?:resident\s+(?:account|id)|occupancy\s+id|tenant\s+ref\.?)\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
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
    ContextRule(
        "US_EIN",
        rf"(?:ein|employer\s+identification(?:\s+number)?|federal\s+tax\s+id)\b{_LABEL_SEPARATOR}(?P<value>\d{{2}}-\d{{7}})\b",
    ),
    ContextRule(
        "PROPERTY_IDENTIFIER",
        rf"(?:property|parcel|apn|asset|portfolio)\s+(?:id|identifier|number|no\.?|ref\.?)\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
    ),
    ContextRule(
        "UNIT_NUMBER",
        rf"(?:apartment|apt\.?|unit)\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{0,9}})\b",
        score=0.91,
    ),
    ContextRule(
        "UNIT_NUMBER",
        r"(?:apartment|apt\.?|unit)(?:[ \t]+number)?[ \t]*(?::|#|=)?[ \t]*\r?\n[ \t]*(?P<value>(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{0,9})\b",
        score=0.91,
    ),
    ContextRule(
        "PROPERTY_ACCESS_CODE",
        rf"(?:building|property|door|gate|entry)\s+(?:access\s+)?code\b{_LABEL_SEPARATOR}(?P<value>{_CODE_VALUE}){_CODE_END}",
    ),
    ContextRule(
        "LOCKBOX_CODE",
        rf"lock\s*box(?:\s+(?:code|combination|combo|pin))?\b{_LABEL_SEPARATOR}(?P<value>{_CODE_VALUE}){_CODE_END}",
    ),
    ContextRule(
        "CONTRACTOR_LICENSE",
        rf"contractor(?:'s)?\s+licen[cs]e(?:\s+(?:id|number|no\.?))?\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{4,30}})\b",
    ),
    ContextRule(
        "INSURANCE_CLAIM_ID",
        rf"(?:insurance\s+)?claim(?:\s+(?:id|reference|number|no\.?))?\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
    ),
    ContextRule(
        "UTILITY_ACCOUNT_ID",
        rf"(?:electric|gas|water|utility)\s+account(?:\s+(?:id|number|no\.?))?\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{4,30}})\b",
    ),
    ContextRule(
        "LOAN_NUMBER",
        rf"loan(?:\s+(?:id|number|no\.?))\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{4,30}})\b",
    ),
    ContextRule(
        "TRANSACTION_ID",
        rf"(?:transaction|closing|deal)\s+(?:id|reference|number|no\.?)\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
    ),

    # ---- Privacy Gate Real Estate expansion v2: existing entity types ----
    # Bank/account forms often appear in tables and can resemble phone numbers.
    # These high-confidence rules ensure the contextual bank entity wins overlap resolution.
    ContextRule(
        "US_BANK_NUMBER",
        rf"(?:acct\.?|a/c|account|bank\s+account|checking\s+account|savings\s+account)\s*(?:number|no\.?|#)?\s*[:#-]?\s*(?P<value>{_ACCOUNT_VALUE})(?=\s*(?:[-–—|,;]?\s*(?:aba\b|routing\b|rtn\b)|$|\r?$))",
        score=0.998,
    ),
    ContextRule(
        "US_BANK_NUMBER",
        rf"(?:operating|security\s+deposit|reserve|escrow|trust|owner|vendor)\s+account[^\r\n]{{0,80}}?\b(?:acct\.?|account)\s*[:#-]?\s*(?P<value>{_ACCOUNT_VALUE})(?=\s*(?:[-–—|,;]?\s*(?:aba\b|routing\b|rtn\b)|$|\r?$))",
        score=0.998,
    ),
    ContextRule(
        "US_ROUTING_NUMBER",
        rf"(?:aba(?:\s+routing)?|routing(?:\s+(?:number|no\.?))?|routing\s*/\s*aba|aba\s*/\s*routing|rtn)\b\s*[:#-]?\s*(?P<value>\d{{9}})\b",
        score=0.998,
    ),
    # Access codes ending in # or * do not have a regex word boundary, so use a look-ahead.
    ContextRule(
        "PROPERTY_ACCESS_CODE",
        rf"(?:building|property|door|gate|entry|front[- ]?entry|service\s+entrance|superintendent\s+(?:service\s+)?entrance|garage|intercom|keypad|vestibule|lobby|roof)\s+(?:access\s+|entry\s+)?(?:code|pin)\b\s*[:#=-]?\s*(?P<value>{_CODE_VALUE}){_CODE_END}",
        score=0.998,
    ),
    ContextRule(
        "PROPERTY_ACCESS_CODE",
        rf"(?:access|entry|door|gate|intercom|keypad)\s+(?:code|pin)\b\s*[:#=-]?\s*(?P<value>{_CODE_VALUE}){_CODE_END}",
        score=0.995,
    ),
    ContextRule(
        "LOCKBOX_CODE",
        rf"(?:lock\s*box|key\s*box)(?:[^\r\n]{{0,35}}?)(?:code|combination|combo|pin)\b\s*[:#=-]?\s*(?P<value>{_CODE_VALUE}){_CODE_END}",
        score=0.998,
    ),
    ContextRule(
        "LOCKBOX_CODE",
        rf"(?:box\s*\d+\s*[-–—:]?\s*)?(?:lock\s*box\s*)?(?:combination|combo)\b\s*[:#=-]?\s*(?P<value>{_CODE_VALUE}){_CODE_END}",
        score=0.996,
    ),
    # Property-specific address labels catch addresses that generic NLP may miss in tables.
    ContextRule(
        "STREET_ADDRESS",
        rf"(?:property|premises|subject\s+property|mailing|billing|prior|previous|forwarding|service|site)\s+address\b\s*[:#-]?\s*(?P<value>{_STREET_VALUE})",
        score=0.97,
    ),
    # Real-estate role labels: deliberately limited to person-oriented labels.
    ContextRule(
        "PERSON",
        rf"(?:resident\s+contact|tenant|resident|applicant|borrower|buyer|seller|guarantor|insured|technician|project\s+manager|authorized\s+signer|administrator|superintendent|managing\s+member|emergency\s+contact|broker\s+contact|contact\s+person|requested\s+by|approved\s+by|assigned\s+to|submitted\s+by|prepared\s+by)\b[ \t]*[:#-]?[ \t]*(?P<value>{_PERSON_NAME})(?=[ \t]*(?:[,;|/]|\r?$|\b(?:email|phone|tenant\s+id|resident\s+id|dob)\b))",
        score=0.96,
    ),
    # Rent-roll rows: Unit + Person + structured tenant/resident ID.
    ContextRule(
        "PERSON",
        rf"(?im)^\s*(?:\d{{1,3}}[A-Z]?|[A-Z]\d{{1,3}}|[A-Z]{{1,2}}\d{{1,3}})\s+(?P<value>{_PERSON_NAME})\s+(?=(?:TEN|RES)-[A-Z0-9-]{{3,30}}\b)",
        score=0.985,
    ),
    # Identity-table rows: Person / Unit followed by DOB.
    ContextRule(
        "PERSON",
        rf"(?im)^\s*(?P<value>{_PERSON_NAME})\s*/\s*[A-Z0-9-]{{1,8}}\s+(?=\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}\b)",
        score=0.985,
    ),
    # Contact-table rows where a person's name sits directly before an email address.
    ContextRule(
        "PERSON",
        rf"(?im)(?P<value>{_PERSON_NAME})\s+(?=[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{{2,}}\b)",
        score=0.91,
    ),
    ContextRule(
        "PERSON",
        rf"(?im)(?P<value>{_PERSON_NAME})\s+(?=(?:called|emailed|reported|requested|stated|advised|confirmed|asked|provided|submitted|signed|authorized|approved|declined|indicated)\b)",
        score=0.93,
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
        "PROPERTY_IDENTIFIER": r"\b(?:PROPERTY|APN)-[A-Z0-9-]{4,30}\b",
        "INSURANCE_CLAIM_ID": r"\bCLM-[A-Z0-9-]{4,30}\b",
        "UTILITY_ACCOUNT_ID": r"\bUTIL-[A-Z0-9-]{4,30}\b",
        "LOAN_NUMBER": r"\bLOAN-[A-Z0-9-]{4,30}\b",
        "TRANSACTION_ID": r"\b(?:TXN|CLOSE)-[A-Z0-9-]{4,30}\b",
    }
    for entity_type, regex in prefixed_patterns.items():
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity=entity_type,
                supported_language="en",
                patterns=[Pattern(name=f"structured_{entity_type.lower()}", regex=regex, score=0.93)],
            )
        )
