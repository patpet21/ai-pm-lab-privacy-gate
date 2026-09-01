from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.real_estate import (
    ContextRule,
    ContextValueRecognizer,
)


_SEP = r"\s*(?:(?:number|no\.?)\s*)?(?::|#)?\s*"


CONTEXT_RULES = (
    ContextRule(
        "US_BANK_NUMBER",
        r"(?im)^\s*(?:(?:dedicated|primary|secondary)\s+)?(?:(?:bank|checking|savings|business|payment|operating|escrow|trust|deposit|rent)\s+)?account\s+(?:number|no\.?)\s*(?::|#)?\s*(?P<value>\d{6,17})\b",
        score=0.995,
    ),
    ContextRule(
        "SWIFT_BIC",
        rf"(?:swift\s*/?\s*bic|swift|bic)\b{_SEP}(?P<value>[A-Z]{{6}}[A-Z0-9]{{2}}(?:[A-Z0-9]{{3}})?)\b",
        score=0.995,
    ),
    ContextRule(
        "CARD_LAST_FOUR",
        r"(?i)\bending\s+in\s+(?P<value>\d{4})\b",
        score=0.995,
    ),
    ContextRule(
        "CARD_TRANSACTION_ID",
        r"(?i)\bCARD-(?P<value>[A-Z0-9][A-Z0-9-]{5,40})\b",
        score=0.995,
    ),
    ContextRule(
        "TRANSFER_TRANSACTION_ID",
        r"(?i)\bTRANSFER-(?P<value>[A-Z0-9][A-Z0-9-]{5,40})\b",
        score=0.995,
    ),
    ContextRule(
        "STATEMENT_REFERENCE",
        r"(?im)^\s*(?:ref|statement\s+(?:ref|reference))\s*:\s*(?P<value>[0-9a-f]{8}-[0-9a-f-]{27,40})\b",
        score=0.99,
    ),
    ContextRule(
        "DATE_OF_BIRTH",
        rf"(?:date\s+of\s+birth|birth\s*date|dob)\b{_SEP}(?P<value>(?:\d{{1,2}}[/-]){{2}}\d{{2,4}}|[A-Z][a-z]+\s+\d{{1,2}},?\s+\d{{4}})\b",
        score=0.99,
    ),
    ContextRule(
        "US_DRIVER_LICENSE",
        r"(?:[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}\s+State\s+)?"
        r"driver(?:'s|s)?\s+licen[cs]e\s*(?:number|no\.?)?\s*(?::|#)?\s*"
        r"(?P<value>[A-Z0-9][A-Z0-9 -]{5,17}[A-Z0-9])(?=$|[.,;\r\n])",
        score=0.995,
    ),
    ContextRule(
        "BUSINESS_REGISTRATION_NUMBER",
        rf"(?:registered|registration|company|business)\s+(?:number|no\.?|id)(?=\s|:|#|$){_SEP}(?P<value>[A-Z0-9][A-Z0-9-]{{5,30}})\b",
        score=0.995,
    ),
    ContextRule(
        "BUSINESS_REGISTRATION_NUMBER",
        rf"(?:(?:[A-Z]{{2}}\s+)?(?:department\s+of\s+state|dos)|secretary\s+of\s+state)\s+(?:entity|business)?\s*(?:id|number|no\.?)(?=\s|:|#|$){_SEP}(?P<value>[A-Z0-9][A-Z0-9-]{{5,30}})\b",
        score=0.995,
    ),
    ContextRule(
        "INVOICE_NUMBER",
        rf"invoice\s*(?:number|no\.?|id|#)?{_SEP}(?P<value>(?:INV-)?[A-Z0-9][A-Z0-9-]{{3,30}})\b",
        score=0.98,
    ),
    ContextRule(
        "PURCHASE_ORDER_ID",
        rf"(?:purchase\s+order|p\.?o\.?)\s*(?:number|no\.?|id)?\b{_SEP}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
        score=0.98,
    ),
    ContextRule(
        "CONTRACT_ID",
        rf"contract\s+(?:number|no\.?|id|reference)\b{_SEP}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
        score=0.98,
    ),
    ContextRule(
        "CUSTOMER_ID",
        rf"(?:customer|client)\s+(?:number|no\.?|id|identifier)\b{_SEP}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
        score=0.98,
    ),
    ContextRule(
        "EMPLOYEE_ID",
        rf"employee\s+(?:number|no\.?|id|identifier)\b{_SEP}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
        score=0.98,
    ),
    ContextRule(
        "CASE_REFERENCE",
        rf"case\s+(?:number|no\.?|id|reference)\b{_SEP}(?P<value>[A-Z0-9][A-Z0-9-]{{3,30}})\b",
        score=0.98,
    ),
    ContextRule(
        "PERSON",
        r"(?im)\bending\s+in\s+\d{4}\s+(?P<value>[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){1,3})\s+Transaction\s*:",
        score=0.99,
    ),
    ContextRule(
        "MERCHANT",
        r"(?im)\bissued\s+by\s+(?P<value>[^\r\n]{2,100})$",
        score=0.94,
    ),
    ContextRule(
        "COUNTERPARTY",
        r"(?im)\b(?:sent\s+money\s+to|received\s+money\s+from)\s+(?P<value>[^\r\n]{2,100}?)(?=\s+with\s+reference\b|\r?$)",
        score=0.97,
    ),
    ContextRule(
        "TRANSACTION_REFERENCE",
        r"(?im)\breference\s*:\s*(?P<value>[^\r\n]{2,120})$",
        score=0.92,
    ),
    ContextRule(
        "TRANSACTION_REFERENCE",
        r"(?im)\bwith\s+reference\s+(?P<value>[^\r\n]{2,120})$",
        score=0.94,
    ),
)


