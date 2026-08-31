from __future__ import annotations

import importlib.util
from dataclasses import replace

import pytest

from ai_pm_lab_privacy_gate.domain.models import PageContent
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.amounts import (
    build_amount_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.dates import (
    build_date_recognizers,
    is_valid_italian_birth_date,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.fiscal import (
    build_fiscal_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.references import (
    build_reference_recognizers,
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


def test_contextual_codice_fiscale_protects_cf_shaped_test_data() -> None:
    recognizers = build_fiscal_recognizers()
    fake_but_cf_shaped = "FRSPTR84H14F205X"

    variants = (
        f"Il suo codice fiscale è {fake_but_cf_shaped}.",
        f"Il codice fiscale del cliente è {fake_but_cf_shaped}.",
        f"CF intestatario: {fake_but_cf_shaped}",
        f"C.F. del proprietario n. {fake_but_cf_shaped}",
        f"Codice fiscale dell'intestatario: {fake_but_cf_shaped}",
    )
    for text in variants:
        assert _values(recognizers, text, "IT_FISCAL_CODE") == [fake_but_cf_shaped]

    # Keep checksum-invalid CF-shaped strings out of generic prose: the fallback
    # is intentionally privacy-first only when an explicit fiscal-code label is present.
    assert _values(
        recognizers,
        f"Riferimento interno {fake_but_cf_shaped}.",
        "IT_FISCAL_CODE",
    ) == []


def test_italian_case_reference_is_contextual() -> None:
    recognizers = build_reference_recognizers()

    variants = (
        ("La pratica di riferimento è RE-2026-45871 e riguarda l'immobile.", "RE-2026-45871"),
        ("Numero pratica: PM-2026-0042", "PM-2026-0042"),
        ("Pratica del cliente: RE-2026-45871", "RE-2026-45871"),
        ("Pratica n. PM-2026-0042", "PM-2026-0042"),
        ("Case ID: NYC-RE-2026-45871", "NYC-RE-2026-45871"),
    )
    for text, expected in variants:
        assert _values(recognizers, text, "CASE_REFERENCE") == [expected]

    assert _values(
        recognizers,
        "La costruzione è stata completata nel 2026.",
        "CASE_REFERENCE",
    ) == []


def test_property_management_financial_scope_keeps_case_reference() -> None:
    base_profile = get_profile("property_management")
    scoped_entities = entities_for_scope(base_profile, "financial")

    assert "CASE_REFERENCE" in scoped_entities


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


@pytest.mark.skipif(
    importlib.util.find_spec("xx_ent_wiki_sm") is None,
    reason="xx_ent_wiki_sm is installed by requirements-lock.txt for release builds",
)
def test_property_management_fixture_masks_fiscal_code_and_case_reference() -> None:
    engine = PresidioPrivacyEngine(language="it")
    base_profile = get_profile("property_management")
    profile = replace(
        base_profile,
        entities=entities_for_scope(base_profile, "financial"),
    )
    text = (
        "Il codice fiscale del cliente è FRSPTR84H14F205X. "
        "La pratica di riferimento è RE-2026-45871 e riguarda l'immobile."
    )

    findings = engine.analyze_page(
        PageContent(page_number=1, text=text),
        profile,
    )
    pairs = {(item.entity_type, item.text) for item in findings}

    assert ("IT_FISCAL_CODE", "FRSPTR84H14F205X") in pairs
    assert ("CASE_REFERENCE", "RE-2026-45871") in pairs
