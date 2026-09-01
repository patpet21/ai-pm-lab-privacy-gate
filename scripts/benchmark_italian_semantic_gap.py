from __future__ import annotations

import argparse
import csv
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ai_pm_lab_privacy_gate.domain.models import PageContent
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.italian_neural import (
    ITALIAN_MODEL_DIR_ENV,
    ItalianNeuralPIIRecognizer,
)


TARGET_ENTITIES = ("PERSON", "ORGANIZATION", "LOCATION", "STREET_ADDRESS")
_MATCH_COVERAGE = 0.80


@dataclass(frozen=True, slots=True)
class ExpectedSpan:
    entity_type: str
    value: str


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    category: str
    text: str
    expected: tuple[ExpectedSpan, ...] = ()


# Curated seed corpus for the four semantic categories where the optional neural
# recognizer can add useful recall. These examples intentionally mix real-estate,
# legal, administrative and ordinary Italian prose. Negative cases protect the
# precision-first behavior of the built-in detector while we mine neural wins.
CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase("person-01", "person", "La pratica è seguita dall'avvocato Chiara D'Amico.", (ExpectedSpan("PERSON", "Chiara D'Amico"),)),
    BenchmarkCase("person-02", "person", "Il geom. Paolo De Santis effettuerà il sopralluogo domani.", (ExpectedSpan("PERSON", "Paolo De Santis"),)),
    BenchmarkCase("person-03", "person", "Responsabile del procedimento: Gianluca Di Stefano.", (ExpectedSpan("PERSON", "Gianluca Di Stefano"),)),
    BenchmarkCase("person-04", "person", "Il referente commerciale è Maria Teresa Lo Monaco.", (ExpectedSpan("PERSON", "Maria Teresa Lo Monaco"),)),
    BenchmarkCase("person-05", "person", "La sig.ra Francesca Riva ha consegnato le chiavi.", (ExpectedSpan("PERSON", "Francesca Riva"),)),
    BenchmarkCase("person-06", "person", "Il tecnico incaricato Luca Bianchi ha firmato il verbale.", (ExpectedSpan("PERSON", "Luca Bianchi"),)),
    BenchmarkCase("person-07", "person", "La consulente Elena Della Valle parteciperà alla riunione.", (ExpectedSpan("PERSON", "Elena Della Valle"),)),
    BenchmarkCase("person-08", "person", "Il cliente Alessandro De Luca ha approvato il preventivo.", (ExpectedSpan("PERSON", "Alessandro De Luca"),)),
    BenchmarkCase("person-09", "person", "Firmato digitalmente da Andrea Di Pietro.", (ExpectedSpan("PERSON", "Andrea Di Pietro"),)),
    BenchmarkCase("person-10", "person", "Per informazioni contattare Sara De Marco presso la sede centrale.", (ExpectedSpan("PERSON", "Sara De Marco"),)),
    BenchmarkCase("person-11", "person", "Il perito Marco Antonio Ferri redigerà la relazione tecnica.", (ExpectedSpan("PERSON", "Marco Antonio Ferri"),)),
    BenchmarkCase("person-12", "person", "La delegata Anna Maria D'Angelo ritirerà la documentazione.", (ExpectedSpan("PERSON", "Anna Maria D'Angelo"),)),

    BenchmarkCase("org-01", "organization", "La documentazione è stata inviata allo Studio Tecnico Bellini.", (ExpectedSpan("ORGANIZATION", "Studio Tecnico Bellini"),)),
    BenchmarkCase("org-02", "organization", "L'incarico è stato affidato ad Agenzia Immobiliare Porta Nuova.", (ExpectedSpan("ORGANIZATION", "Agenzia Immobiliare Porta Nuova"),)),
    BenchmarkCase("org-03", "organization", "Il preventivo arriva da Impresa Edile Fratelli Greco.", (ExpectedSpan("ORGANIZATION", "Impresa Edile Fratelli Greco"),)),
    BenchmarkCase("org-04", "organization", "La controparte è assistita dallo Studio Legale De Angelis & Partners.", (ExpectedSpan("ORGANIZATION", "Studio Legale De Angelis & Partners"),)),
    BenchmarkCase("org-05", "organization", "La riunione si terrà presso Condominio Residenza Aurora.", (ExpectedSpan("ORGANIZATION", "Condominio Residenza Aurora"),)),
    BenchmarkCase("org-06", "organization", "Il finanziamento è gestito da Banca Popolare di Sondrio.", (ExpectedSpan("ORGANIZATION", "Banca Popolare di Sondrio"),)),
    BenchmarkCase("org-07", "organization", "La ricerca è stata svolta dal Politecnico di Milano.", (ExpectedSpan("ORGANIZATION", "Politecnico di Milano"),)),
    BenchmarkCase("org-08", "organization", "La pratica è stata trasmessa alla Fondazione Casa Serena.", (ExpectedSpan("ORGANIZATION", "Fondazione Casa Serena"),)),
    BenchmarkCase("org-09", "organization", "Il servizio è affidato all'Associazione Proprietari Italiani.", (ExpectedSpan("ORGANIZATION", "Associazione Proprietari Italiani"),)),
    BenchmarkCase("org-10", "organization", "La manutenzione è curata da Cooperativa Servizi Lombardia.", (ExpectedSpan("ORGANIZATION", "Cooperativa Servizi Lombardia"),)),
    BenchmarkCase("org-11", "organization", "La gestione è passata ad Amministrazioni Rossi e Associati.", (ExpectedSpan("ORGANIZATION", "Amministrazioni Rossi e Associati"),)),
    BenchmarkCase("org-12", "organization", "Il progetto è seguito da Consorzio Edilizia Nord.", (ExpectedSpan("ORGANIZATION", "Consorzio Edilizia Nord"),)),

    BenchmarkCase("location-01", "location", "L'immobile si trova a Sesto San Giovanni.", (ExpectedSpan("LOCATION", "Sesto San Giovanni"),)),
    BenchmarkCase("location-02", "location", "Il conduttore è domiciliato a Reggio Emilia.", (ExpectedSpan("LOCATION", "Reggio Emilia"),)),
    BenchmarkCase("location-03", "location", "La sede operativa è a San Donato Milanese.", (ExpectedSpan("LOCATION", "San Donato Milanese"),)),
    BenchmarkCase("location-04", "location", "Il cliente si è trasferito da Castellammare di Stabia.", (ExpectedSpan("LOCATION", "Castellammare di Stabia"),)),
    BenchmarkCase("location-05", "location", "Il cantiere ricade nel comune di Peschiera Borromeo.", (ExpectedSpan("LOCATION", "Peschiera Borromeo"),)),
    BenchmarkCase("location-06", "location", "La proprietà è situata a Cernusco sul Naviglio.", (ExpectedSpan("LOCATION", "Cernusco sul Naviglio"),)),
    BenchmarkCase("location-07", "location", "La consegna avverrà a San Benedetto del Tronto.", (ExpectedSpan("LOCATION", "San Benedetto del Tronto"),)),
    BenchmarkCase("location-08", "location", "L'atto è stato registrato a Desenzano del Garda.", (ExpectedSpan("LOCATION", "Desenzano del Garda"),)),
    BenchmarkCase("location-09", "location", "Il sopralluogo è previsto a Castel San Pietro Terme.", (ExpectedSpan("LOCATION", "Castel San Pietro Terme"),)),
    BenchmarkCase("location-10", "location", "Il tecnico arriva da Santa Maria Capua Vetere.", (ExpectedSpan("LOCATION", "Santa Maria Capua Vetere"),)),
    BenchmarkCase("location-11", "location", "La società possiede un ufficio a Bassano del Grappa.", (ExpectedSpan("LOCATION", "Bassano del Grappa"),)),
    BenchmarkCase("location-12", "location", "La riunione è fissata a Lido di Ostia.", (ExpectedSpan("LOCATION", "Lido di Ostia"),)),

    BenchmarkCase("street-01", "street_address", "L'immobile è sito in Via Giuseppe Verdi 24.", (ExpectedSpan("STREET_ADDRESS", "Via Giuseppe Verdi 24"),)),
    BenchmarkCase("street-02", "street_address", "La sede è in Corso Vittorio Emanuele II 14.", (ExpectedSpan("STREET_ADDRESS", "Corso Vittorio Emanuele II 14"),)),
    BenchmarkCase("street-03", "street_address", "Il garage si trova in Vicolo delle Rose 3/A.", (ExpectedSpan("STREET_ADDRESS", "Vicolo delle Rose 3/A"),)),
    BenchmarkCase("street-04", "street_address", "Recapitare la lettera in Piazza XXV Aprile 8.", (ExpectedSpan("STREET_ADDRESS", "Piazza XXV Aprile 8"),)),
    BenchmarkCase("street-05", "street_address", "L'accesso secondario è da Via Roma n. 18.", (ExpectedSpan("STREET_ADDRESS", "Via Roma n. 18"),)),
    BenchmarkCase("street-06", "street_address", "Il negozio è in Piazza della Repubblica, 5.", (ExpectedSpan("STREET_ADDRESS", "Piazza della Repubblica, 5"),)),
    BenchmarkCase("street-07", "street_address", "Il terreno confina con Località Cascina Nuova 7.", (ExpectedSpan("STREET_ADDRESS", "Località Cascina Nuova 7"),)),
    BenchmarkCase("street-08", "street_address", "Il proprietario risiede in Via Monte Napoleone.", (ExpectedSpan("STREET_ADDRESS", "Via Monte Napoleone"),)),
    BenchmarkCase("street-09", "street_address", "L'unità è ubicata in Viale Europa 22 interno 4.", (ExpectedSpan("STREET_ADDRESS", "Viale Europa 22"),)),
    BenchmarkCase("street-10", "street_address", "Il cantiere ha ingresso da Strada Provinciale 46 n. 7.", (ExpectedSpan("STREET_ADDRESS", "Strada Provinciale 46 n. 7"),)),
    BenchmarkCase("street-11", "street_address", "Il domicilio indicato è Largo Augusto 3.", (ExpectedSpan("STREET_ADDRESS", "Largo Augusto 3"),)),
    BenchmarkCase("street-12", "street_address", "La consegna va effettuata in Piazzale Loreto 12B.", (ExpectedSpan("STREET_ADDRESS", "Piazzale Loreto 12B"),)),

    BenchmarkCase("negative-01", "negative", "Il progetto prevede una nuova organizzazione dei lavori."),
    BenchmarkCase("negative-02", "negative", "La persona responsabile deve verificare il documento."),
    BenchmarkCase("negative-03", "negative", "Via libera alla proposta dopo la revisione tecnica."),
    BenchmarkCase("negative-04", "negative", "Il corso di formazione inizierà lunedì mattina."),
    BenchmarkCase("negative-05", "negative", "Lo studio preliminare è stato completato ieri."),
    BenchmarkCase("negative-06", "negative", "La società deve inviare la documentazione entro venerdì."),
    BenchmarkCase("negative-07", "negative", "L'amministratore verifica il registro prima della firma."),
    BenchmarkCase("negative-08", "negative", "Il cliente abita in città ma non ha indicato l'indirizzo."),
    BenchmarkCase("negative-09", "negative", "La piazza sarà riqualificata durante il prossimo anno."),
    BenchmarkCase("negative-10", "negative", "Il tecnico ha richiesto una via alternativa per l'accesso."),
    BenchmarkCase("negative-11", "negative", "Il responsabile dello studio ha approvato il progetto."),
    BenchmarkCase("negative-12", "negative", "Organizzazione, persona, location e street address sono categorie di test."),
)


