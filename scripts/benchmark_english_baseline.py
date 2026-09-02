from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, PageContent
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile


DEFAULT_CORPUS = Path("benchmarks/english/v1")
DEFAULT_CSV = Path("build/benchmarks/english_baseline_v1.csv")
DEFAULT_SUMMARY = Path("build/benchmarks/english_baseline_v1_summary.json")
EXPECTED_CASES = 300
EXPECTED_SPANS = 227
EXPECTED_NEGATIVES = 75
RELAXED_OVERLAP = 0.80


@dataclass(frozen=True, slots=True)
class ExpectedSpan:
    entity_type: str
    value: str
    page_number: int
    start: int
    end: int

    @property
    def key(self) -> tuple[int, int, int, str]:
        return (self.page_number, self.start, self.end, self.entity_type)


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    group: str
    genre: str
    source_kind: str
    coverage: str
    format_tags: tuple[str, ...]
    pages: tuple[str, ...]
    expected: tuple[ExpectedSpan, ...]


@dataclass(frozen=True, slots=True)
class Prediction:
    entity_type: str
    value: str
    page_number: int
    start: int
    end: int
    score: float

    @property
    def key(self) -> tuple[int, int, int, str]:
        return (self.page_number, self.start, self.end, self.entity_type)


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not-installed"


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def _corpus_files(path: Path) -> tuple[Path, ...]:
    if path.is_dir():
        files = tuple(sorted(path.glob("*.jsonl")))
    else:
        files = (path,)
    if not files:
        raise ValueError(f"No JSONL benchmark files found in {path}")
    return files


def _load_cases(path: Path) -> tuple[BenchmarkCase, ...]:
    cases: list[BenchmarkCase] = []
    seen_ids: set[str] = set()

    for corpus_file in _corpus_files(path):
        with corpus_file.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError(
                        f"{corpus_file}:{line_number}: row must be a JSON object"
                    )

                case_id = str(payload.get("id", "")).strip()
                if not case_id:
                    raise ValueError(f"{corpus_file}:{line_number}: missing id")
                if case_id in seen_ids:
                    raise ValueError(
                        f"{corpus_file}:{line_number}: duplicate id {case_id}"
                    )
                seen_ids.add(case_id)

                if "pages" in payload:
                    raw_pages = payload["pages"]
                    if (
                        not isinstance(raw_pages, list)
                        or not raw_pages
                        or not all(isinstance(value, str) for value in raw_pages)
                    ):
                        raise ValueError(
                            f"{corpus_file}:{line_number}: pages must be strings"
                        )
                    if "text" in payload:
                        raise ValueError(
                            f"{corpus_file}:{line_number}: use text or pages, not both"
                        )
                    pages = tuple(raw_pages)
                else:
                    text = payload.get("text")
                    if not isinstance(text, str):
                        raise ValueError(
                            f"{corpus_file}:{line_number}: text must be a string"
                        )
                    pages = (text,)

                raw_expected = payload.get("expected", [])
                if not isinstance(raw_expected, list):
                    raise ValueError(
                        f"{corpus_file}:{line_number}: expected must be a list"
                    )
                expected: list[ExpectedSpan] = []
                seen_spans: set[tuple[int, int, int, str]] = set()
                for item in raw_expected:
                    entity_type = str(item["entity_type"])
                    value = str(item["value"])
                    page_number = int(item.get("page_number", 1))
                    start = int(item["start"])
                    end = int(item["end"])
                    if not (1 <= page_number <= len(pages)):
                        raise ValueError(
                            f"{corpus_file}:{line_number}: invalid page {page_number}"
                        )
                    page_text = pages[page_number - 1]
                    if start < 0 or end <= start or end > len(page_text):
                        raise ValueError(
                            f"{corpus_file}:{line_number}: invalid span {start}:{end}"
                        )
                    if page_text[start:end] != value:
                        raise ValueError(
                            f"{corpus_file}:{line_number}: span text mismatch for "
                            f"{entity_type}: expected {value!r}, got {page_text[start:end]!r}"
                        )
                    span = ExpectedSpan(
                        entity_type=entity_type,
                        value=value,
                        page_number=page_number,
                        start=start,
                        end=end,
                    )
                    if span.key in seen_spans:
                        raise ValueError(
                            f"{corpus_file}:{line_number}: duplicate expected span {span.key}"
                        )
                    seen_spans.add(span.key)
                    expected.append(span)

                coverage = str(payload.get("coverage", "current"))
                if coverage not in {"current", "roadmap"}:
                    raise ValueError(
                        f"{corpus_file}:{line_number}: invalid coverage {coverage!r}"
                    )
                tags = payload.get("format_tags", [])
                if not isinstance(tags, list):
                    raise ValueError(
                        f"{corpus_file}:{line_number}: format_tags must be a list"
                    )

                cases.append(
                    BenchmarkCase(
                        case_id=case_id,
                        group=str(payload["group"]),
                        genre=str(payload["genre"]),
                        source_kind=str(payload.get("source_kind", "text")),
                        coverage=coverage,
                        format_tags=tuple(str(value) for value in tags),
                        pages=pages,
                        expected=tuple(expected),
                    )
                )

    expected_spans = sum(len(case.expected) for case in cases)
    negative_cases = sum(not case.expected for case in cases)
    if len(cases) != EXPECTED_CASES:
        raise ValueError(
            f"Frozen English v1 corpus must contain {EXPECTED_CASES} cases; "
            f"found {len(cases)}"
        )
    if expected_spans != EXPECTED_SPANS:
        raise ValueError(
            f"Frozen English v1 corpus must contain {EXPECTED_SPANS} spans; "
            f"found {expected_spans}"
        )
    if negative_cases != EXPECTED_NEGATIVES:
        raise ValueError(
            f"Frozen English v1 corpus must contain {EXPECTED_NEGATIVES} negatives; "
            f"found {negative_cases}"
        )
    return tuple(cases)


