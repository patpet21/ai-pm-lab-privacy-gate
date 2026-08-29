from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.financial import (
    build_financial_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.fiscal import (
    build_fiscal_recognizers,
)


ITALIAN_ENTITY_TYPES = (
    "IT_FISCAL_CODE",
    "IT_VAT_NUMBER",
    "IBAN_CODE",
)


def install_italian_recognizers(registry) -> None:  # noqa: ANN001
    """Install deterministic recognizers that are safe to run without an NLP model."""
    for recognizer in (*build_fiscal_recognizers(), *build_financial_recognizers()):
        registry.add_recognizer(recognizer)
