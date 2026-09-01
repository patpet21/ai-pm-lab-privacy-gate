from __future__ import annotations

import re
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ai_pm_lab_privacy_gate.domain.models import Finding, PageContent
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile
from ai_pm_lab_privacy_gate.infrastructure.pii.languages import get_language_config


class PresidioPrivacyEngine:
    """Lazy, local-only Presidio adapter shared by every application surface."""

    def __init__(self, model_name: str | None = None, language: str = "en") -> None:
        language_config = get_language_config(language)
        self._language = language_config.code
        self._model_name = model_name or language_config.model_name
        self._analyzer: Any | None = None
        self._anonymizer: Any | None = None
        self._lock = threading.Lock()

    @property
    def document_language(self) -> str:
        return self._language

    @property
    def model_name(self) -> str:
        return self._model_name

    def _ensure_loaded(self) -> tuple[Any, Any]:
        if self._analyzer is not None and self._anonymizer is not None:
            return self._analyzer, self._anonymizer
        with self._lock:
            if self._analyzer is None:
                import spacy
                import tldextract
                from presidio_analyzer import AnalyzerEngine
                from presidio_analyzer.nlp_engine import NlpEngineProvider
                from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.registry import (
                    install_custom_recognizers,
                )

                # Presidio can download a missing spaCy model automatically. PrivacyGate
                # must remain local-only, so fail clearly instead of making a network call.
                if not (
                    spacy.util.is_package(self._model_name)
                    or Path(self._model_name).exists()
                ):
                    raise RuntimeError(
                        f"Local NLP model {self._model_name!r} is not installed. "
                        "PrivacyGate does not download NLP models at runtime."
                    )

                # Presidio's email recognizer normally lets tldextract refresh
                # the suffix list online. Use its bundled snapshot so the first
                # scan remains local-only.
                tldextract.extract = tldextract.TLDExtract(
                    suffix_list_urls=(), cache_dir=None
                )
                configuration: dict[str, Any] = {
                    "nlp_engine_name": "spacy",
                    "models": [
                        {"lang_code": self._language, "model_name": self._model_name}
                    ],
                }
                if self._language == "it":
                    # xx_ent_wiki_sm exposes PER / ORG / LOC / MISC. Keep only the
                    # privacy-relevant labels and map them onto Presidio entities.
                    configuration["ner_model_configuration"] = {
                        "model_to_presidio_entity_mapping": {
                            "PER": "PERSON",
                            "ORG": "ORGANIZATION",
                            "LOC": "LOCATION",
                        },
                        "labels_to_ignore": ["MISC"],
                        "default_score": 0.85,
                    }
                nlp_engine = NlpEngineProvider(nlp_configuration=configuration).create_engine()
                analyzer = AnalyzerEngine(
                    nlp_engine=nlp_engine,
                    supported_languages=[self._language],
                )
                install_custom_recognizers(
                    analyzer.registry,
                    languages=(self._language,),
                )
                self._analyzer = analyzer
            if self._anonymizer is None:
                from presidio_anonymizer import AnonymizerEngine

                self._anonymizer = AnonymizerEngine()
        return self._analyzer, self._anonymizer

    def analyze_page(self, page: PageContent, profile: PrivacyProfile) -> list[Finding]:
        analyzer, _ = self._ensure_loaded()
        supported = set(analyzer.get_supported_entities(language=self._language))
        requested_entities = list(profile.entities)
        if self._language == "it":
            from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian import (
                ITALIAN_ENTITY_TYPES,
            )

            requested_entities.extend(ITALIAN_ENTITY_TYPES)
        entities = [
            entity
            for entity in dict.fromkeys(requested_entities)
            if entity in supported
        ]
        results = analyzer.analyze(
            text=page.text,
            language=self._language,
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
        if self._language == "it":
            from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.guardrails import (
                filter_italian_ner_results,
            )

            results = filter_italian_ner_results(page.text, results)
            results = self._prefer_specific_italian_results(results)
        elif self._language == "en":
            from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.guardrails import (
                filter_english_contextual_results,
                filter_english_ner_results,
            )

            results = filter_english_ner_results(
                page.text,
                results,
                profile_key=profile.key,
            )
            # Apply generic numeric/date conflict filtering before overlap
            # resolution so a deterministic bank/ID recognizer can win instead
            # of a higher-scoring DATE_TIME guess on the same characters.
            results = filter_english_contextual_results(page.text, results)
        resolved = self._without_overlaps(results)
        return [self._to_finding(page, result, index) for index, result in enumerate(resolved)]

    @staticmethod
    def _prefer_specific_italian_results(results: list[Any]) -> list[Any]:
        """Prefer Italian-specific categories over overlapping generic ones.

        A PEC is also syntactically a normal email address, so both recognizers can
        fire on exactly the same span. Preserve the semantically richer IT_PEC_ADDRESS
        result and discard only the overlapping generic EMAIL_ADDRESS result.
        """
        pec_spans = [
            (item.start, item.end)
            for item in results
            if str(item.entity_type) == "IT_PEC_ADDRESS"
        ]
        if not pec_spans:
            return results
        return [
            item
            for item in results
            if not (
                str(item.entity_type) == "EMAIL_ADDRESS"
                and any(item.start < end and start < item.end for start, end in pec_spans)
            )
        ]

    @staticmethod
    def _without_overlaps(results: list[Any]) -> list[Any]:
        """Prefer high-confidence contextual IDs over generic numeric guesses."""
        accepted: list[Any] = []
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
    def _to_finding(page: PageContent, result: Any, index: int) -> Finding:
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
