from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path

from ai_pm_lab_privacy_gate.domain.models import PageContent
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.italian_neural import (
    ITALIAN_MODEL_DIR_ENV,
    ItalianNeuralPIIRecognizer,
)

from benchmark_italian_semantic_gap import (
    BENCHMARK_PROFILE,
    TARGET_ENTITIES,
    BenchmarkCase,
    ExpectedSpan,
    _expected_bounds,
    _format_predictions,
    _has_expected,
    _standard_engine_without_neural,
    _target_predictions,
)


# Holdout corpus created only after the first semantic benchmark and the real DOCX
# regression passed. Production rules must not be changed merely to fit this set.
# Its job is to measure generalization on new names, institutions, places, address
# shapes and ordinary Italian prose before we decide whether another rule is safe.
BLIND_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase("blind-person-01", "person", "Il notaio Roberto Gallo autenticherà la firma.", (ExpectedSpan("PERSON", "Roberto Gallo"),)),
    BenchmarkCase("blind-person-02", "person", "La dott.ssa Valentina Neri invierà la relazione.", (ExpectedSpan("PERSON", "Valentina Neri"),)),
    BenchmarkCase("blind-person-03", "person", "Responsabile sicurezza: Matteo Puglisi.", (ExpectedSpan("PERSON", "Matteo Puglisi"),)),
    BenchmarkCase("blind-person-04", "person", "La property manager Elisa Fontana coordina la consegna.", (ExpectedSpan("PERSON", "Elisa Fontana"),)),
    BenchmarkCase("blind-person-05", "person", "Il rag. Stefano Caruso ha verificato i conteggi.", (ExpectedSpan("PERSON", "Stefano Caruso"),)),
    BenchmarkCase("blind-person-06", "person", "La signora Beatrice Moretti ritirerà il verbale.", (ExpectedSpan("PERSON", "Beatrice Moretti"),)),
    BenchmarkCase("blind-person-07", "person", "Tecnico referente Davide Marchesi disponibile domani.", (ExpectedSpan("PERSON", "Davide Marchesi"),)),
    BenchmarkCase("blind-person-08", "person", "La progettista Ilaria Mancini presenterà le tavole.", (ExpectedSpan("PERSON", "Ilaria Mancini"),)),
    BenchmarkCase("blind-person-09", "person", "Il coordinatore Nicola Rinaldi apre la riunione.", (ExpectedSpan("PERSON", "Nicola Rinaldi"),)),
    BenchmarkCase("blind-person-10", "person", "Il documento è stato firmato da Federica D'Onofrio.", (ExpectedSpan("PERSON", "Federica D'Onofrio"),)),
    BenchmarkCase("blind-person-11", "person", "Il custode Marco De Rosa consegnerà il telecomando.", (ExpectedSpan("PERSON", "Marco De Rosa"),)),
    BenchmarkCase("blind-person-12", "person", "La mediatrice Alessia Lo Russo contatterà le parti.", (ExpectedSpan("PERSON", "Alessia Lo Russo"),)),
    BenchmarkCase("blind-person-13", "person", "Il direttore lavori Enrico Bellomo approva il SAL.", (ExpectedSpan("PERSON", "Enrico Bellomo"),)),
    BenchmarkCase("blind-person-14", "person", "La consulente legale Marta Di Biase prepara l'atto.", (ExpectedSpan("PERSON", "Marta Di Biase"),)),
    BenchmarkCase("blind-person-15", "person", "Il referente è Giovanni Maria Serra.", (ExpectedSpan("PERSON", "Giovanni Maria Serra"),)),

    BenchmarkCase("blind-org-01", "organization", "Il mandato è stato conferito a Immobiliare Quercia S.r.l.", (ExpectedSpan("ORGANIZATION", "Immobiliare Quercia S.r.l."),)),
    BenchmarkCase("blind-org-02", "organization", "La procura è depositata presso Studio Notarile Fontana.", (ExpectedSpan("ORGANIZATION", "Studio Notarile Fontana"),)),
    BenchmarkCase("blind-org-03", "organization", "L'annuncio è gestito da Agenzia Casa Navigli.", (ExpectedSpan("ORGANIZATION", "Agenzia Casa Navigli"),)),
    BenchmarkCase("blind-org-04", "organization", "I lavori sono affidati a Impresa Costruzioni Lombarda.", (ExpectedSpan("ORGANIZATION", "Impresa Costruzioni Lombarda"),)),
    BenchmarkCase("blind-org-05", "organization", "L'assemblea di Condominio Parco Verde è convocata venerdì.", (ExpectedSpan("ORGANIZATION", "Condominio Parco Verde"),)),
    BenchmarkCase("blind-org-06", "organization", "La domanda è stata inviata a Fondazione Abitare Insieme.", (ExpectedSpan("ORGANIZATION", "Fondazione Abitare Insieme"),)),
    BenchmarkCase("blind-org-07", "organization", "La ricerca è coordinata dall'Università degli Studi di Torino.", (ExpectedSpan("ORGANIZATION", "Università degli Studi di Torino"),)),
    BenchmarkCase("blind-org-08", "organization", "Il parere è stato richiesto all'Ordine degli Ingegneri di Napoli.", (ExpectedSpan("ORGANIZATION", "Ordine degli Ingegneri di Napoli"),)),
    BenchmarkCase("blind-org-09", "organization", "La visura proviene dalla Camera di Commercio di Bologna.", (ExpectedSpan("ORGANIZATION", "Camera di Commercio di Bologna"),)),
    BenchmarkCase("blind-org-10", "organization", "L'alloggio è amministrato da Istituto Autonomo Case Popolari.", (ExpectedSpan("ORGANIZATION", "Istituto Autonomo Case Popolari"),)),
    BenchmarkCase("blind-org-11", "organization", "La manutenzione è assegnata a Cooperativa Abitare Futuro.", (ExpectedSpan("ORGANIZATION", "Cooperativa Abitare Futuro"),)),
    BenchmarkCase("blind-org-12", "organization", "Il contratto quadro è intestato a Consorzio Stabili Centro.", (ExpectedSpan("ORGANIZATION", "Consorzio Stabili Centro"),)),
    BenchmarkCase("blind-org-13", "organization", "La pratica è seguita da Studio Associato Riva e Bassi.", (ExpectedSpan("ORGANIZATION", "Studio Associato Riva e Bassi"),)),
    BenchmarkCase("blind-org-14", "organization", "Il reclamo è sostenuto da Associazione Inquilini Uniti.", (ExpectedSpan("ORGANIZATION", "Associazione Inquilini Uniti"),)),
    BenchmarkCase("blind-org-15", "organization", "La commercializzazione è curata da Gruppo Immobiliare Levante.", (ExpectedSpan("ORGANIZATION", "Gruppo Immobiliare Levante"),)),

    BenchmarkCase("blind-location-01", "location", "Il sopralluogo è programmato a Monza.", (ExpectedSpan("LOCATION", "Monza"),)),
    BenchmarkCase("blind-location-02", "location", "La proprietaria si è trasferita ad Aosta.", (ExpectedSpan("LOCATION", "Aosta"),)),
    BenchmarkCase("blind-location-03", "location", "La seconda casa si trova a Riva del Garda.", (ExpectedSpan("LOCATION", "Riva del Garda"),)),
    BenchmarkCase("blind-location-04", "location", "Il tecnico arriva da Civitanova Marche.", (ExpectedSpan("LOCATION", "Civitanova Marche"),)),
    BenchmarkCase("blind-location-05", "location", "La sede temporanea è a San Giuliano Milanese.", (ExpectedSpan("LOCATION", "San Giuliano Milanese"),)),
    BenchmarkCase("blind-location-06", "location", "Il fascicolo è stato depositato a Torre del Greco.", (ExpectedSpan("LOCATION", "Torre del Greco"),)),
    BenchmarkCase("blind-location-07", "location", "La consegna è prevista a Conegliano.", (ExpectedSpan("LOCATION", "Conegliano"),)),
    BenchmarkCase("blind-location-08", "location", "Il locatore risiede a Porto San Giorgio.", (ExpectedSpan("LOCATION", "Porto San Giorgio"),)),
    BenchmarkCase("blind-location-09", "location", "L'atto è stato sottoscritto a Città di Castello.", (ExpectedSpan("LOCATION", "Città di Castello"),)),
    BenchmarkCase("blind-location-10", "location", "La società ha un deposito a Novi Ligure.", (ExpectedSpan("LOCATION", "Novi Ligure"),)),
    BenchmarkCase("blind-location-11", "location", "Il cliente proviene da Acireale.", (ExpectedSpan("LOCATION", "Acireale"),)),
    BenchmarkCase("blind-location-12", "location", "La riunione operativa si terrà a Gallarate.", (ExpectedSpan("LOCATION", "Gallarate"),)),
    BenchmarkCase("blind-location-13", "location", "L'immobile turistico è a Montecatini Terme.", (ExpectedSpan("LOCATION", "Montecatini Terme"),)),
    BenchmarkCase("blind-location-14", "location", "La documentazione è conservata a Casalecchio di Reno.", (ExpectedSpan("LOCATION", "Casalecchio di Reno"),)),
    BenchmarkCase("blind-location-15", "location", "Il nuovo domicilio è a Quartu Sant'Elena.", (ExpectedSpan("LOCATION", "Quartu Sant'Elena"),)),

    BenchmarkCase("blind-street-01", "street_address", "Il box è in Via dei Tigli 42.", (ExpectedSpan("STREET_ADDRESS", "Via dei Tigli 42"),)),
    BenchmarkCase("blind-street-02", "street_address", "L'ufficio si trova in Corso Garibaldi, 81.", (ExpectedSpan("STREET_ADDRESS", "Corso Garibaldi, 81"),)),
    BenchmarkCase("blind-street-03", "street_address", "La sede secondaria è in Viale della Libertà n. 6.", (ExpectedSpan("STREET_ADDRESS", "Viale della Libertà n. 6"),)),
    BenchmarkCase("blind-street-04", "street_address", "Il recapito indicato è Piazza San Carlo 11.", (ExpectedSpan("STREET_ADDRESS", "Piazza San Carlo 11"),)),
    BenchmarkCase("blind-street-05", "street_address", "Il magazzino è in Vicolo del Gelsomino 2/C.", (ExpectedSpan("STREET_ADDRESS", "Vicolo del Gelsomino 2/C"),)),
    BenchmarkCase("blind-street-06", "street_address", "Il fondo agricolo è in Località Pian del Lago 9.", (ExpectedSpan("STREET_ADDRESS", "Località Pian del Lago 9"),)),
    BenchmarkCase("blind-street-07", "street_address", "L'accesso carrabile è da Strada Comunale delle Vigne 4.", (ExpectedSpan("STREET_ADDRESS", "Strada Comunale delle Vigne 4"),)),
    BenchmarkCase("blind-street-08", "street_address", "Il conduttore abita in Via Fratelli Bandiera 33 interno 2.", (ExpectedSpan("STREET_ADDRESS", "Via Fratelli Bandiera 33"),)),
    BenchmarkCase("blind-street-09", "street_address", "La proprietaria risiede in Via delle Magnolie.", (ExpectedSpan("STREET_ADDRESS", "Via delle Magnolie"),)),
    BenchmarkCase("blind-street-10", "street_address", "La società ha sede in Piazza Sant'Oronzo 5.", (ExpectedSpan("STREET_ADDRESS", "Piazza Sant'Oronzo 5"),)),
    BenchmarkCase("blind-street-11", "street_address", "Il domicilio eletto è Salita Santa Lucia 16.", (ExpectedSpan("STREET_ADDRESS", "Salita Santa Lucia 16"),)),
    BenchmarkCase("blind-street-12", "street_address", "Il laboratorio è ubicato in Borgo San Frediano 27.", (ExpectedSpan("STREET_ADDRESS", "Borgo San Frediano 27"),)),
    BenchmarkCase("blind-street-13", "street_address", "Il cantiere è raggiungibile da SP 35, civico 8.", (ExpectedSpan("STREET_ADDRESS", "SP 35, civico 8"),)),
    BenchmarkCase("blind-street-14", "street_address", "La struttura ricettiva è sulla SS 16 Adriatica 105.", (ExpectedSpan("STREET_ADDRESS", "SS 16 Adriatica 105"),)),
    BenchmarkCase("blind-street-15", "street_address", "L'appartamento è in Via 4 Novembre 12.", (ExpectedSpan("STREET_ADDRESS", "Via 4 Novembre 12"),)),

    BenchmarkCase("blind-negative-01", "negative", "Il notaio deve controllare la firma prima dell'invio."),
    BenchmarkCase("blind-negative-02", "negative", "La fondazione del muro richiede un nuovo calcolo strutturale."),
    BenchmarkCase("blind-negative-03", "negative", "Il consorzio deve approvare il bilancio entro dicembre."),
    BenchmarkCase("blind-negative-04", "negative", "L'agenzia immobiliare ha pubblicato un nuovo annuncio."),
    BenchmarkCase("blind-negative-05", "negative", "Lo studio notarile resterà chiuso nel pomeriggio."),
    BenchmarkCase("blind-negative-06", "negative", "Il condominio necessita di un intervento sulla facciata."),
    BenchmarkCase("blind-negative-07", "negative", "Via libera ai lavori dopo il voto dell'assemblea."),
    BenchmarkCase("blind-negative-08", "negative", "Per arrivare al cantiere seguire la strada provinciale per sette chilometri."),
    BenchmarkCase("blind-negative-09", "negative", "La piazza centrale sarà chiusa al traffico domani."),
    BenchmarkCase("blind-negative-10", "negative", "Il responsabile sicurezza deve aggiornare la procedura."),
    BenchmarkCase("blind-negative-11", "negative", "L'organizzazione del sopralluogo richiede due squadre."),
    BenchmarkCase("blind-negative-12", "negative", "Il gruppo immobiliare valuterà nuove procedure interne."),
    BenchmarkCase("blind-negative-13", "negative", "La banca dati contiene soltanto record di prova."),
    BenchmarkCase("blind-negative-14", "negative", "Il comune di residenza deve essere indicato nel modulo."),
    BenchmarkCase("blind-negative-15", "negative", "La città di destinazione non è stata ancora scelta."),
    BenchmarkCase("blind-negative-16", "negative", "Lo studio associato ha aggiornato il proprio metodo di lavoro."),
    BenchmarkCase("blind-negative-17", "negative", "Il direttore lavori deve firmare il verbale entro sera."),
    BenchmarkCase("blind-negative-18", "negative", "Il signorile palazzo è stato restaurato di recente."),
    BenchmarkCase("blind-negative-19", "negative", "PERSON, ORGANIZATION, LOCATION e STREET_ADDRESS sono etichette tecniche."),
    BenchmarkCase("blind-negative-20", "negative", "Il campo indirizzo può rimanere vuoto durante questa prova."),
)


