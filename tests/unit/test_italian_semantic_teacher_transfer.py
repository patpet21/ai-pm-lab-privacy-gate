from __future__ import annotations

from collections.abc import Iterable

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.addresses import (
    build_address_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.business import (
    build_business_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.people import (
    build_person_recognizers,
)


def _values(recognizers: Iterable[object], text: str, entity_type: str) -> set[str]:
    values: set[str] = set()
    for recognizer in recognizers:
        for result in recognizer.analyze(text, [entity_type], nlp_artifacts=None):
            if str(result.entity_type) == entity_type:
                values.add(text[int(result.start) : int(result.end)])
    return values


def test_teacher_person_gap_transfers_to_lightweight_honorific_rule() -> None:
    text = "La sig.ra Francesca Riva ha consegnato le chiavi."
    assert "Francesca Riva" in _values(build_person_recognizers(), text, "PERSON")


def test_teacher_organization_gaps_transfer_to_semantic_prefix_rules() -> None:
    cases = (
        ("L'incarico è stato affidato ad Agenzia Immobiliare Porta Nuova.", "Agenzia Immobiliare Porta Nuova"),
        ("Il preventivo arriva da Impresa Edile Fratelli Greco.", "Impresa Edile Fratelli Greco"),
        ("La riunione si terrà presso Condominio Residenza Aurora.", "Condominio Residenza Aurora"),
        ("Il finanziamento è gestito da Banca Popolare di Sondrio.", "Banca Popolare di Sondrio"),
        ("La ricerca è stata svolta dal Politecnico di Milano.", "Politecnico di Milano"),
        ("La pratica è stata trasmessa alla Fondazione Casa Serena.", "Fondazione Casa Serena"),
        ("La manutenzione è curata da Cooperativa Servizi Lombardia.", "Cooperativa Servizi Lombardia"),
        ("La gestione è passata ad Amministrazioni Rossi e Associati.", "Amministrazioni Rossi e Associati"),
        ("Il progetto è seguito da Consorzio Edilizia Nord.", "Consorzio Edilizia Nord"),
    )
    recognizers = build_business_recognizers()
    for text, expected in cases:
        assert expected in _values(recognizers, text, "ORGANIZATION")


def test_teacher_street_gaps_transfer_without_global_numberless_street_rule() -> None:
    cases = (
        ("Il negozio è in Piazza della Repubblica, 5.", "Piazza della Repubblica, 5"),
        ("Il terreno confina con Località Cascina Nuova 7.", "Località Cascina Nuova 7"),
        ("Il proprietario risiede in Via Monte Napoleone.", "Via Monte Napoleone"),
        ("Il cantiere ha ingresso da Strada Provinciale 46 n. 7.", "Strada Provinciale 46 n. 7"),
    )
    recognizers = build_address_recognizers()
    for text, expected in cases:
        assert expected in _values(recognizers, text, "STREET_ADDRESS")


def test_teacher_transfer_rules_keep_benchmark_negatives_clean() -> None:
    people = build_person_recognizers()
    businesses = build_business_recognizers()
    addresses = build_address_recognizers()

    assert not _values(people, "Il sig. responsabile deve verificare il documento.", "PERSON")
    assert not _values(businesses, "La banca dati sarà aggiornata domani.", "ORGANIZATION")
    assert not _values(businesses, "Il condominio necessita di manutenzione.", "ORGANIZATION")
    assert not _values(addresses, "Via libera alla proposta dopo la revisione tecnica.", "STREET_ADDRESS")
    assert not _values(addresses, "Il tecnico ha richiesto una via alternativa per l'accesso.", "STREET_ADDRESS")
    assert not _values(addresses, "La piazza sarà riqualificata durante il prossimo anno.", "STREET_ADDRESS")