def _document(case: BenchmarkCase) -> AnalysisDocument:
    return AnalysisDocument(
        source_kind=case.source_kind,
        pages=tuple(
            PageContent(page_number=index, text=text)
            for index, text in enumerate(case.pages, start=1)
        ),
    )


def _prediction(item: Any) -> Prediction:
    return Prediction(
        entity_type=str(item.entity_type),
        value=str(item.text),
        page_number=int(item.page_number),
        start=int(item.start),
        end=int(item.end),
        score=float(item.score),
    )


def _overlap(expected: ExpectedSpan, prediction: Prediction) -> float:
    if expected.page_number != prediction.page_number:
        return 0.0
    width = max(1, expected.end - expected.start)
    overlap = max(
        0,
        min(expected.end, prediction.end) - max(expected.start, prediction.start),
    )
    return overlap / width


def _category_hit(expected: ExpectedSpan, predictions: Iterable[Prediction]) -> bool:
    return any(
        prediction.entity_type == expected.entity_type
        and _overlap(expected, prediction) >= RELAXED_OVERLAP
        for prediction in predictions
    )


def _wrong_category(expected: ExpectedSpan, predictions: Iterable[Prediction]) -> list[str]:
    return [
        f"{prediction.entity_type}:{prediction.value!r}"
        for prediction in predictions
        if prediction.entity_type != expected.entity_type
        and _overlap(expected, prediction) >= RELAXED_OVERLAP
    ]


