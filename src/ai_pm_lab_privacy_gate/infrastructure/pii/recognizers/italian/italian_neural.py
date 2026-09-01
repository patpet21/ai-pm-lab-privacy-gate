from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from presidio_analyzer import EntityRecognizer, RecognizerResult


ITALIAN_MODEL_DIR_ENV = "PRIVACYGATE_ITALIAN_MODEL_DIR"
ITALIAN_MODEL_FOLDER = "PrivacyGate-Italian-Model"
_REQUIRED_MODEL_FILES = ("model.onnx", "tokenizer.json", "config.json")

# The neural model is a semantic recall layer only. Structured identifiers stay
# owned by PrivacyGate's deterministic/checksum/contextual recognizers.
_NEURAL_LABEL_TO_ENTITY = {
    "FULLNAME": "PERSON",
    "ORG": "ORGANIZATION",
    "CITY": "LOCATION",
    "STREET": "STREET_ADDRESS",
}


def resolve_italian_model_dir(explicit: str | Path | None = None) -> Path:
    """Return the neutral local model directory without making network calls."""
    if explicit is not None:
        return Path(explicit).expanduser().resolve()

    configured = os.environ.get(ITALIAN_MODEL_DIR_ENV)
    if configured:
        return Path(configured).expanduser().resolve()

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root) / "resources" / "models" / ITALIAN_MODEL_FOLDER

    source = Path(__file__).resolve()
    for parent in source.parents:
        if parent.name == "src":
            return parent.parent / "resources" / "models" / ITALIAN_MODEL_FOLDER

    return Path.cwd() / "resources" / "models" / ITALIAN_MODEL_FOLDER


def _split_bio_label(label: str) -> tuple[str, str | None]:
    normalized = str(label).strip()
    if normalized == "O":
        return "O", None
    if (
        len(normalized) > 2
        and normalized[0] in {"B", "I"}
        and normalized[1] in {"-", "_"}
    ):
        return normalized[0], normalized[2:].upper()
    return "O", None


