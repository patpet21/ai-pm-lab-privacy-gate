from __future__ import annotations

import re
from dataclasses import dataclass

from presidio_analyzer import EntityRecognizer, RecognizerResult

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.real_estate import (
    ContextRule,
    ContextValueRecognizer,
)


_SEP = r"[ \t]*(?::|=|#|[-–—])[ \t]*"
_IBAN_VALUE = r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}"


# Precision-first secrets/native expansion. Contextual rules require a strong
# label plus a structured value; they do not fire on bare words such as
# "API key", "token", "secret", "MAC", or "IBAN".
CONTEXT_RULES = (
    ContextRule(
        "API_KEY",
        rf"(?:openai[ \t]+)?api[ \t]+key{_SEP}(?P<value>sk-(?:proj-)?[A-Za-z0-9_-]{{20,}})\b",
        score=1.0,
    ),
    ContextRule(
        "ACCESS_TOKEN",
        rf"(?:github[ \t]+)?(?:access[ \t]+)?token{_SEP}(?P<value>(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]+)\b",
        score=1.0,
    ),
    ContextRule(
        "JWT_TOKEN",
        r"authorization[ \t]*:[ \t]*bearer[ \t]+(?P<value>[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})\b",
        score=1.0,
    ),
    ContextRule(
        "OAUTH_SECRET",
        rf"oauth(?:[ \t]+client)?[ \t]+secret{_SEP}(?P<value>oauth_[A-Za-z0-9_-]{{12,}})\b",
        score=1.0,
    ),
    ContextRule(
        "CLOUD_CREDENTIAL",
        rf"aws[ \t]+access[ \t]+key[ \t]+id{_SEP}(?P<value>(?:AKIA|ASIA)[A-Z0-9]{{15,16}})\b",
        score=1.0,
    ),
    ContextRule(
        "DATABASE_CREDENTIAL",
        rf"database[ \t]+url{_SEP}(?P<value>(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?):\/\/[^\s:@/]+:[^\s@/]+@[^\s]+)",
        score=1.0,
    ),
    ContextRule(
        "WEBHOOK_SECRET",
        rf"webhook(?:[ \t]+signing)?[ \t]+secret{_SEP}(?P<value>whsec_[A-Za-z0-9_-]{{16,}})\b",
        score=1.0,
    ),
    ContextRule(
        "MAC_ADDRESS",
        rf"(?:device[ \t]+)?mac(?:[ \t]+address)?{_SEP}(?P<value>(?:[0-9A-F]{{2}}:){{5}}[0-9A-F]{{2}})\b",
        score=1.0,
    ),
    ContextRule(
        "CRYPTO",
        rf"bitcoin[ \t]+address{_SEP}(?P<value>(?:bc1[ac-hj-np-z02-9]{{11,71}}|[13][a-km-zA-HJ-NP-Z1-9]{{25,34}}))\b",
        score=1.0,
    ),
    ContextRule(
        "IBAN_CODE",
        rf"(?:beneficiary[ \t]+)?iban{_SEP}(?P<value>{_IBAN_VALUE})\b",
        score=1.0,
    ),
    ContextRule(
        "IBAN_CODE",
        rf"(?im)^[ \t]*iban[ \t]*\r?\n[ \t]*(?P<value>{_IBAN_VALUE})\b",
        score=1.0,
    ),
)


@dataclass(frozen=True, slots=True)
class _BlockRule:
    entity_type: str
    pattern: str
    score: float = 1.0


class _BlockRecognizer(EntityRecognizer):
    """Recognize structured multiline secrets without broad DOTALL matching."""

    def __init__(self, rule: _BlockRule) -> None:
        super().__init__(
            supported_entities=[rule.entity_type],
            supported_language="en",
            name=f"PrivacyGateEnglish{rule.entity_type.title().replace('_', '')}Recognizer",
        )
        self._rule = rule
        self._regex = re.compile(rule.pattern, re.MULTILINE)

    def load(self) -> None:
        return None

    def analyze(self, text, entities, nlp_artifacts=None):  # noqa: ANN001
        if self._rule.entity_type not in entities:
            return []
        results: list[RecognizerResult] = []
        for match in self._regex.finditer(text):
            start, end = match.span("value")
            results.append(
                RecognizerResult(
                    entity_type=self._rule.entity_type,
                    start=start,
                    end=end,
                    score=self._rule.score,
                    recognition_metadata={
                        RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                    },
                )
            )
        return results


_BLOCK_RULES = (
    _BlockRule(
        "PRIVATE_KEY",
        r"(?P<value>-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n(?:[A-Za-z0-9+/=]{8,}[ \t]*\r?\n)+-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)",
    ),
)


def install_english_secrets_pack_recognizers(registry) -> None:  # noqa: ANN001
    for rule in CONTEXT_RULES:
        registry.add_recognizer(ContextValueRecognizer(rule))
    for rule in _BLOCK_RULES:
        registry.add_recognizer(_BlockRecognizer(rule))
