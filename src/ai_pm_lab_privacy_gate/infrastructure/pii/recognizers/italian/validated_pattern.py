from __future__ import annotations

import re
from collections.abc import Callable

from presidio_analyzer import EntityRecognizer, RecognizerResult


Validator = Callable[[str], bool]


class ValidatedRegexRecognizer(EntityRecognizer):
    """Small deterministic recognizer for structured Italian identifiers."""

    def __init__(
        self,
        *,
        entity_type: str,
        pattern: str,
        validator: Validator,
        score: float = 0.995,
    ) -> None:
        super().__init__(supported_entities=[entity_type], supported_language="it")
        self._entity_type = entity_type
        self._regex = re.compile(pattern, re.IGNORECASE)
        self._validator = validator
        self._score = score

    def load(self) -> None:
        return None

    def analyze(self, text, entities, nlp_artifacts=None):  # noqa: ANN001
        if self._entity_type not in entities:
            return []
        results: list[RecognizerResult] = []
        for match in self._regex.finditer(text):
            value = match.group(0)
            if not self._validator(value):
                continue
            results.append(
                RecognizerResult(
                    entity_type=self._entity_type,
                    start=match.start(),
                    end=match.end(),
                    score=self._score,
                    recognition_metadata={
                        RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                    },
                )
            )
        return results