def _trim_text_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Trim tokenizer boundary whitespace without altering internal entity text."""
    start = max(0, int(start))
    end = min(len(text), int(end))
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _collect_bio_results(
    *,
    text: str,
    offsets: Sequence[tuple[int, int]],
    labels: Sequence[str],
    scores: Sequence[float],
    requested_entities: set[str],
    recognizer_name: str,
    base_offset: int = 0,
) -> list[RecognizerResult]:
    """Merge BIO token predictions into PrivacyGate entity spans."""
    results: list[RecognizerResult] = []
    current_entity: str | None = None
    current_start: int | None = None
    current_end: int | None = None
    current_scores: list[float] = []

    def flush() -> None:
        nonlocal current_entity, current_start, current_end, current_scores
        if (
            current_entity is not None
            and current_start is not None
            and current_end is not None
            and current_end > current_start
        ):
            raw_score = float(sum(current_scores) / max(1, len(current_scores)))
            span_start, span_end = _trim_text_span(text, current_start, current_end)
            value = text[span_start:span_end]
            from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.guardrails import (
                is_italian_ner_false_positive,
            )

            if (
                span_end <= span_start
                or raw_score < 0.55
                or is_italian_ner_false_positive(current_entity, value)
            ):
                current_entity = None
                current_start = None
                current_end = None
                current_scores = []
                return

            # Keep neural recall above generic spaCy (0.85) but below PrivacyGate
            # deterministic/contextual recognizers (0.95+), so overlap resolution
            # naturally preserves the intended source priority.
            score = min(0.94, 0.86 + (0.08 * raw_score))
            results.append(
                RecognizerResult(
                    entity_type=current_entity,
                    start=base_offset + span_start,
                    end=base_offset + span_end,
                    score=score,
                    recognition_metadata={
                        RecognizerResult.RECOGNIZER_NAME_KEY: recognizer_name,
                    },
                )
            )
        current_entity = None
        current_start = None
        current_end = None
        current_scores = []

    for offset, raw_label, raw_score in zip(offsets, labels, scores):
        start, end = int(offset[0]), int(offset[1])
        prefix, source_entity = _split_bio_label(raw_label)
        mapped_entity = _NEURAL_LABEL_TO_ENTITY.get(source_entity or "")

        if (
            end <= start
            or prefix == "O"
            or mapped_entity is None
            or mapped_entity not in requested_entities
        ):
            flush()
            continue

        can_continue = (
            prefix == "I"
            and current_entity == mapped_entity
            and current_end is not None
            and start >= current_end
        )
        if not can_continue:
            flush()
            current_entity = mapped_entity
            current_start = start
            current_end = end
            current_scores = [float(raw_score)]
            continue

        current_end = end
        current_scores.append(float(raw_score))

    flush()
    return results


class ItalianNeuralPIIRecognizer(EntityRecognizer):
    """Offline ONNX semantic recognizer used only for Italian documents."""

    def __init__(
        self,
        *,
        model_dir: str | Path | None = None,
        max_tokens: int = 1024,
        overlap_tokens: int = 64,
    ) -> None:
        supported = tuple(dict.fromkeys(_NEURAL_LABEL_TO_ENTITY.values()))
        super().__init__(supported_entities=list(supported), supported_language="it")
        if max_tokens < 16:
            raise ValueError("max_tokens must be at least 16")
        if overlap_tokens < 0 or overlap_tokens >= max_tokens - 2:
            raise ValueError("overlap_tokens must be smaller than the content window")
        self._model_dir = resolve_italian_model_dir(model_dir)
        self._max_tokens = int(max_tokens)
        self._overlap_tokens = int(overlap_tokens)
        self._tokenizer: Any | None = None
        self._session: Any | None = None
        self._id2label: dict[int, str] = {}
        self._load_lock = threading.Lock()

    @property
    def model_dir(self) -> Path:
        return self._model_dir

    @property
    def is_available(self) -> bool:
        return all((self._model_dir / name).is_file() for name in _REQUIRED_MODEL_FILES)

    def load(self) -> None:
        # Presidio may call load while building the registry. The heavy ONNX session
        # stays lazy so selecting English never loads the Italian neural model.
        return None

    def _ensure_loaded(self) -> bool:
        if self._session is not None and self._tokenizer is not None:
            return True
        if not self.is_available:
            return False

        with self._load_lock:
            if self._session is not None and self._tokenizer is not None:
                return True

            try:
                import onnxruntime as ort
                from tokenizers import Tokenizer
            except ImportError as exc:
                raise RuntimeError(
                    "The local Italian neural model is present, but its lightweight "
                    "ONNX/tokenizer runtime is not installed."
                ) from exc

            config = json.loads(
                (self._model_dir / "config.json").read_text(encoding="utf-8")
            )
            raw_id2label = config.get("id2label")
            if not isinstance(raw_id2label, dict):
                raise RuntimeError("Italian neural model config.json has no id2label map.")

            id2label: dict[int, str] = {}
            for key, value in raw_id2label.items():
                try:
                    index = int(key)
                except (TypeError, ValueError) as exc:
                    raise RuntimeError(
                        "Italian neural model config.json contains an invalid label id."
                    ) from exc
                id2label[index] = str(value)

            tokenizer = Tokenizer.from_file(str(self._model_dir / "tokenizer.json"))
            session = ort.InferenceSession(
                str(self._model_dir / "model.onnx"),
                providers=["CPUExecutionProvider"],
            )
            input_names = {item.name for item in session.get_inputs()}
            if not {"input_ids", "attention_mask"} <= input_names:
                raise RuntimeError(
                    "Italian neural ONNX model does not expose the expected inputs."
                )

            self._id2label = id2label
            self._tokenizer = tokenizer
            self._session = session
        return True

    def analyze(self, text, entities, nlp_artifacts=None):  # noqa: ANN001
        requested = set(entities or ())
        requested &= set(self.supported_entities)
        if not text or not requested or not self._ensure_loaded():
            return []

        tokenizer = self._tokenizer
        if tokenizer is None:
            return []

        plain = tokenizer.encode(text, add_special_tokens=False)
        content_offsets = [
            (int(start), int(end))
            for start, end in plain.offsets
            if int(end) > int(start)
        ]
        if not content_offsets:
            return []

        max_content_tokens = self._max_tokens - 2
        step = max(1, max_content_tokens - self._overlap_tokens)
        results: list[RecognizerResult] = []

        for token_start in range(0, len(content_offsets), step):
            token_end = min(token_start + max_content_tokens, len(content_offsets))
            chunk_offsets = content_offsets[token_start:token_end]
            if not chunk_offsets:
                continue
            char_start = chunk_offsets[0][0]
            char_end = chunk_offsets[-1][1]
            if char_end <= char_start:
                continue
            results.extend(
                self._analyze_chunk(
                    text[char_start:char_end],
                    base_offset=char_start,
                    requested_entities=requested,
                )
            )
            if token_end >= len(content_offsets):
                break

        deduplicated: dict[tuple[str, int, int], RecognizerResult] = {}
        for result in results:
            key = (str(result.entity_type), int(result.start), int(result.end))
            current = deduplicated.get(key)
            if current is None or float(result.score) > float(current.score):
                deduplicated[key] = result
        return sorted(
            deduplicated.values(),
            key=lambda item: (int(item.start), int(item.end), str(item.entity_type)),
        )

    def _analyze_chunk(
        self,
        text: str,
        *,
        base_offset: int,
        requested_entities: set[str],
    ) -> list[RecognizerResult]:
        tokenizer = self._tokenizer
        session = self._session
        if tokenizer is None or session is None:
            return []

        encoded = tokenizer.encode(text, add_special_tokens=True)
        input_ids = np.asarray([encoded.ids], dtype=np.int64)
        attention_mask = np.ones_like(input_ids, dtype=np.int64)
        logits = session.run(
            ["logits"],
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            },
        )[0]

        token_logits = np.asarray(logits[0])
        predicted_ids = np.argmax(token_logits, axis=-1)
        labels: list[str] = []
        scores: list[float] = []
        for row, predicted in zip(token_logits, predicted_ids):
            predicted_index = int(predicted)
            labels.append(self._id2label.get(predicted_index, "O"))
            shifted = row - np.max(row)
            probabilities = np.exp(shifted)
            denominator = float(np.sum(probabilities))
            score = (
                float(probabilities[predicted_index] / denominator)
                if denominator > 0.0
                else 0.0
            )
            scores.append(score)

        return _collect_bio_results(
            text=text,
            offsets=[(int(start), int(end)) for start, end in encoded.offsets],
            labels=labels,
            scores=scores,
            requested_entities=requested_entities,
            recognizer_name=self.name,
            base_offset=base_offset,
        )


def build_italian_neural_recognizers() -> tuple[ItalianNeuralPIIRecognizer, ...]:
    return (ItalianNeuralPIIRecognizer(),)
