from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


# Numbered civic addresses are strong enough to recognize without an additional
# label. Support punctuation/"n." variants and Località, which are common in
# Italian property documents. Provincial-road addresses need a dedicated shape
# so the road number is not mistaken for the civic number.
_STREET_PATTERN = (
    r"(?i)\b(?:via|viale|piazza|piazzale|corso|largo|vicolo|strada|lungomare|"
    r"contrada|frazione|località|localita)\s+"
    r"(?:[A-ZÀ-ÖØ-öø-ÿ0-9][\wÀ-ÖØ-öø-ÿ'’.-]*)"
    r"(?:\s+[A-ZÀ-ÖØ-öø-ÿ0-9][\wÀ-ÖØ-öø-ÿ'’.-]*){0,7}"
    r"\s*,?\s*(?:n(?:umero)?\.?\s*)?\d{1,5}[A-Z]?(?:[/\-][A-Z0-9]{1,4})?\b"
)
_PROVINCIAL_ROAD_PATTERN = (
    r"(?i)\bstrada\s+provinciale\s+\d{1,4}\s+"
    r"(?:n(?:umero)?\.?\s*)\d{1,5}[A-Z]?\b"
)
# A street without a civic number is too broad to detect globally ("via libera"
# is ordinary Italian). Accept it only after explicit residence/address context,
# and require normal capitalization inside the street name.
_NAMED_STREET_NO_NUMBER = (
    r"(?-i:(?:Via|Viale|Piazza|Piazzale|Corso|Largo|Vicolo|Strada|Lungomare|"
    r"Contrada|Frazione|Località)\s+"
    r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’-]*"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’-]*){0,5})"
)


def build_address_recognizers() -> tuple[object, ...]:
    return (
        PatternRecognizer(
            supported_entity="STREET_ADDRESS",
            supported_language="it",
            patterns=[
                Pattern("italian_provincial_road_address", _PROVINCIAL_ROAD_PATTERN, 0.975),
                Pattern("italian_street_address", _STREET_PATTERN, 0.96),
            ],
        ),
        ItalianContextValueRecognizer(
            entity_type="STREET_ADDRESS",
            pattern=(
                rf"\b(?:risiede|residente|domiciliat[oa]|"
                rf"domicilio\s+(?:indicato\s+)?(?:è|:)?|"
                rf"indirizzo\s+(?:indicato\s+)?(?:è|:)?)"
                rf"\s+(?:in|a)?\s*(?P<value>{_NAMED_STREET_NO_NUMBER})"
                rf"(?=\s*[,.;:]|$)"
            ),
            score=0.965,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_POSTAL_CODE",
            pattern=r"(?:\bcap\b|codice\s+di\s+avviamento\s+postale)\s*[:#-]?\s*(?P<value>\d{5})(?!\d)",
            score=0.985,
        ),
        # Common inline Italian address shape: Via ... 24, 20121 Milano (MI).
        # The comma + five digits + capitalized locality makes this much safer
        # than treating every five-digit number as a CAP.
        ItalianContextValueRecognizer(
            entity_type="IT_POSTAL_CODE",
            pattern=r",\s*(?P<value>\d{5})(?!\d)\s+(?=[A-ZÀ-ÖØ-Þ])",
            score=0.97,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_POSTAL_CODE",
            pattern=r"^\s*(?P<value>\d{5})\s+[A-ZÀ-ÖØ-öø-ÿ][^\r\n,;]{1,50}(?:\s+\([A-Z]{2}\))?\s*$",
            score=0.94,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_PROVINCE",
            pattern=r"\b(?:provincia|prov\.?)\s*[:#-]?\s*(?P<value>[A-Z]{2})\b",
            score=0.98,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_PROVINCE",
            pattern=r"\b\d{5}\s+[A-ZÀ-ÖØ-öø-ÿ][^\r\n,;]{1,40}\s+\((?P<value>[A-Z]{2})\)",
            score=0.95,
        ),
    )