PATTERN_RECOGNIZERS = (
    PatternRecognizer(
        supported_entity="MONEY_AMOUNT",
        supported_language="en",
        patterns=[
            Pattern(
                "currency_amount",
                r"(?<![\w.])(?:[-+]?\s*(?:[$€£]|USD\s*|EUR\s*|GBP\s*))?\d{1,3}(?:,\d{3})*\.\d{2}(?:\s*(?:USD|EUR|GBP))?(?!\w)",
                0.88,
            )
        ],
    ),
    PatternRecognizer(
        supported_entity="POSTAL_CODE",
        supported_language="en",
        patterns=[
            Pattern("us_zip", r"(?<!\d)\d{5}(?:-\d{4})?(?!\d)", 0.86),
            Pattern("standalone_international_postal", r"(?m)^\s*\d{4,6}\s*$", 0.72),
        ],
    ),
    PatternRecognizer(
        supported_entity="STREET_ADDRESS",
        supported_language="en",
        patterns=[
            Pattern(
                "north_american_street",
                r"(?i)\b\d{1,6}(?:-\d{1,6})?\s+"
                r"(?:[A-Z0-9.'-]+\s+){1,8}"
                r"(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Lane|Ln\.?|Drive|Dr\.?|Court|Ct\.?|Parkway|Pkwy\.?|Highway|Hwy)(?=\s|,|$)"
                r"(?:\s*,?\s*(?:Apt\.?|Apartment|Unit|Suite)\s+[A-Z0-9-]+)?"
                r"(?:\s*,\s*[A-Z][A-Za-z.' -]{1,40})?"
                r"(?:\s*,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)?",
                0.94,
            ),
            Pattern(
                "international_street",
                r"(?im)\b(?:Via|Rue|Calle|Corso|Viale|Piazza|Avenida)\s+[^\r\n]{2,60}?\s+\d+[A-Z]?(?:\s*,\s*[^\r\n]{1,30})?",
                0.93,
            ),
            Pattern(
                "multiline_address_block",
                r"(?im)\b(?:Via|Rue|Calle|Corso|Viale|Piazza|Avenida)\s+[^\r\n]{2,60}?\s+\d+[A-Z]?[^\r\n]*\r?\n[^\r\n]{2,50}\r?\n\s*\d{4,6}\s*\r?\n[^\r\n]{2,40}",
                0.985,
            ),
        ],
    ),
)


def install_universal_sensitive_recognizers(registry) -> None:  # noqa: ANN001
    for rule in CONTEXT_RULES:
        registry.add_recognizer(ContextValueRecognizer(rule))
    for recognizer in PATTERN_RECOGNIZERS:
        registry.add_recognizer(recognizer)