def run(model_dir: Path, output_csv: Path) -> int:
    neural = ItalianNeuralPIIRecognizer(model_dir=model_dir)
    if not neural.is_available:
        raise SystemExit(
            f"Italian neural model is not available at {model_dir}. "
            "Required: model.onnx, tokenizer.json, config.json"
        )

    standard = _standard_engine_without_neural()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    expected_total = 0
    standard_hits = 0
    neural_hits = 0
    combined_hits = 0
    teacher_gaps: list[str] = []
    both_missed: list[str] = []
    negative_total = 0
    standard_negative_clean = 0
    neural_negative_clean = 0
    combined_negative_clean = 0
    category_totals: dict[str, int] = defaultdict(int)
    category_standard: dict[str, int] = defaultdict(int)
    category_neural: dict[str, int] = defaultdict(int)
    category_combined: dict[str, int] = defaultdict(int)

    for case in BLIND_CASES:
        standard_items = standard.analyze_page(
            PageContent(page_number=1, text=case.text),
            BENCHMARK_PROFILE,
        )
        neural_items = neural.analyze(case.text, list(TARGET_ENTITIES))
        combined_items = PresidioPrivacyEngine._without_overlaps(
            [*standard_items, *neural_items]
        )

        standard_predictions = _target_predictions(standard_items, case.text)
        neural_predictions = _target_predictions(neural_items, case.text)
        combined_predictions = _target_predictions(combined_items, case.text)

        if not case.expected:
            negative_total += 1
            standard_clean = not standard_predictions
            neural_clean = not neural_predictions
            combined_clean = not combined_predictions
            standard_negative_clean += int(standard_clean)
            neural_negative_clean += int(neural_clean)
            combined_negative_clean += int(combined_clean)
            rows.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "text": case.text,
                    "expected_type": "NONE",
                    "expected_value": "",
                    "standard_hit": str(standard_clean),
                    "neural_hit": str(neural_clean),
                    "combined_hit": str(combined_clean),
                    "teacher_gap": "False",
                    "standard_predictions": _format_predictions(standard_predictions),
                    "neural_predictions": _format_predictions(neural_predictions),
                    "combined_predictions": _format_predictions(combined_predictions),
                }
            )
            continue

        for expected in case.expected:
            expected_total += 1
            category_totals[case.category] += 1
            start, end = _expected_bounds(case.text, expected.value)
            standard_hit = _has_expected(
                standard_predictions,
                entity_type=expected.entity_type,
                start=start,
                end=end,
            )
            neural_hit = _has_expected(
                neural_predictions,
                entity_type=expected.entity_type,
                start=start,
                end=end,
            )
            combined_hit = _has_expected(
                combined_predictions,
                entity_type=expected.entity_type,
                start=start,
                end=end,
            )
            teacher_gap = neural_hit and not standard_hit

            standard_hits += int(standard_hit)
            neural_hits += int(neural_hit)
            combined_hits += int(combined_hit)
            category_standard[case.category] += int(standard_hit)
            category_neural[case.category] += int(neural_hit)
            category_combined[case.category] += int(combined_hit)

            if teacher_gap:
                teacher_gaps.append(
                    f"{case.case_id}: {expected.entity_type} -> {expected.value!r}"
                )
            if not standard_hit and not neural_hit:
                both_missed.append(
                    f"{case.case_id}: {expected.entity_type} -> {expected.value!r}"
                )

            rows.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "text": case.text,
                    "expected_type": expected.entity_type,
                    "expected_value": expected.value,
                    "standard_hit": str(standard_hit),
                    "neural_hit": str(neural_hit),
                    "combined_hit": str(combined_hit),
                    "teacher_gap": str(teacher_gap),
                    "standard_predictions": _format_predictions(standard_predictions),
                    "neural_predictions": _format_predictions(neural_predictions),
                    "combined_predictions": _format_predictions(combined_predictions),
                }
            )

    fieldnames = list(rows[0]) if rows else []
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("PrivacyGate Italian semantic blind benchmark")
    print(f"Cases: {len(BLIND_CASES)}")
    print(f"Expected semantic spans: {expected_total}")
    print(f"Standard hits: {standard_hits}/{expected_total}")
    print(f"Neural hits: {neural_hits}/{expected_total}")
    print(f"Combined hits: {combined_hits}/{expected_total}")
    print(f"Teacher gaps (neural hit, standard miss): {len(teacher_gaps)}")
    print(f"Both missed: {len(both_missed)}")
    print(f"Negative cases: {negative_total}")
    print(f"Standard negative clean: {standard_negative_clean}/{negative_total}")
    print(f"Neural negative clean: {neural_negative_clean}/{negative_total}")
    print(f"Combined negative clean: {combined_negative_clean}/{negative_total}")
    print("\nCategory recall:")
    for category in ("person", "organization", "location", "street_address"):
        total = category_totals[category]
        print(
            f"  {category}: Standard {category_standard[category]}/{total} | "
            f"Neural {category_neural[category]}/{total} | "
            f"Combined {category_combined[category]}/{total}"
        )
    print(f"CSV: {output_csv.resolve()}")

    if teacher_gaps:
        print("\nTeacher gaps to inspect; do not auto-transfer:")
        for item in teacher_gaps:
            print(f"  - {item}")
    if both_missed:
        print("\nCases missed by both layers:")
        for item in both_missed:
            print(f"  - {item}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a holdout Italian semantic benchmark against Standard, the optional "
            "local neural recognizer, and their existing combined overlap logic."
        )
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=None,
        help=(
            "Directory containing model.onnx, tokenizer.json and config.json. "
            f"Defaults to ${ITALIAN_MODEL_DIR_ENV} when set."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/benchmarks/italian_semantic_blind.csv"),
        help="CSV report path.",
    )
    args = parser.parse_args()

    model_dir = args.model_dir
    if model_dir is None:
        configured = os.environ.get(ITALIAN_MODEL_DIR_ENV)
        if not configured:
            parser.error(
                f"pass --model-dir or set {ITALIAN_MODEL_DIR_ENV} to the local model directory"
            )
        model_dir = Path(configured)

    return run(model_dir.expanduser().resolve(), args.output)


if __name__ == "__main__":
    raise SystemExit(main())
