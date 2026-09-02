from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_CSV = Path("build/benchmarks/english_baseline_v1.csv")
DEFAULT_CORPUS = Path("benchmarks/english/v1")
DEFAULT_REPORT = Path("build/benchmarks/english_baseline_v1_diagnosis.md")

PRIORITY_ENTITIES = (
    "ORGANIZATION",
    "DATE_TIME",
    "PERSON",
    "STREET_ADDRESS",
    "POSTAL_CODE",
    "LOCATION",
    "URL",
    "US_DRIVER_LICENSE",
)

SAFE_RECALL_ENTITIES = (
    "CONTRACT_ID",
    "PURCHASE_ORDER_ID",
    "SWIFT_BIC",
    "CASE_REFERENCE",
    "TENANT_ID",
    "US_EIN",
    "US_ROUTING_NUMBER",
    "US_SSN",
)


def _load_corpus(path: Path) -> dict[str, dict[str, Any]]:
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    if not files:
        raise SystemExit(f"No corpus JSONL files found at {path}")

    cases: dict[str, dict[str, Any]] = {}
    for file_path in files:
        with file_path.open("r", encoding="utf-8") as handle:
            for line_number, raw in enumerate(handle, start=1):
                line = raw.strip()
                if not line:
                    continue
                payload = json.loads(line)
                case_id = str(payload.get("id", "")).strip()
                if not case_id:
                    raise SystemExit(f"{file_path}:{line_number}: missing id")
                if case_id in cases:
                    raise SystemExit(f"Duplicate corpus case id: {case_id}")
                cases[case_id] = payload
    return cases


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(
            f"Benchmark CSV not found: {path}\n"
            "Run scripts/benchmark_english_baseline.py first."
        )
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _items(row: dict[str, str], key: str) -> list[dict[str, Any]]:
    raw = row.get(key, "").strip()
    if not raw:
        return []
    value = json.loads(raw)
    return value if isinstance(value, list) else []


def _page(item: dict[str, Any]) -> int:
    return int(item.get("page_number", 1))


def _start(item: dict[str, Any]) -> int:
    return int(item.get("start", 0))


def _end(item: dict[str, Any]) -> int:
    return int(item.get("end", 0))


def _overlaps(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        _page(a) == _page(b)
        and max(_start(a), _start(b)) < min(_end(a), _end(b))
    )


def _text(case: dict[str, Any]) -> str:
    if isinstance(case.get("text"), str):
        return str(case["text"])
    pages = case.get("pages", [])
    if isinstance(pages, list):
        return " ⟦PAGE⟧ ".join(str(value) for value in pages)
    return ""


def _short(value: str, limit: int = 220) -> str:
    value = value.replace("\n", " ↵ ")
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _finding(item: dict[str, Any]) -> str:
    entity = str(item.get("entity_type", "?"))
    value = str(item.get("value", ""))
    score = item.get("score")
    suffix = f" score={float(score):.3f}" if score is not None else ""
    return (
        f"{entity}={value!r} "
        f"p{_page(item)}[{_start(item)}:{_end(item)}]{suffix}"
    )


def _row_detail(row: dict[str, str], case: dict[str, Any]) -> list[str]:
    expected = _items(row, "expected")
    misses = _items(row, "misses")
    extras = _items(row, "extras")
    lines = [
        f"- **{row['case_id']}** — group={row['group']}, coverage={row['coverage']}",
        f"  - Text: `{_short(_text(case))}`",
        "  - Expected: " + ("; ".join(_finding(item) for item in expected) or "NONE"),
        "  - Misses: " + ("; ".join(_finding(item) for item in misses) or "NONE"),
        "  - Extras: " + ("; ".join(_finding(item) for item in extras) or "NONE"),
    ]
    wrong = row.get("wrong_category_overlap", "").strip()
    if wrong:
        lines.append(f"  - Wrong-category overlap: {wrong}")
    return lines


