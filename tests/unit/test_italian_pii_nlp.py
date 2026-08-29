from __future__ import annotations

import importlib.util

import pytest

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
