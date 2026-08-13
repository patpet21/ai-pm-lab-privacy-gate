from __future__ import annotations

import threading
import re
from collections.abc import Iterable
from typing import Any

from ai_pm_lab_privacy_gate.domain.models import Finding, PageContent
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile


class PresidioPrivacyEngine:
    """Lazy, local-only Presidio adapter shared by every application surface."""

    def __init__(self, model_name: str = "en_core_web_sm") -> None:
        self._model_name = model_name
        self._analyzer: Any | None = None
        self._anonymizer: Any | None = None
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> tuple[Any, Any]:
        if self._analyzer is not None and self._anonymizer is not None:
            return self._analyzer, self._anonymizer
        with self._lock:
            if self._analyzer is None:
                import tldextract
                from presidio_analyzer import AnalyzerEngine
                from presidio_analyzer.nlp_engine import NlpEngineProvider
                from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.registry import (
                    install_custom_recognizers,
                )

                # Presidio's email recognizer normally lets tldextract refresh
                # the suffix list online. Use its bundled snapshot so the first
                # scan remains local-only.
                tldextract.extract = tldextract.TLDExtract(
                    suffix_list_urls=(), cache_dir=None
                )
                configuration = {
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": "en", "model_name": self._model_name}],
                }
                nlp_engine = NlpEngineProvider(nlp_configuration=configuration).create_engine()
                analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
                install_custom_recognizers(analyzer.registry)
                self._analyzer = analyzer
            if self._anonymizer is None:
                from presidio_anonymizer import AnonymizerEngine

                self._anonymizer = AnonymizerEngine()
        return self._analyzer, self._anonymizer

    def analyze_page(self, page: PageContent, profile: PrivacyProfile) -> list[Finding]:
        analyzer, _ = self._ensure_loaded()
        supported = set(analyzer.get_supported_entities(language="en"))
        entities = [entity for entity in profile.entities if entity in supported]
        results = analyzer.analyze(
            text=page.text,
            language="en",
            entities=entities,
            score_threshold=profile.threshold,
        )
        token_spans = [
            match.span()
            for match in re.finditer(
                r"\[\[(?:PG_)?[A-Z0-9_]+(?:_\d{3})?\]\]|\[REDACTED\]",
                page.text,
            )
        ]
        if token_spans:
            results = [
                result
                for result in results
                if not any(result.start < end and start < result.end for start, end in token_spans)
            ]
        resolved = self._without_overlaps(results)
        return [self._to_finding(page, result, index) for index, result in enumerate(resolved)]

    @staticmethod
    def _without_overlaps(results: list[Any]) -> list[Any]:
        """Prefer high-confidence contextual IDs over generic numeric guesses."""
        accepted: list[RecognizerResult] = []
        for candidate in sorted(
            results,
            key=lambda item: (-item.score, -(item.end - item.start), item.start),
        ):
            if any(candidate.start < current.end and current.start < candidate.end for current in accepted):
                continue
            accepted.append(candidate)
        return sorted(accepted, key=lambda item: (item.start, item.end))

    def protect_text(self, text: str, findings: Iterable[Finding]) -> str:
        selected = list(findings)
        if not selected:
            return text
        from presidio_analyzer import RecognizerResult
        from presidio_anonymizer.entities import OperatorConfig

        _, anonymizer = self._ensure_loaded()
        results = [
            RecognizerResult(
                entity_type=item.entity_type,
                start=item.start,
                end=item.end,
                score=item.score,
            )
            for item in selected
        ]
        operators = {
            entity: OperatorConfig("replace", {"new_value": f"<{entity}>"})
            for entity in {item.entity_type for item in selected}
        }
        return anonymizer.anonymize(text=text, analyzer_results=results, operators=operators).text

    @staticmethod
    def _to_finding(page: PageContent, result: RecognizerResult, index: int) -> Finding:
        radius = 34
        left = max(0, result.start - radius)
        right = min(len(page.text), result.end + radius)
        context = page.text[left:right].replace("\r", " ").replace("\n", " ")
        return Finding(
            finding_id=f"p{page.page_number}-{result.start}-{result.end}-{index}",
            entity_type=result.entity_type,
            text=page.text[result.start:result.end],
            start=result.start,
            end=result.end,
            score=float(result.score),
            page_number=page.page_number,
            context=context,
        )
