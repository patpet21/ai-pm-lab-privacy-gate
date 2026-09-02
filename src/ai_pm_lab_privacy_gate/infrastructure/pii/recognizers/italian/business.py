from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


_SEPARATOR = r"\s*(?:(?:n(?:umero)?\.?|no\.?)\s*)?[:#-]?\s*"

_ORGANIZATION_WITH_LEGAL_SUFFIX = (
    r"(?<![\wÀ-ÖØ-öø-ÿ])"
    r"(?-i:"
    r"(?:[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’&.-]*\s+){1,8}"
    r"(?:[Ss]\.?\s*[Rr]\.?\s*[Ll]\.?|[Ss]\.?\s*[Pp]\.?\s*[Aa]\.?|"
    r"[Ss][Nn][Cc]|[Ss][Aa][Ss])"
    r")"
    r"(?=\s|[,;:]|\.?$)"
)

# High-precision organization shapes learned from the local semantic benchmarks.
# The lead must be an institutional/business form and the proper-name body keeps
# normal capitalization. This intentionally avoids a generic "capitalized words"
# rule, which would damage precision on ordinary Italian prose.
_ORGANIZATION_LEAD = (
    r"(?:Agenzia\s+(?:Immobiliare|Casa)|Impresa\s+(?:Edile|Costruzioni)|"
    r"Gruppo\s+Immobiliare|Studio\s+(?:Tecnico|Legale|Notarile|Associato)|"
    r"Fondazione|Cooperativa|Amministrazioni|Consorzio|Condominio|Banca|"
    r"Politecnico|Associazione|Università|Ordine)"
)
_ORGANIZATION_NAME_TOKEN = r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’-]{1,30}"
_ORGANIZATION_CONNECTOR = r"(?:di|del|della|dei|degli|delle|e|&)"
_ORGANIZATION_BODY = (
    rf"(?:(?:{_ORGANIZATION_CONNECTOR})\s+)?{_ORGANIZATION_NAME_TOKEN}"
    rf"(?:\s+(?:(?:{_ORGANIZATION_CONNECTOR})\s+)?{_ORGANIZATION_NAME_TOKEN}){{0,5}}"
)
_SEMANTIC_ORGANIZATION = (
    rf"(?-i:{_ORGANIZATION_LEAD}\s+{_ORGANIZATION_BODY})"
)
# A proper organization can be followed by punctuation or ordinary lowercase
# sentence continuation ("Condominio Parco Verde è convocato..."). The strong,
# case-sensitive lead/body remains the precision gate.
_ORGANIZATION_BOUNDARY = r"(?=\s*(?:[,.;:]|$|(?-i:[a-zà-öø-ÿ])))"


def _looks_like_registry_number(value: str) -> bool:
    compact = "".join(char for char in value if char.isalnum())
    return len(compact) >= 6 and any(char.isdigit() for char in compact)


def build_business_recognizers() -> tuple[ItalianContextValueRecognizer, ...]:
    return (
        ItalianContextValueRecognizer(
            entity_type="ORGANIZATION",
            pattern=rf"(?P<value>{_ORGANIZATION_WITH_LEGAL_SUFFIX})",
            score=0.998,
        ),
        ItalianContextValueRecognizer(
            entity_type="ORGANIZATION",
            pattern=rf"(?P<value>{_SEMANTIC_ORGANIZATION}){_ORGANIZATION_BOUNDARY}",
            score=0.992,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_REA_NUMBER",
            pattern=rf"(?:\br\.?\s*e\.?\s*a\.?|\brepertorio\s+economico\s+amministrativo)(?=\s|:|#|-){_SEPARATOR}(?P<value>[A-Z]{{2}}\s*[-/]?\s*\d{{3,9}})\b",
            score=0.99,
        ),
        ItalianContextValueRecognizer(
            entity_type="IT_BUSINESS_REGISTER_NUMBER",
            pattern=rf"\b(?:numero\s+)?registro\s+(?:delle\s+)?imprese\b{_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9./-]{{5,20}})\b",
            score=0.975,
            validator=_looks_like_registry_number,
        ),
    )
