from __future__ import annotations

from types import SimpleNamespace

from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.italian_neural import (
    ItalianNeuralPIIRecognizer,
    _collect_bio_results,
    resolve_italian_model_dir,
)


def test_neural_runtime_uses_explicit_local_model_directory(tmp_path) -> None:
    resolved = resolve_italian_model_dir(tmp_path)
    assert resolved == tmp_path.resolve()


def test_missing_neural_runtime_is_a_safe_noop(tmp_path) -> None:
    recognizer = ItalianNeuralPIIRecognizer(model_dir=tmp_path)
    assert not recognizer.is_available
    assert recognizer.analyze("Mario Rossi vive a Milano", ["PERSON", "LOCATION"]) == []


def test_bio_predictions_map_only_semantic_entities() -> None:
    text = "Mario Rossi vive a Milano."
    offsets = [(0, 0), (0, 5), (6, 11), (12, 16), (17, 18), (19, 25), (25, 26), (0, 0)]
    labels = ["O", "B-FULLNAME", "I-FULLNAME", "O", "O", "B-CITY", "O", "O"]
    scores = [1.0, 0.99, 0.98, 1.0, 1.0, 0.97, 1.0, 1.0]

    results = _collect_bio_results(
        text=text,
        offsets=offsets,
        labels=labels,
        scores=scores,
        requested_entities={"PERSON", "LOCATION"},
        recognizer_name="ItalianNeuralPIIRecognizer",
    )

    assert [(item.entity_type, text[item.start : item.end]) for item in results] == [
        ("PERSON", "Mario Rossi"),
        ("LOCATION", "Milano"),
    ]


def test_bio_predictions_trim_tokenizer_boundary_whitespace() -> None:
    text = "nato a Roma e residente a Milano"
    results = _collect_bio_results(
        text=text,
        offsets=[(6, 11), (23, 30)],
        labels=["B-CITY", "B-CITY"],
        scores=[0.99, 0.99],
        requested_entities={"LOCATION"},
        recognizer_name="ItalianNeuralPIIRecognizer",
    )

    assert [(item.start, item.end, text[item.start : item.end]) for item in results] == [
        (7, 11, "Roma"),
        (24, 30, "Milano"),
    ]


def test_structured_neural_labels_do_not_enter_privacygate_results() -> None:
    text = "IT60X0542811101000000123456 CA12345AA"
    results = _collect_bio_results(
        text=text,
        offsets=[(0, 27), (28, 37)],
        labels=["B-IBAN", "B-ID_DOC"],
        scores=[0.99, 0.99],
        requested_entities={"PERSON", "LOCATION", "ORGANIZATION", "STREET_ADDRESS"},
        recognizer_name="ItalianNeuralPIIRecognizer",
    )
    assert results == []


def test_neural_semantic_guardrails_reject_single_word_person() -> None:
    text = "Pine"
    results = _collect_bio_results(
        text=text,
        offsets=[(0, 4)],
        labels=["B-FULLNAME"],
        scores=[0.99],
        requested_entities={"PERSON"},
        recognizer_name="ItalianNeuralPIIRecognizer",
    )
    assert results == []


def test_neural_score_band_preserves_existing_overlap_priority() -> None:
    neural = SimpleNamespace(
        entity_type="STREET_ADDRESS",
        start=0,
        end=20,
        score=0.94,
    )
    deterministic = SimpleNamespace(
        entity_type="STREET_ADDRESS",
        start=0,
        end=20,
        score=0.95,
    )
    generic = SimpleNamespace(
        entity_type="LOCATION",
        start=0,
        end=20,
        score=0.85,
    )

    assert PresidioPrivacyEngine._without_overlaps([generic, neural, deterministic]) == [
        deterministic
    ]
    assert PresidioPrivacyEngine._without_overlaps([generic, neural]) == [neural]