BENCHMARK_PROFILE = PrivacyProfile(
    key="italian_semantic_benchmark",
    name="Italian semantic benchmark",
    description="Local benchmark for the four semantic Italian entity classes.",
    entities=TARGET_ENTITIES,
    threshold=0.35,
)


@contextmanager
def _temporary_env(name: str, value: str):
    previous = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def _standard_engine_without_neural() -> PresidioPrivacyEngine:
    # The neural recognizer resolves its path when the Presidio registry is built.
    # Point it at an empty temporary directory only while the standard engine is
    # initialized. The resulting engine then remains a faithful built-in baseline.
    with tempfile.TemporaryDirectory(prefix="privacygate-it-standard-") as empty_dir:
        with _temporary_env(ITALIAN_MODEL_DIR_ENV, empty_dir):
            engine = PresidioPrivacyEngine(language="it")
            engine._ensure_loaded()
            return engine


def _target_predictions(items: Iterable[object], text: str) -> list[tuple[str, int, int, str, float]]:
    predictions: list[tuple[str, int, int, str, float]] = []
    for item in items:
        entity_type = str(getattr(item, "entity_type"))
        if entity_type not in TARGET_ENTITIES:
            continue
        start = int(getattr(item, "start"))
        end = int(getattr(item, "end"))
        predictions.append(
            (
                entity_type,
                start,
                end,
                text[start:end],
                float(getattr(item, "score")),
            )
        )
    return sorted(predictions, key=lambda value: (value[1], value[2], value[0]))


