from __future__ import annotations

import importlib.util

import pytest

from ai_pm_lab_privacy_gate.domain.models import PageContent
from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.amounts import (
    build_amount_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.dates import (
    build_date_recognizers,
    is_valid_italian_birth_date,
)


def _values(recognizers, text: str, entity_type: str) -> list[str]:
    values: list[str] = []
    for recognizer in recognizers:
        if entity_type not in recognizer.supported_entities:
            continue
        for result in recognizer.analyze(text, [entity_type]):
            values.append(text[result.start : result.end])
    return values


def test_italian_birth_date_context_and_validation() -> None:
    recognizers = build_date_recognizers()

    assert is_valid_italian_birth_date("10 dicembre 1985")
    assert is_valid_italian_birth_date("10/12/1985")
    assert not is_valid_italian_birth_date("31 febbraio 1985")

    assert _values(
        recognizers,
        "Mario Rossi, nato a Roma il 10 dicembre 1985.",
        "DATE_OF_BIRTH",
    ) == ["10 dicembre 1985"]
    assert _values(
        recognizers,
        "Data di nascita: 10/12/1985",
        "DATE_OF_BIRTH",
    ) == ["10/12/1985"]
    assert _values(
        recognizers,
        "Contratto firmato il 10 dicembre 1985",
        "DATE_OF_BIRTH",
    ) == []


def test_italian_real_estate_amounts_are_contextual() -> None:
    recognizers = build_amount_recognizers()
    text = (
        "Importo del canone mensile: Euro 1.850,00.\n"
        "Deposito cauzionale: € 3.700,00.\n"
        "Prezzo di acquisto: Euro 425.000,00.\n"
        "Offerta di acquisto: 410.000,00 EUR.\n"
        "Compenso di gestione: Euro 150,00.\n"
        "Totale fattura: € 980,50."
    )

    assert _values(recognizers, text, "RENT_AMOUNT") == ["Euro 1.850,00"]
    assert _values(recognizers, text, "SECURITY_DEPOSIT_AMOUNT") == ["€ 3.700,00"]
    assert _values(recognizers, text, "PURCHASE_PRICE") == ["Euro 425.000,00"]
    assert _values(recognizers, text, "OFFER_PRICE") == ["410.000,00 EUR"]
    assert _values(recognizers, text, "MANAGEMENT_FEE") == ["Euro 150,00"]
    assert _values(recognizers, text, "INVOICE_AMOUNT") == ["€ 980,50"]

    assert _values(
        recognizers,
        "Numero pratica 1850 e anno 1985.",
        "RENT_AMOUNT",
    ) == []


@pytest.mark.skipif(
    importlib.util.find_spec("xx_ent_wiki_sm") is None,
    reason="xx_ent_wiki_sm is installed by requirements-lock.txt for release builds",
)
def test_real_fixture_classifies_pec_birth_date_and_monthly_rent() -> None:
    engine = PresidioPrivacyEngine(language="it")
    text = (
        "Locatore: Mario Rossi, nato a Roma il 10 dicembre 1985. "
        "PEC: amministrazione@auroragestioni.pec.it. "
        "Importo del canone mensile: Euro 1.850,00."
    )

    findings = engine.analyze_page(
        PageContent(page_number=1, text=text),
        get_profile("property_management"),
    )
    pairs = {(item.entity_type, item.text) for item in findings}

    assert ("DATE_OF_BIRTH", "10 dicembre 1985") in pairs
    assert ("IT_PEC_ADDRESS", "amministrazione@auroragestioni.pec.it") in pairs
    assert ("EMAIL_ADDRESS", "amministrazione@auroragestioni.pec.it") not in pairs
    assert ("RENT_AMOUNT", "Euro 1.850,00") in pairs
