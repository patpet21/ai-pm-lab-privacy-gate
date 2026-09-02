from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.real_estate import (
    ContextRule,
    ContextValueRecognizer,
)


_SEP = r"\s*(?::|#|=|[-–—])?\s*"
_REQ_SEP = r"\s*(?::|#|=|[-–—])\s*"
_ID = r"(?=[A-Z0-9./-]*\d)[A-Z0-9][A-Z0-9./-]{2,39}"
_AMOUNT = r"(?:USD\s*|[$€£]\s*)?\d[\d,]*(?:\.\d{1,2})?"
_PERCENT_OR_AMOUNT = rf"(?:\d{{1,3}}(?:\.\d+)?\s*%|{_AMOUNT})"
_SECRET = r"[^\s,;]{4,128}"


# Precision-first recall additions. Every rule requires an explicit field label
# or domain phrase; no value-only guessing is introduced here.
CONTEXT_RULES = (
    ContextRule(
        "US_EIN",
        rf"(?:ein|employer\s+identification(?:\s+number)?|federal\s+tax\s+id)\b{_SEP}(?P<value>\d{{2}}-\d{{7}})\b",
        score=0.998,
    ),
    ContextRule(
        "US_SSN",
        rf"(?:ssn|social\s+security(?:\s+(?:number|no\.?))?)\b{_SEP}(?P<value>\d{{3}}-\d{{2}}-\d{{4}})\b",
        score=0.998,
    ),
    ContextRule(
        "US_ROUTING_NUMBER",
        rf"(?:aba(?:\s+routing)?|bank\s+routing(?:\s+(?:number|no\.?))?|routing(?:\s+(?:number|no\.?))?)\b{_SEP}(?P<value>\d{{9}})\b",
        score=0.998,
    ),
    ContextRule(
        "SWIFT_BIC",
        rf"(?:swift(?:\s*/\s*bic)?(?:\s+code)?|bic)\b{_SEP}(?P<value>[A-Z]{{6}}[A-Z0-9]{{2}}(?:[A-Z0-9]{{3}})?)\b",
        score=0.998,
    ),
    ContextRule(
        "CARD_LAST_FOUR",
        rf"(?:(?:visa|mastercard|amex|card)\s+)?ending(?:\s+in)?\b{_SEP}(?P<value>\d{{4}})\b",
        score=0.997,
    ),
    ContextRule(
        "CARD_LAST_FOUR",
        rf"(?:card\s+)?last\s+(?:four|4)\b{_SEP}(?P<value>\d{{4}})\b",
        score=0.997,
    ),
    ContextRule(
        "BUSINESS_REGISTRATION_NUMBER",
        rf"(?:business|company|registration)\s+(?:id|identifier|number|no\.?)\b{_SEP}(?P<value>{_ID})\b",
        score=0.997,
    ),
    ContextRule(
        "INVOICE_NUMBER",
        rf"(?:invoice|inv\.?)\s*(?:number|no\.?|id|#)?{_SEP}(?P<value>{_ID})\b",
        score=0.997,
    ),
    ContextRule(
        "PURCHASE_ORDER_ID",
        rf"(?:purchase\s+order|p\.?\s*o\.?)\s*(?:number|no\.?|id)?{_SEP}(?P<value>{_ID})\b",
        score=0.997,
    ),
    ContextRule(
        "CONTRACT_ID",
        rf"(?:agreement\s+)?contract(?:\s+(?:number|no\.?|id|reference))?{_SEP}(?P<value>{_ID})\b",
        score=0.997,
    ),
    ContextRule(
        "CUSTOMER_ID",
        rf"(?:customer|client)\s+(?:number|no\.?|id|identifier)\b{_SEP}(?P<value>{_ID})\b",
        score=0.997,
    ),
    ContextRule(
        "EMPLOYEE_ID",
        rf"employee\s+(?:number|no\.?|id|identifier)\b{_SEP}(?P<value>{_ID})\b",
        score=0.997,
    ),
    ContextRule(
        "CASE_REFERENCE",
        rf"case\s+(?:number|no\.?|id|reference)\b{_SEP}(?P<value>{_ID})\b",
        score=0.997,
    ),
    ContextRule(
        "HOUSING_LEGAL_CASE_ID",
        rf"(?:legal\s+matter|housing\s+court\s+index|docket|eviction\s+case)(?:\s+(?:id|number|no\.?|reference))?\b{_SEP}(?P<value>{_ID})\b",
        score=0.997,
    ),
    ContextRule(
        "TENANT_ID",
        rf"(?:tenant\s+(?:id|identifier)|resident\s+(?:account|id)|occupancy\s+id|tenant\s+ref\.?)\b{_SEP}(?P<value>{_ID})\b",
        score=0.997,
    ),
    ContextRule(
        "LEASE_ID",
        rf"lease\s+(?:id|identifier|number|no\.?)\b{_SEP}(?P<value>{_ID})\b",
        score=0.997,
    ),
    ContextRule(
        "NYC_BBL",
        rf"(?:nyc\s+)?bbl\b{_SEP}(?P<value>[1-5]-?\d{{5}}-?\d{{4}})\b",
        score=0.999,
    ),
    ContextRule(
        "PROPERTY_IDENTIFIER",
        rf"(?:tax\s+)?(?:block|lot)\b{_SEP}(?P<value>\d{{1,6}})\b",
        score=0.998,
    ),
    ContextRule(
        "DATE_OF_BIRTH",
        r"\bborn\s+on\s+(?P<value>[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})\b",
        score=0.998,
    ),
    ContextRule(
        "SECURITY_CODE",
        rf"(?:alarm|security(?:\s+panel)?|disarm|arm)\s+(?:code|pin)\b{_SEP}(?P<value>(?=[A-Z0-9#*-]*\d)[A-Z0-9#*-]{{3,16}})\b",
        score=0.998,
    ),
    ContextRule(
        "SAFE_COMBINATION",
        rf"safe\s+(?:combination|combo|code)\b{_SEP}(?P<value>(?=[A-Z0-9#*.-]*\d)[A-Z0-9#*.-]{{3,32}})\b",
        score=0.998,
    ),
    ContextRule(
        "RENT_AMOUNT",
        rf"(?:monthly|legal|preferential|contract|asking)?\s*rent(?:\s+amount)?\b{_SEP}(?P<value>{_AMOUNT})",
        score=0.998,
    ),
    ContextRule(
        "SECURITY_DEPOSIT_AMOUNT",
        rf"security\s+deposit(?:\s+(?:held|balance|total|amount))?\b{_SEP}(?P<value>{_AMOUNT})",
        score=0.998,
    ),
    ContextRule(
        "OPERATING_BALANCE",
        rf"operating\s+(?:balance|cash)\b{_SEP}(?P<value>{_AMOUNT})",
        score=0.998,
    ),
    ContextRule(
        "PURCHASE_PRICE",
        rf"(?:purchase|contract|sale|acquisition|agreed|closing)\s+price\b{_SEP}(?P<value>{_AMOUNT})",
        score=0.998,
    ),
    ContextRule(
        "BROKER_COMMISSION",
        rf"(?:broker\s+commission|broker\s+fee|commission)\b{_SEP}(?P<value>{_PERCENT_OR_AMOUNT})",
        score=0.998,
    ),
    ContextRule(
        "ESCROW_AMOUNT",
        rf"(?:escrow\s+(?:holdback|balance)|repair\s+escrow|tax\s+escrow)\b{_SEP}(?P<value>{_AMOUNT})",
        score=0.998,
    ),
    ContextRule(
        "CONTRACTOR_LICENSE",
        rf"contractor(?:'s)?\s+licen[cs]e(?:\s+(?:id|number|no\.?))?\b{_SEP}(?P<value>{_ID})\b",
        score=0.998,
    ),
    ContextRule(
        "LIEN_WAIVER_ID",
        rf"lien\s+waiver(?:\s+(?:id|number|no\.?|reference))?\b{_SEP}(?P<value>{_ID})\b",
        score=0.998,
    ),
    ContextRule(
        "WIFI_CREDENTIAL",
        rf"(?:building\s+)?wi[- ]?fi\s+(?:password|passphrase|pwd)\b{_REQ_SEP}(?P<value>{_SECRET})",
        score=0.998,
    ),
)


PATTERN_RECOGNIZERS = (
    PatternRecognizer(
        supported_entity="URL",
        supported_language="en",
        patterns=[
            Pattern(
                "full_http_url",
                r"https?://[^\s<>\"']*[A-Za-z0-9/_~#%=&+.-]",
                0.99,
            )
        ],
    ),
)


def install_english_safe_recall_recognizers(registry) -> None:  # noqa: ANN001
    for rule in CONTEXT_RULES:
        registry.add_recognizer(ContextValueRecognizer(rule))
    for recognizer in PATTERN_RECOGNIZERS:
        registry.add_recognizer(recognizer)
