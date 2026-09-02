from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


# Numbered civic addresses are strong enough to recognize without an additional
# label. Support punctuation/"n." variants and common Italian address forms.
_STREET_PATTERN = (
    r"(?i)\b(?:via|viale|piazza|piazzale|corso|largo|vicolo|strada|lungomare|"
    r"contrada|frazione|località|localita|salita|borgo)\s+"
    r"(?:[A-ZÀ-ÖØ-öø-ÿ0-9][\wÀ-ÖØ-öø-ÿ'’.-]*)"
    r"(?:\s+[A-ZÀ-ÖØ-öø-ÿ0-9][\wÀ-ÖØ-öø-ÿ'’.-]*){0,7}"
    r"\s*,?\s*(?:n(?:umero)?\.?\s*)?\d{1,5}[A-Z]?(?:[/\-][A-Z0-9]{1,4})?\b"
)
_CONTEXTUAL_NUMBERED_STREET = (
    r"(?:via|viale|piazza|piazzale|corso|largo|vicolo|strada|lungomare|"
    r"contrada|frazione|località|localita|salita|borgo)\s+"
    r"(?:[A-ZÀ-ÖØ-öø-ÿ0-9][\wÀ-ÖØ-öø-ÿ'’.-]*)"
    r"(?:\s+[A-ZÀ-ÖØ-öø-ÿ0-9][\wÀ-ÖØ-öø-ÿ'’.-]*){0,7}"
    r"\s*,?\s*(?:n(?:umero)?\.?\s*)?\d{1,5}[A-Z]?(?:[/\-][A-Z0-9]{1,4})?\b"
)
_PROVINCIAL_ROAD_PATTERN = (
    r"(?i)\bstrada\s+provinciale\s+\d{1,4}\s+"
    r"(?:n(?:umero)?\.?\s*)\d{1,5}[A-Z]?\b"
)
_PROVINCIAL_ROAD_VALUE = (
    r"(?-i:Strada\s+Provinciale\s+\d{1,4}\s+"
    r"n(?:umero)?\.?\s*\d{1,5}[A-Z]?)"
)
_SP_CIVIC_PATTERN = (
    r"(?i)\bS\.?\s*P\.?\s*\d{1,4}\s*,?\s*civico\s+"
    r"\d{1,5}[A-Z]?(?:[/\-][A-Z0-9]{1,4})?\b"
)
_SS_ADDRESS_PATTERN = (
    r"(?i)\bS\.?\s*S\.?\s*\d{1,4}"
    r"(?:\s+[A-ZÀ-ÖØ-öø-ÿ][\wÀ-ÖØ-öø-ÿ'’.-]*){1,5}"
    r"\s+\d{1,5}[A-Z]?(?:[/\-][A-Z0-9]{1,4})?\b"
)

# A street without a civic number is too broad to detect globally ("via libera"
# is ordinary Italian). Accept it only after explicit residence/address context,
# and require normal capitalization in the proper street name. Lowercase Italian
# connectors such as "delle" are allowed inside the name.
_STREET_NAME_TOKEN = r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’-]*"
_STREET_NAME_CONNECTOR = (
    r"(?:di|del|della|dei|degli|delle|da|dal|dallo|dalla|dai|dagli|sul|sulla|sui|sulle)"
)
_NAMED_STREET_NO_NUMBER = (
    rf"(?-i:(?:Via|Viale|Piazza|Piazzale|Corso|Largo|Vicolo|Strada|Lungomare|"
    rf"Contrada|Frazione|Località|Salita|Borgo)\s+"
    rf"(?:(?:{_STREET_NAME_CONNECTOR})\s+)?{_STREET_NAME_TOKEN}"
    rf"(?:\s+(?:(?:{_STREET_NAME_CONNECTOR})\s+)?{_STREET_NAME_TOKEN}){{0,5}})"
)


def build_address_recognizers() -> tuple[object, ...]:
    return (
        PatternRecognizer(
            supported_entity="STREET_ADDRESS",
            supported_language="it",
            patterns=[
                Pattern("italian_sp_civic_address", _SP_CIVIC_PATTERN, 0.985),
                Pattern("italian_ss_named_address", _SS_ADDRESS_PATTERN, 0.98),
                Pattern("italian_provincial_road_address", _PROVINCIAL_ROAD_PATTERN, 0.975),
                Pattern("italian_street_address", _STREET_PATTERN, 0.96),
            ],
        ),
        # In contracts and administrative documents these labels are strong
        # evidence that the following numbered street is an address. Give this
        # path deterministic priority over semantic NER so a street cannot be
        # split into LOCATION/PERSON fragments while leaving the civic number.
        ItalianContextValueRecognizer(
            entity_type="STREET_ADDRESS",
            pattern=(
                rf"\b(?:residente|domiciliat[oa]|con\s+sede|sito|situat[oa]|ubicat[oa])"
                rf"\s+(?:in|a)?\s*(?P<value>{_CONTEXTUAL_NUMBERED_STREET})"
                rf"(?=\s*[,.;:]|$)"
            ),
            score=0.995,
        ),
        ItalianContextValueRecognizer(
            entity_type="STREET_ADDRESS",
            pattern=(
                rf"\b(?:ingresso\s+da|accesso\s+da|sito\s+in|ubicat[oa]\s+in|"
                rf"si\s+trova\s+in|indirizzo\s+(?:indicato\s+)?(?:è|:)?)"
                rf"\s*(?P<value>{_PROVINCIAL_ROAD_VALUE})"
                rf"(?=\s*[,.;:]|$)"
            ),
            score=0.985,
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
