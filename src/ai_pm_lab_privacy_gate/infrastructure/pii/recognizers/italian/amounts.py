from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contextual import (
    ItalianContextValueRecognizer,
)


_NUMBER = r"(?:\d{1,3}(?:\.\d{3})+|\d{1,9})(?:,\d{2})?"
_EURO_AMOUNT = rf"(?:(?:€\s*|EUR\s+|Euro\s+){_NUMBER}|{_NUMBER}\s*(?:€|EUR|Euro)?)"
_SEPARATOR = r"\s*(?::|=|-)?\s*"


def build_amount_recognizers() -> tuple[ItalianContextValueRecognizer, ...]:
    """Precision-first Italian property/finance amount recognizers.

    Values are returned only when a clear business label is present. This avoids
    treating every number or price in an Italian document as sensitive while
    reusing PrivacyGate's existing real-estate entity taxonomy.
    """
    return (
        ItalianContextValueRecognizer(
            entity_type="RENT_AMOUNT",
            pattern=(
                rf"\b(?:importo\s+del\s+)?(?:canone(?:\s+di\s+locazione|\s+mensile)?|"
                rf"affitto(?:\s+mensile)?|locazione\s+mensile)\b"
                rf"{_SEPARATOR}(?P<value>{_EURO_AMOUNT})"
            ),
            score=0.995,
        ),
        ItalianContextValueRecognizer(
            entity_type="SECURITY_DEPOSIT_AMOUNT",
            pattern=(
                rf"\b(?:deposito\s+cauzionale|deposito\s+di\s+garanzia|cauzione)\b"
                rf"{_SEPARATOR}(?P<value>{_EURO_AMOUNT})"
            ),
            score=0.995,
        ),
        ItalianContextValueRecognizer(
            entity_type="PURCHASE_PRICE",
            pattern=(
                rf"\b(?:prezzo\s+di\s+(?:acquisto|vendita)|prezzo\s+di\s+compravendita|"
                rf"corrispettivo\s+di\s+vendita)\b"
                rf"{_SEPARATOR}(?P<value>{_EURO_AMOUNT})"
            ),
            score=0.995,
        ),
        ItalianContextValueRecognizer(
            entity_type="OFFER_PRICE",
            pattern=(
                rf"\b(?:prezzo\s+offerto|offerta(?:\s+di\s+acquisto)?|"
                rf"proposta\s+di\s+acquisto)\b"
                rf"{_SEPARATOR}(?P<value>{_EURO_AMOUNT})"
            ),
            score=0.99,
        ),
        ItalianContextValueRecognizer(
            entity_type="MANAGEMENT_FEE",
            pattern=(
                rf"\b(?:compenso|commissione|onorario|fee)\s+(?:di\s+)?gestione\b"
                rf"{_SEPARATOR}(?P<value>{_EURO_AMOUNT})"
            ),
            score=0.99,
        ),
        ItalianContextValueRecognizer(
            entity_type="INVOICE_AMOUNT",
            pattern=(
                rf"\b(?:totale\s+fattura|importo\s+fattura|totale\s+da\s+pagare|"
                rf"importo\s+da\s+pagare)\b"
                rf"{_SEPARATOR}(?P<value>{_EURO_AMOUNT})"
            ),
            score=0.99,
        ),
    )