def _expected_bounds(text: str, value: str) -> tuple[int, int]:
    start = text.find(value)
    if start < 0:
        raise ValueError(f"Benchmark value {value!r} is not present in {text!r}")
    return start, start + len(value)


def _matches_expected(
    prediction: tuple[str, int, int, str, float],
    *,
    entity_type: str,
    start: int,
    end: int,
) -> bool:
    if prediction[0] != entity_type:
        return False
    overlap = max(0, min(end, prediction[2]) - max(start, prediction[1]))
    expected_length = max(1, end - start)
    return (overlap / expected_length) >= _MATCH_COVERAGE


def _has_expected(
    predictions: list[tuple[str, int, int, str, float]],
    *,
    entity_type: str,
    start: int,
    end: int,
) -> bool:
    return any(
        _matches_expected(
            prediction,
            entity_type=entity_type,
            start=start,
            end=end,
        )
        for prediction in predictions
    )


def _format_predictions(predictions: list[tuple[str, int, int, str, float]]) -> str:
    return " | ".join(
        f"{entity}:{value!r}@{score:.3f}"
        for entity, _start, _end, value, score in predictions
    )


def run(model_dir: Path, output_csv: Path) -> int:
    neural = ItalianNeuralPIIRecognizer(model_dir=model_dir)
    if not neural.is_available:
        required = "model.onnx, tokenizer.json, config.json"
        raise SystemExit(
            f"Italian neural model is not available at {model_dir}. Required: {required}"
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

    for case in CASES:
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

    print("PrivacyGate Italian semantic gap benchmark")
    print(f"Cases: {len(CASES)}")
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
    print(f"CSV: {output_csv.resolve()}")

    if teacher_gaps:
        print("\nTeacher gaps to inspect for lightweight rules/context:")
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
            "Compare PrivacyGate's built-in Italian semantic detector with the "
            "optional local neural recognizer. No network calls are made."
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
        default=Path("build/benchmarks/italian_semantic_gap.csv"),
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
