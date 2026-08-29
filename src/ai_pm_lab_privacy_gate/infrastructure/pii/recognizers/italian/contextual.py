from __future__ import annotations

import re
from collections.abc import Callable

from presidio_analyzer import EntityRecognizer, RecognizerResult


Validator = Callable[[str], bool]


class ItalianContextValueRecognizer(EntityRecognizer):
    """Return only the sensitive value that follows an explicit Italian label."""

    def __init__(
        self,
        *,
        entity_type: str,
        pattern: str,
        score: float = 0.98,
        validator: Validator | None = None,
    ) -> None:
        super().__init__(supported_entities=[entity_type], supported_language="it")
        self._entity_type = entity_type
        self._regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self._score = score
        self._validator = validator

    def load(self) -> None:
        return None

    def analyze(self, text, entities, nlp_artifacts=None):  # noqa: ANN001
        if self._entity_type not in entities:
            return []
        results: list[RecognizerResult] = []
        for match in self._regex.finditer(text):
            start, end = match.span("value")
            value = match.group("value")
            if self._validator is not None and not self._validator(value):
                continue
            results.append(
                RecognizerResult(
                    entity_type=self._entity_type,
                    start=start,
                    end=end,
                    score=self._score,
                    recognition_metadata={
                        RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                    },
                )
            )
        return results
