from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PiiLanguageConfig:
    code: str
    label: str
    model_name: str


DEFAULT_DOCUMENT_LANGUAGE = "en"

_LANGUAGE_ALIASES = {
    "en": "en",
    "english": "en",
    "it": "it",
    "italian": "it",
    "italiano": "it",
}

LANGUAGE_CONFIGS: dict[str, PiiLanguageConfig] = {
    "en": PiiLanguageConfig(code="en", label="English", model_name="en_core_web_sm"),
    # Use the small MIT multilingual NER model as the distributable Italian
    # baseline. The official it_core_news_sm 3.8.0 model is CC BY-NC-SA 3.0,
    # so it is intentionally not bundled in PrivacyGate releases.
    "it": PiiLanguageConfig(code="it", label="Italiano", model_name="xx_ent_wiki_sm"),
}


def normalize_document_language(value: str | None) -> str:
    """Return the canonical language code used by the local PII engine."""
    raw = (value or DEFAULT_DOCUMENT_LANGUAGE).strip().lower()
    try:
        return _LANGUAGE_ALIASES[raw]
    except KeyError as exc:
        supported = ", ".join(sorted(LANGUAGE_CONFIGS))
        raise ValueError(f"Unsupported document language {value!r}; expected one of: {supported}") from exc


def get_language_config(value: str | None) -> PiiLanguageConfig:
    return LANGUAGE_CONFIGS[normalize_document_language(value)]
