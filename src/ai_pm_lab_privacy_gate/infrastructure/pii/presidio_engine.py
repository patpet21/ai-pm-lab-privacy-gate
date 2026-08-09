from __future__ import annotations

import threading
from collections.abc import Iterable

import tldextract
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from ai_pm_lab_privacy_gate.domain.models import Finding, PageContent
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.registry import install_custom_recognizers


# Presidio's email recognizer calls tldextract. Its default singleton attempts to
# refresh the Public Suffix List over the network on first use. Replace only that
# singleton function with the bundled snapshot implementation to enforce offline
# behavior while retaining Presidio's email validation.
_offline_tld_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)
tldextract.extract = _offline_tld_extract


class PresidioPrivacyEngine:
    """Lazy, local-only Presidio adapter shared by every application surface."""

    def __init__(self, model_name: str = "en_core_web_sm") -> None:
        self._model_name = model_name
        self._analyzer: AnalyzerEngine | None = None
        self._anonymizer: AnonymizerEngine | None = None
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> tuple[AnalyzerEngine, AnonymizerEngine]:
        if self._analyzer is not None and self._anonymizer is not None:
            return self._analyzer, self._anonymizer
        with self._lock:
            if self._analyzer is None:
                configuration = {
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": "en", "model_name": self._model_name}],
                }
                nlp_engine = NlpEngineProvider(nlp_configuration=configuration).create_engine()
                analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
                install_custom_recognizers(analyzer.registry)
                self._analyzer = analyzer
            if self._anonymizer is None:
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
        return [self._to_finding(page, result, index) for index, result in enumerate(results)]

    def protect_text(self, text: str, findings: Iterable[Finding]) -> str:
        selected = list(findings)
        if not selected:
            return text
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
