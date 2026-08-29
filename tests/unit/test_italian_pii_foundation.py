from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.languages import (
    get_language_config,
    normalize_document_language,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian import ITALIAN_ENTITY_TYPES
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.financial import (
    is_valid_italian_iban,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.fiscal import (
    is_valid_codice_fiscale,
    is_valid_partita_iva,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.registry import (
    install_custom_recognizers,
)


class _RecordingRegistry:
    def __init__(self) -> None:
        self.recognizers = []

    def add_recognizer(self, recognizer) -> None:  # noqa: ANN001
        self.recognizers.append(recognizer)


def test_language_config_keeps_english_default_and_exposes_italian() -> None:
    assert normalize_document_language(None) == "en"
    assert normalize_document_language("Italiano") == "it"
    assert get_language_config("it").model_name == "it_core_news_sm"

    engine = PresidioPrivacyEngine()
    assert engine.document_language == "en"
    assert engine.model_name == "en_core_web_sm"

    italian_engine = PresidioPrivacyEngine(language="it")
    assert italian_engine.document_language == "it"
    assert italian_engine.model_name == "it_core_news_sm"


def test_italian_registry_isolated_from_english_installers() -> None:
    registry = _RecordingRegistry()
    install_custom_recognizers(registry, languages=("it",))

    entities = {
        entity
        for recognizer in registry.recognizers
        for entity in recognizer.supported_entities
    }
    assert entities == set(ITALIAN_ENTITY_TYPES)
    assert all(recognizer.supported_language == "it" for recognizer in registry.recognizers)


def test_codice_fiscale_checksum() -> None:
    assert is_valid_codice_fiscale("RSSMRA85T10A562S")
    assert not is_valid_codice_fiscale("RSSMRA85T10A562A")


def test_partita_iva_checksum() -> None:
    assert is_valid_partita_iva("00743110157")
    assert is_valid_partita_iva("IT00743110157")
    assert not is_valid_partita_iva("00743110158")


def test_italian_iban_mod97() -> None:
    assert is_valid_italian_iban("IT60X0542811101000000123456")
    assert is_valid_italian_iban("IT60 X054 2811 1010 0000 0123 456")
    assert not is_valid_italian_iban("IT60X0542811101000000123457")
