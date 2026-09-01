from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


# Precision-first person recognition for common Italian business/property text.
# The multilingual NER model remains useful for natural prose, while these
# explicit role/party contexts recover complete names when the compact model
# splits a person into a first name and surname or mistakes the surname for ORG.
_NAME_TOKEN = r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]{1,30}"
_FULL_NAME = rf"{_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{1,3}}"
# ItalianContextValueRecognizer is compiled IGNORECASE because most field labels
# should be flexible. For honorific-only evidence we deliberately require the
# name itself to keep normal name capitalization, which avoids turning ordinary
# prose after "sig." into a PERSON result.
_STRICT_FULL_NAME = rf"(?-i:{_FULL_NAME})"


def build_person_recognizers() -> tuple[ItalianContextValueRecognizer, ...]:
    return (
        ItalianContextValueRecognizer(
            entity_type="PERSON",
            pattern=(
                rf"\b(?:locatore|conduttore|proprietari[oa]|inquilin[oa])\b"
                rf"\s*[:#-]?\s*(?P<value>{_FULL_NAME})"
                rf"(?=\s*(?:,|;|\bnat[oa]\b|\bresidente\b|\bdomiciliat[oa]\b))"
            ),
            score=0.995,
        ),
        ItalianContextValueRecognizer(
            entity_type="PERSON",
            pattern=(
                rf"\b(?:amministratore|amministratrice|ingegnere|architetto|"
                rf"avvocato|dottore|dottoressa|geometra)\b"
                rf"\s+(?P<value>{_FULL_NAME})"
                rf"(?=\s*(?:,|;|\bpresso\b|\bmentre\b|\bche\b|\bdi\b|$))"
            ),
            score=0.995,
        ),
        ItalianContextValueRecognizer(
            entity_type="PERSON",
            pattern=(
                rf"\b(?:sig(?:nor)?\.?|sig(?:nora|\.ra)\.?|sig(?:norina|\.na)\.?)"
                rf"\s+(?P<value>{_STRICT_FULL_NAME})"
                rf"(?=\s*(?:,|;|\bha\b|\bè\b|\bche\b|\bpresso\b|$))"
            ),
            score=0.99,
        ),
    )
