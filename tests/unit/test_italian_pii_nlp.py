from __future__ import annotations

import importlib.util

import pytest

from ai_pm_lab_privacy_gate.domain.models import PageContent
from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine


def test_missing_nlp_model_never_triggers_runtime_download() -> None:
    engine = PresidioPrivacyEngine(
        model_name="privacy_gate_missing_test_model",
        language="it",
    )

    with pytest.raises(RuntimeError, match="does not download NLP models at runtime"):
        engine._ensure_loaded()


@pytest.mark.skipif(
    importlib.util.find_spec("xx_ent_wiki_sm") is None,
    reason="xx_ent_wiki_sm is installed by requirements-lock.txt for release builds",
)
def test_italian_nlp_registry_exposes_privacy_entities() -> None:
    engine = PresidioPrivacyEngine(language="it")
    analyzer, _ = engine._ensure_loaded()

    supported = set(analyzer.get_supported_entities(language="it"))
    assert {"PERSON", "ORGANIZATION", "LOCATION"} <= supported


@pytest.mark.skipif(
    importlib.util.find_spec("xx_ent_wiki_sm") is None,
    reason="xx_ent_wiki_sm is installed by requirements-lock.txt for release builds",
)
def test_italian_nlp_fixture_guardrails_keep_values_not_field_labels() -> None:
    engine = PresidioPrivacyEngine(language="it")
    text = (
        "Locatore: Mario Rossi, nato a Roma e residente a Milano. "
        "Codice Fiscale: RSSMRA85T10A562S. Telefono: +39 347 123 4567. "
        "Società: Aurora Gestioni Immobiliari S.r.l. "
        "Foglio 123. Targa veicolo autorizzato: AB123CD."
    )
    findings = engine.analyze_page(
        PageContent(page_number=1, text=text),
        get_profile("property_management"),
    )
    pairs = {(item.entity_type, item.text) for item in findings}

    assert ("PERSON", "Mario Rossi") in pairs
    assert any(
        entity == "LOCATION" and value in {"Roma", "Milano"}
        for entity, value in pairs
    )
    assert ("ORGANIZATION", "Aurora Gestioni Immobiliari S.r.l.") in pairs
    assert ("IT_VEHICLE_PLATE", "AB123CD") in pairs

    blocked = {"Codice Fiscale", "Telefono", "Foglio", "Targa"}
    assert not any(
        entity in {"PERSON", "ORGANIZATION", "LOCATION"} and value in blocked
        for entity, value in pairs
    )