def run(csv_path: Path, corpus_path: Path, report_path: Path) -> int:
    rows = _load_rows(csv_path)
    corpus = _load_corpus(corpus_path)

    if len(rows) != 300:
        raise SystemExit(f"Expected 300 benchmark rows, found {len(rows)}")

    missing_cases = [row["case_id"] for row in rows if row["case_id"] not in corpus]
    if missing_cases:
        raise SystemExit(f"CSV case ids missing from corpus: {missing_cases[:10]}")

    nonperfect = [row for row in rows if row.get("perfect", "").lower() != "true"]
    fp_entities: Counter[str] = Counter()
    fn_entities: Counter[str] = Counter()
    negative_fp_entities: Counter[str] = Counter()
    priority_cases: dict[str, set[str]] = defaultdict(set)
    recall_cases: dict[str, set[str]] = defaultdict(set)

    miss_signals = Counter()
    extra_signals = Counter()
    current_true_misses: list[tuple[str, dict[str, Any]]] = []
    roadmap_misses: list[tuple[str, dict[str, Any]]] = []
    boundary_misses: list[tuple[str, dict[str, Any]]] = []
    wrong_category_misses: list[tuple[str, dict[str, Any]]] = []
    unsolicited_extras: list[tuple[str, dict[str, Any]]] = []
    negative_rows: list[dict[str, str]] = []

    for row in rows:
        misses = _items(row, "misses")
        extras = _items(row, "extras")
        is_negative = int(row.get("expected_count", "0")) == 0

        if is_negative and extras:
            negative_rows.append(row)

        for extra in extras:
            entity = str(extra.get("entity_type", "?"))
            fp_entities[entity] += 1
            if is_negative:
                negative_fp_entities[entity] += 1
            if entity in PRIORITY_ENTITIES:
                priority_cases[entity].add(row["case_id"])

            same_type_overlap = any(
                str(miss.get("entity_type")) == entity and _overlaps(miss, extra)
                for miss in misses
            )
            different_type_overlap = any(
                str(miss.get("entity_type")) != entity and _overlaps(miss, extra)
                for miss in misses
            )
            if same_type_overlap:
                extra_signals["span-boundary-extra"] += 1
            elif different_type_overlap:
                extra_signals["wrong-category-extra"] += 1
            else:
                extra_signals["unsolicited-fp"] += 1
                unsolicited_extras.append((row["case_id"], extra))

        for miss in misses:
            entity = str(miss.get("entity_type", "?"))
            fn_entities[entity] += 1
            if entity in PRIORITY_ENTITIES:
                priority_cases[entity].add(row["case_id"])
            if entity in SAFE_RECALL_ENTITIES:
                recall_cases[entity].add(row["case_id"])

            if row.get("coverage") == "roadmap":
                miss_signals["roadmap-gap"] += 1
                roadmap_misses.append((row["case_id"], miss))
                continue

            same_type_overlap = any(
                str(extra.get("entity_type")) == entity and _overlaps(miss, extra)
                for extra in extras
            )
            different_type_overlap = any(
                str(extra.get("entity_type")) != entity and _overlaps(miss, extra)
                for extra in extras
            )
            if same_type_overlap:
                miss_signals["span-boundary"] += 1
                boundary_misses.append((row["case_id"], miss))
            elif different_type_overlap:
                miss_signals["wrong-category"] += 1
                wrong_category_misses.append((row["case_id"], miss))
            else:
                miss_signals["current-detection-miss"] += 1
                current_true_misses.append((row["case_id"], miss))

    total_fp = sum(fp_entities.values())
    total_fn = sum(fn_entities.values())

    lines: list[str] = [
        "# PrivacyGate English baseline v1 — failure diagnosis",
        "",
        "This report is diagnostic only. It does not change benchmark annotations or production behavior.",
        "",
        "## Executive summary",
        "",
        f"- Benchmark cases: {len(rows)}",
        f"- Non-perfect cases: {len(nonperfect)}",
        f"- False-positive findings: {total_fp}",
        f"- Missed expected findings: {total_fn}",
        f"- Negative cases with at least one detection: {len(negative_rows)}",
        "",
        "### Miss signals",
        "",
        f"- Current detection misses (no overlapping prediction): {miss_signals['current-detection-miss']}",
        f"- Same-entity span/boundary mismatches: {miss_signals['span-boundary']}",
        f"- Wrong-category overlaps: {miss_signals['wrong-category']}",
        f"- Deliberate roadmap gaps: {miss_signals['roadmap-gap']}",
        "",
        "### Extra-detection signals",
        "",
        f"- Unsolicited false positives: {extra_signals['unsolicited-fp']}",
        f"- Extras caused by same-entity boundary mismatch: {extra_signals['span-boundary-extra']}",
        f"- Extras overlapping a differently categorized expected span: {extra_signals['wrong-category-extra']}",
        "",
        "## False positives by entity",
        "",
        "| Entity | FP | On negative cases |",
        "| --- | ---: | ---: |",
    ]
    for entity, count in fp_entities.most_common():
        lines.append(f"| {entity} | {count} | {negative_fp_entities[entity]} |")

    lines.extend(
        [
            "",
            "## Misses by expected entity",
            "",
            "| Entity | FN |",
            "| --- | ---: |",
        ]
    )
    for entity, count in fn_entities.most_common():
        lines.append(f"| {entity} | {count} |")

    lines.extend(["", "## Negative/adversarial cases that produced detections", ""])
    if negative_rows:
        for row in negative_rows:
            lines.extend(_row_detail(row, corpus[row["case_id"]]))
    else:
        lines.append("All negative cases were clean.")

    lines.extend(["", "## Priority precision/semantic entities", ""])
    for entity in PRIORITY_ENTITIES:
        case_ids = sorted(priority_cases.get(entity, set()))
        if not case_ids:
            continue
        lines.extend([f"### {entity} ({len(case_ids)} affected cases)", ""])
        row_by_id = {row["case_id"]: row for row in rows}
        for case_id in case_ids:
            lines.extend(_row_detail(row_by_id[case_id], corpus[case_id]))
        lines.append("")

    lines.extend(["", "## High-precision / low-recall candidates", ""])
    row_by_id = {row["case_id"]: row for row in rows}
    for entity in SAFE_RECALL_ENTITIES:
        case_ids = sorted(recall_cases.get(entity, set()))
        if not case_ids:
            continue
        lines.extend([f"### {entity} — missed cases", ""])
        for case_id in case_ids:
            lines.extend(_row_detail(row_by_id[case_id], corpus[case_id]))
        lines.append("")

    lines.extend(["", "## Deliberate roadmap misses", ""])
    for case_id, miss in roadmap_misses:
        lines.append(f"- **{case_id}** — {_finding(miss)} — `{_short(_text(corpus[case_id]))}`")

    lines.extend(["", "## Current misses with no overlapping prediction", ""])
    for case_id, miss in current_true_misses:
        lines.append(f"- **{case_id}** — {_finding(miss)} — `{_short(_text(corpus[case_id]))}`")

    lines.extend(["", "## Same-entity span/boundary mismatches", ""])
    for case_id, miss in boundary_misses:
        row = row_by_id[case_id]
        lines.extend(_row_detail(row, corpus[case_id]))

    lines.extend(["", "## Wrong-category overlaps", ""])
    for case_id, miss in wrong_category_misses:
        row = row_by_id[case_id]
        lines.extend(_row_detail(row, corpus[case_id]))

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print("PrivacyGate English baseline failure diagnosis")
    print(f"Cases: {len(rows)}")
    print(f"Non-perfect cases: {len(nonperfect)}")
    print(f"FP findings: {total_fp}")
    print(f"FN findings: {total_fn}")
    print(f"Negative cases with detections: {len(negative_rows)}")
    print("Miss signals:")
    print(f"  current detection miss: {miss_signals['current-detection-miss']}")
    print(f"  span/boundary mismatch: {miss_signals['span-boundary']}")
    print(f"  wrong-category overlap: {miss_signals['wrong-category']}")
    print(f"  roadmap gap: {miss_signals['roadmap-gap']}")
    print("Extra signals:")
    print(f"  unsolicited FP: {extra_signals['unsolicited-fp']}")
    print(f"  span/boundary extra: {extra_signals['span-boundary-extra']}")
    print(f"  wrong-category extra: {extra_signals['wrong-category-extra']}")
    print("Top false-positive entities:")
    for entity, count in fp_entities.most_common(10):
        print(f"  {entity:28s} {count:3d} (negative={negative_fp_entities[entity]})")
    print("Top missed entities:")
    for entity, count in fn_entities.most_common(10):
        print(f"  {entity:28s} {count:3d}")
    print(f"Report: {report_path.resolve()}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose the frozen English baseline CSV without re-running or "
            "changing PrivacyGate detection."
        )
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return run(args.csv.resolve(), args.corpus.resolve(), args.report.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