def _metric(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _metric_text(data: dict[str, float | int]) -> str:
    return (
        f"P={float(data['precision']):.3f} "
        f"R={float(data['recall']):.3f} "
        f"F1={float(data['f1']):.3f} "
        f"(TP={data['tp']} FP={data['fp']} FN={data['fn']})"
    )


def run(
    corpus: Path,
    output_csv: Path,
    summary_path: Path,
    *,
    profile_key: str,
    scope_key: str,
) -> int:
    cases = _load_cases(corpus)
    base_profile = get_profile(profile_key)
    enabled_entities = entities_for_scope(base_profile, scope_key)
    benchmark_profile = replace(base_profile, entities=enabled_entities)
    service = PrivacyGateService()

    total = Counter()
    by_group: dict[str, Counter[str]] = defaultdict(Counter)
    by_coverage: dict[str, Counter[str]] = defaultdict(Counter)
    by_entity: dict[str, Counter[str]] = defaultdict(Counter)
    rows: list[dict[str, str]] = []
    correct_category_hits = 0
    negative_clean = 0
    perfect_cases = 0

    for case in cases:
        findings = service.analyze(
            _document(case),
            benchmark_profile,
            language="en",
        )
        predictions = tuple(_prediction(item) for item in findings)
        expected_by_key = {item.key: item for item in case.expected}
        predicted_by_key = {item.key: item for item in predictions}

        exact_keys = expected_by_key.keys() & predicted_by_key.keys()
        misses = [
            item for key, item in expected_by_key.items() if key not in predicted_by_key
        ]
        extras = [
            item for key, item in predicted_by_key.items() if key not in expected_by_key
        ]
        tp, fp, fn = len(exact_keys), len(extras), len(misses)
        perfect = tp == len(case.expected) and fp == 0 and fn == 0
        clean_negative = not case.expected and not predictions

        total.update(cases=1, expected=len(case.expected), tp=tp, fp=fp, fn=fn)
        total["perfect"] += int(perfect)
        total["negative"] += int(not case.expected)
        total["negative_clean"] += int(clean_negative)
        perfect_cases += int(perfect)
        negative_clean += int(clean_negative)

        group = by_group[case.group]
        group.update(cases=1, expected=len(case.expected), tp=tp, fp=fp, fn=fn)
        group["perfect"] += int(perfect)
        group["negative"] += int(not case.expected)
        group["negative_clean"] += int(clean_negative)

        coverage = by_coverage[case.coverage]
        coverage.update(cases=1, expected=len(case.expected), tp=tp, fp=fp, fn=fn)
        coverage["perfect"] += int(perfect)

        case_category_hits = sum(
            int(_category_hit(expected, predictions)) for expected in case.expected
        )
        correct_category_hits += case_category_hits

        for expected in case.expected:
            bucket = by_entity[expected.entity_type]
            bucket["expected"] += 1
            if expected.key in predicted_by_key:
                bucket["tp"] += 1
            else:
                bucket["fn"] += 1
        for prediction in extras:
            by_entity[prediction.entity_type]["fp"] += 1

        wrong: list[str] = []
        for expected in misses:
            overlaps = _wrong_category(expected, predictions)
            if overlaps:
                wrong.append(
                    f"{expected.entity_type}:{expected.value!r} -> " + ", ".join(overlaps)
                )

        rows.append(
            {
                "case_id": case.case_id,
                "group": case.group,
                "genre": case.genre,
                "coverage": case.coverage,
                "source_kind": case.source_kind,
                "format_tags": "|".join(case.format_tags),
                "expected_count": str(len(case.expected)),
                "prediction_count": str(len(predictions)),
                "exact_tp": str(tp),
                "fp": str(fp),
                "fn": str(fn),
                "correct_category_hits": str(case_category_hits),
                "perfect": str(perfect),
                "negative_clean": str(clean_negative) if not case.expected else "",
                "expected": json.dumps(
                    [
                        {
                            "entity_type": item.entity_type,
                            "value": item.value,
                            "page_number": item.page_number,
                            "start": item.start,
                            "end": item.end,
                        }
                        for item in case.expected
                    ],
                    ensure_ascii=False,
                ),
                "predictions": json.dumps(
                    [
                        {
                            "entity_type": item.entity_type,
                            "value": item.value,
                            "page_number": item.page_number,
                            "start": item.start,
                            "end": item.end,
                            "score": round(item.score, 6),
                        }
                        for item in predictions
                    ],
                    ensure_ascii=False,
                ),
                "misses": json.dumps(
                    [
                        {
                            "entity_type": item.entity_type,
                            "value": item.value,
                            "page_number": item.page_number,
                            "start": item.start,
                            "end": item.end,
                        }
                        for item in misses
                    ],
                    ensure_ascii=False,
                ),
                "extras": json.dumps(
                    [
                        {
                            "entity_type": item.entity_type,
                            "value": item.value,
                            "page_number": item.page_number,
                            "start": item.start,
                            "end": item.end,
                            "score": round(item.score, 6),
                        }
                        for item in extras
                    ],
                    ensure_ascii=False,
                ),
                "wrong_category_overlap": " | ".join(wrong),
            }
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    strict = _metric(total["tp"], total["fp"], total["fn"])
    current = _metric(
        by_coverage["current"]["tp"],
        by_coverage["current"]["fp"],
        by_coverage["current"]["fn"],
    )
    roadmap = _metric(
        by_coverage["roadmap"]["tp"],
        by_coverage["roadmap"]["fp"],
        by_coverage["roadmap"]["fn"],
    )

    group_summary = {
        name: {
            **_metric(data["tp"], data["fp"], data["fn"]),
            "cases": data["cases"],
            "expected": data["expected"],
            "perfect_cases": data["perfect"],
            "negative_cases": data["negative"],
            "negative_clean": data["negative_clean"],
        }
        for name, data in sorted(by_group.items())
    }
    entity_summary = {
        name: {
            **_metric(data["tp"], data["fp"], data["fn"]),
            "expected": data["expected"],
        }
        for name, data in sorted(by_entity.items())
    }

    expected_types = {
        expected.entity_type for case in cases for expected in case.expected
    }
    summary = {
        "corpus": str(corpus),
        "runtime": {
            "git_sha": _git_sha(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "presidio_analyzer": _version("presidio-analyzer"),
            "presidio_anonymizer": _version("presidio-anonymizer"),
            "spacy": _version("spacy"),
            "en_core_web_sm": _version("en-core-web-sm"),
            "profile": profile_key,
            "scope": scope_key,
            "enabled_entity_count": len(enabled_entities),
        },
        "cases": total["cases"],
        "expected_spans": total["expected"],
        "negative_cases": total["negative"],
        "strict_exact": strict,
        "current_coverage": current,
        "roadmap_coverage": roadmap,
        "correct_category_overlap_recall": (
            correct_category_hits / total["expected"] if total["expected"] else 1.0
        ),
        "perfect_cases": perfect_cases,
        "negative_clean": negative_clean,
        "negative_clean_rate": (
            negative_clean / total["negative"] if total["negative"] else 1.0
        ),
        "expected_entities_not_enabled_by_profile": sorted(
            expected_types - set(enabled_entities)
        ),
        "by_group": group_summary,
        "by_entity": entity_summary,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("PrivacyGate English baseline benchmark")
    print(f"Cases: {total['cases']}")
    print(f"Expected spans: {total['expected']}")
    print(f"Negative/adversarial cases: {total['negative']}")
    print(f"Strict exact: {_metric_text(strict)}")
    print(f"Current coverage: {_metric_text(current)}")
    print(f"Roadmap coverage: {_metric_text(roadmap)}")
    print(
        "Correct-category overlap recall: "
        f"{summary['correct_category_overlap_recall']:.3f}"
    )
    print(f"Perfect cases: {perfect_cases}/{total['cases']}")
    print(
        f"Negative clean: {negative_clean}/{total['negative']} "
        f"({summary['negative_clean_rate']:.3f})"
    )
    print(f"CSV: {output_csv.resolve()}")
    print(f"Summary: {summary_path.resolve()}")

    print("\nBy group:")
    for name, data in group_summary.items():
        metric = _metric(int(data["tp"]), int(data["fp"]), int(data["fn"]))
        suffix = ""
        if int(data["negative_cases"]):
            suffix = (
                f" negative-clean={data['negative_clean']}/{data['negative_cases']}"
            )
        print(
            f"  {name:12s} cases={int(data['cases']):3d} "
            f"{_metric_text(metric)}{suffix}"
        )

    problems = [
        (name, data)
        for name, data in entity_summary.items()
        if int(data["fn"]) or int(data["fp"])
    ]
    if problems:
        print("\nEntities with misses or false positives:")
        for name, data in problems:
            print(
                f"  {name:32s} "
                f"{_metric_text(_metric(int(data['tp']), int(data['fp']), int(data['fn'])))}"
            )

    not_enabled = summary["expected_entities_not_enabled_by_profile"]
    if not_enabled:
        print("\nExpected roadmap entities not enabled by the selected product profile:")
        for entity_type in not_enabled:
            print(f"  - {entity_type}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen PrivacyGate English baseline through the real central "
            "PrivacyGateService. No network calls are made."
        )
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--profile", default="general_business")
    parser.add_argument("--scope", default="maximum")
    args = parser.parse_args()
    return run(
        args.corpus.resolve(),
        args.output,
        args.summary,
        profile_key=args.profile,
        scope_key=args.scope,
    )


if __name__ == "__main__":
    raise SystemExit(main())
