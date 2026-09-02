from __future__ import annotations

import re
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ai_pm_lab_privacy_gate.domain.models import Finding, PageContent
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile
from ai_pm_lab_privacy_gate.infrastructure.pii.languages import get_language_config


_UNIT_FALSE_VALUES = {
    "at",
    "for",
    "has",
    "includes",
    "is",
    "located",
    "number",
    "of",
    "was",
    "will",
}
_STREET_SUFFIX_RE = re.compile(
    r"\b(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Lane|Ln\.?|"
    r"Drive|Dr\.?|Court|Ct\.?|Parkway|Pkwy\.?|Highway|Hwy|Place|Pl\.?|Terrace|Ter\.?|Way)\b",
    re.IGNORECASE,
)
_ITALIAN_SEMANTIC_ENTITIES = {"PERSON", "ORGANIZATION", "LOCATION", "STREET_ADDRESS"}

# English precision-first cleanup. These values are field labels, public tool/product
# names, roles, or document concepts rather than private PERSON/ORG/LOCATION values.
_EN_NER_FIELD_NOISE = {
    "amex",
    "beneficiary iban",
    "bic",
    "borrower",
    "card",
    "dob",
    "driver",
    "email",
    "hpd complaint",
    "housing court",
    "iban",
    "invoice id",
    "lien",
    "mfa",
    "po box",
    "po id",
    "project budget",
    "projected noi",
    "seller credit",
    "state",
    "suite",
    "traveler",
    "visa",
}
_EN_PUBLIC_TECH_PHRASES = {
    "microsoft presidio",
}
_EN_NON_SENSITIVE_DATE_VALUES = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "today",
    "tomorrow",
    "yesterday",
    "noon",
    "midnight",
    "this morning",
    "this afternoon",
    "this evening",
    "next week",
    "next month",
    "next quarter",
    "next year",
    "last week",
    "last month",
    "last quarter",
    "last year",
}
_EN_CONTEXT_VALUE_FALSE_VALUES = {
    "INSURANCE_POLICY_ID": {"follows", "next"},
    "INVOICE_NUMBER": {"issued", "processing", "total"},
    "MAINTENANCE_TICKET_ID": {"management"},
    "VEHICLE_LICENSE_PLATE": {"is ready for"},
}
_EN_GENERIC_LOSES_TO = {
    "DATE_TIME": {
        "DATE_OF_BIRTH",
        "US_EIN",
        "CARD_LAST_FOUR",
        "SECURITY_CODE",
        "SAFE_COMBINATION",
    },
    "POSTAL_CODE": {
        "BUSINESS_REGISTRATION_NUMBER",
        "CASE_REFERENCE",
        "CONTRACT_ID",
        "CONTRACTOR_LICENSE",
        "CUSTOMER_ID",
        "HOUSING_LEGAL_CASE_ID",
        "IBAN_CODE",
        "INVOICE_NUMBER",
        "LEASE_ID",
        "LIEN_WAIVER_ID",
        "NYC_BBL",
        "PROPERTY_IDENTIFIER",
        "PURCHASE_ORDER_ID",
        "TENANT_ID",
        "US_EIN",
    },
    "PHONE_NUMBER": {"US_SSN"},
    "US_DRIVER_LICENSE": {"CONTRACTOR_LICENSE", "US_EIN"},
    "US_BANK_NUMBER": {"US_ROUTING_NUMBER"},
    "LOCKBOX_CODE": {"SAFE_COMBINATION"},
    "MONEY_AMOUNT": {
        "ACCOUNTS_PAYABLE_AMOUNT",
        "BROKER_COMMISSION",
        "CAPEX_BUDGET_AMOUNT",
        "CASH_TO_CLOSE",
        "CLOSING_COST_AMOUNT",
        "CLOSING_CREDIT",
        "COMMITTED_COST_AMOUNT",
        "CONTINGENCY_AMOUNT",
        "CONTRACTOR_BID_AMOUNT",
        "DEBT_SERVICE_AMOUNT",
        "EARNEST_MONEY_AMOUNT",
        "ESCROW_AMOUNT",
        "HOUSING_ASSISTANCE_AMOUNT",
        "INSURANCE_CLAIM_AMOUNT",
        "INSURANCE_DEDUCTIBLE_AMOUNT",
        "INSURANCE_PREMIUM_AMOUNT",
        "INVOICE_AMOUNT",
        "LATE_FEE_AMOUNT",
        "LOAN_AMOUNT",
        "LOAN_BALANCE",
        "MANAGEMENT_FEE",
        "MATERIAL_ALLOWANCE_AMOUNT",
        "NEGOTIATION_LIMIT_AMOUNT",
        "NOI_AMOUNT",
        "OFFER_PRICE",
        "OPERATING_BALANCE",
        "OWNER_DISTRIBUTION",
        "PAY_APPLICATION_AMOUNT",
        "PAYMENT_PLAN_AMOUNT",
        "PREAPPROVAL_AMOUNT",
        "PROJECT_BUDGET_AMOUNT",
        "PROPERTY_TAX_AMOUNT",
        "PURCHASE_ORDER_VALUE",
        "PURCHASE_PRICE",
        "REMAINING_CAPITAL_BUDGET",
        "RENT_AMOUNT",
        "RENT_CONCESSION_AMOUNT",
        "RESERVE_BALANCE",
        "RETAINAGE_AMOUNT",
        "SECURITY_DEPOSIT_AMOUNT",
        "SELLER_NET_PROCEEDS",
        "SUBCONTRACT_AMOUNT",
        "TENANT_BALANCE",
        "TENANT_INCOME_AMOUNT",
    },
}
_EN_LEGAL_SUFFIX_RE = re.compile(
    r"\b(?:LLC|Inc\.?|Corp\.?|Corporation|Ltd\.?|Company|Co\.?)\b",
    re.IGNORECASE,
)


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
            results = self._filter_context_value_false_positives(page.text, results)
            results = self._prefer_specific_english_results(results)
        resolved = self._without_overlaps(results)
        return [self._to_finding(page, result, index) for index, result in enumerate(resolved)]

    @staticmethod
    def _filter_context_value_false_positives(text: str, results: Iterable[Any]) -> list[Any]:
        """Drop structurally impossible values emitted by broad EN rules/NER.

        The filter is intentionally English-only at the call site. It rejects
        document/field labels, non-sensitive scheduling words, fragments embedded
        inside larger identifiers, and known context-recognizer grammar failures.
        Deterministic sensitive values are preserved unless the emitted span is
        structurally impossible for the claimed entity.
        """
        filtered: list[Any] = []
        for result in results:
            entity_type = str(result.entity_type)
            start = int(result.start)
            end = int(result.end)
            value = text[start:end].strip()
            normalized = " ".join(value.split()).casefold().strip(" .,:;#")
            line_left = text.rfind("\n", 0, start) + 1
            line_right = text.find("\n", end)
            if line_right < 0:
                line_right = len(text)
            line = text[line_left:line_right]
            line_normalized = " ".join(line.split()).casefold()

            invalid_values = _EN_CONTEXT_VALUE_FALSE_VALUES.get(entity_type)
            if invalid_values and normalized in invalid_values:
                continue

            if entity_type == "UNIT_NUMBER":
                if normalized in _UNIT_FALSE_VALUES:
                    continue

            if entity_type == "RENT_AMOUNT":
                compact = re.sub(r"\s+", "", value)
                if re.fullmatch(r"-\d{1,6}(?:\.0{1,2})?", compact):
                    tail = text[end : min(len(text), end + 80)]
                    same_sentence_tail = re.split(r"[\r\n.;]", tail, maxsplit=1)[0]
                    if _STREET_SUFFIX_RE.search(same_sentence_tail):
                        continue

            if entity_type in {"PERSON", "ORGANIZATION", "LOCATION"}:
                if normalized in _EN_NER_FIELD_NOISE:
                    continue
                if normalized in _EN_PUBLIC_TECH_PHRASES:
                    continue
                if re.fullmatch(r"ai\s*&\s*llms?\s*:\s*chatgpt", normalized):
                    continue
                if (
                    entity_type == "ORGANIZATION"
                    and re.search(r"\b(?:password|secret|token|credential|recovery code)\b", line_normalized)
                    and not re.search(r"\s", value)
                    and re.search(r"\d", value)
                ):
                    continue
                if entity_type == "LOCATION" and _EN_LEGAL_SUFFIX_RE.search(value):
                    continue

            if entity_type == "DATE_TIME":
                if normalized in _EN_NON_SENSITIVE_DATE_VALUES:
                    continue
                if re.fullmatch(r"box\s*#?\s*\d+", normalized):
                    continue
                if normalized == "last 4":
                    continue
                if re.search(
                    r"\b(?:ein|employer identification|card last|last four|alarm code|security code)\b",
                    line_normalized,
                ) and not re.search(r"\b(?:dob|date of birth|born)\b", line_normalized):
                    continue
                if re.fullmatch(r"\d{8}", value) and re.search(
                    r"\b(?:version|build|release)\b",
                    line_normalized,
                ):
                    continue
                if re.fullmatch(r"\d{4}", value) and re.search(
                    r"\b(?:project|scheduled|version|build|alarm|security|access|pin|card)\b",
                    line_normalized,
                ):
                    continue

            if entity_type == "POSTAL_CODE":
                prefix = text[max(line_left, start - 12) : start]
                embedded_directly = start > 0 and text[start - 1].isalnum()
                embedded_after_hyphen = bool(re.search(r"[A-Za-z0-9]-$", prefix))
                id_context = bool(
                    re.search(
                        r"\b(?:id|identifier|account|contract|client|matter|iban|tenant|resident|invoice|case|lease|ein|license)\b",
                        line_normalized,
                    )
                )
                if embedded_directly or (embedded_after_hyphen and id_context):
                    continue

            if entity_type == "US_DRIVER_LICENSE" and re.search(
                r"\b(?:ein|employer identification|contractor license)\b",
                line_normalized,
            ):
                prefix = text[max(line_left, start - 10) : start]
                if start > 0 and (text[start - 1] == "-" or re.search(r"[A-Za-z0-9]-$", prefix)):
                    continue

            if entity_type == "ORGANIZATION":
                if normalized in {"scan & protect", "scan and protect"}:
                    continue
                tail = text[end : min(len(text), end + 48)]
                if re.match(r"\s+property\s+(?:ids?|identifiers?)\b", tail, re.IGNORECASE):
                    continue

            filtered.append(result)
        return filtered

    @staticmethod
    def _prefer_specific_english_results(results: list[Any]) -> list[Any]:
        """Prefer a specific English PrivacyGate category over a generic overlap.

        Presidio can emit a high-confidence generic DATE_TIME, POSTAL_CODE,
        PHONE_NUMBER, bank number, or amount over the same characters recognized
        by a more specific PrivacyGate category. Remove only the generic result
        when an explicitly compatible specific category overlaps it; all other
        candidates keep the normal score-based arbitration.
        """
        items = list(results)
        filtered: list[Any] = []
        for candidate in items:
            entity_type = str(getattr(candidate, "entity_type", ""))
            winners = _EN_GENERIC_LOSES_TO.get(entity_type)
            if winners and any(
                other is not candidate
                and str(getattr(other, "entity_type", "")) in winners
                and int(candidate.start) < int(other.end)
                and int(other.start) < int(candidate.end)
                for other in items
            ):
                continue
            filtered.append(candidate)
        return filtered

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
    def _is_italian_neural_result(result: Any) -> bool:
        """Identify only PrivacyGate's optional Italian neural semantic layer."""
        metadata = getattr(result, "recognition_metadata", None) or {}
        recognizer_name = str(
            metadata.get("recognizer_name")
            or metadata.get("recognizer_identifier")
            or ""
        )
        return "italianneuralpiirecognizer" in recognizer_name.casefold()

    @classmethod
    def _prefer_standard_over_contained_italian_neural(cls, results: list[Any]) -> list[Any]:
        """Prevent Advanced Italian from shrinking a valid Standard semantic span.

        The optional neural model is a recall layer. If it predicts only a strict
        substring of an already-recognized Standard PERSON/ORG/LOCATION/STREET span,
        keep the broader Standard value even when the neural confidence is higher.
        This is source-specific, so English and unrelated recognizers are unchanged.
        """
        items = list(results)
        standard_semantic = [
            item
            for item in items
            if not cls._is_italian_neural_result(item)
            and str(getattr(item, "entity_type", "")) in _ITALIAN_SEMANTIC_ENTITIES
        ]
        filtered: list[Any] = []
        for candidate in items:
            if (
                cls._is_italian_neural_result(candidate)
                and str(getattr(candidate, "entity_type", "")) in _ITALIAN_SEMANTIC_ENTITIES
                and any(
                    int(container.start) <= int(candidate.start)
                    and int(container.end) >= int(candidate.end)
                    and (int(container.start), int(container.end))
                    != (int(candidate.start), int(candidate.end))
                    for container in standard_semantic
                )
            ):
                continue
            filtered.append(candidate)
        return filtered

    @classmethod
    def _without_overlaps(cls, results: list[Any]) -> list[Any]:
        """Prefer high-confidence results after source-aware Italian arbitration."""
        candidates = cls._prefer_standard_over_contained_italian_neural(list(results))
        accepted: list[Any] = []
        for candidate in sorted(
            candidates,
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
