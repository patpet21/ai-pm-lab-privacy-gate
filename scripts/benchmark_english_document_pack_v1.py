from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile

FROZEN_DETECTOR_SHA = "18d95fe1ae3d16cc6a11175b0ec691eb8106fe0d"
FROZEN_CORPUS_SHA256 = "be98c2326c8e5abbc9a987e9e10a9c2a7dc2b6a8b0f905fbbad25d4aab4862df"
EXPECTED_DOCUMENTS = 40
EXPECTED_SPANS = 246
EXPECTED_NEGATIVES = 5
RELAXED_OVERLAP = 0.80

CORPUS = Path("benchmarks/english/document_pack_v1/english_document_pack_v1.jsonl")
OUT_CSV = Path("build/benchmarks/english_document_pack_v1.csv")
OUT_JSON = Path("build/benchmarks/english_document_pack_v1_summary.json")


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _maximum_profile():
    base = get_profile("general_business")
    return replace(base, entities=entities_for_scope(base, "maximum"))


def _load_corpus(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != FROZEN_CORPUS_SHA256:
        raise SystemExit(
            "Frozen corpus SHA mismatch: "
            f"expected {FROZEN_CORPUS_SHA256}, got {digest}. "
            "Do not edit the corpus after the first run."
        )

    docs: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise SystemExit(f"{path}:{line_number}: document must be an object")
            docs.append(item)

    if len(docs) != EXPECTED_DOCUMENTS:
        raise SystemExit(f"Expected {EXPECTED_DOCUMENTS} documents, found {len(docs)}")
    ids = [str(doc.get("id", "")) for doc in docs]
    if len(set(ids)) != len(ids) or any(not item for item in ids):
        raise SystemExit("Document ids must be non-empty and unique")

    total_spans = 0
    negatives = 0
    for doc in docs:
        text = str(doc.get("text", ""))
        expected = doc.get("expected", [])
        if not isinstance(expected, list):
            raise SystemExit(f"{doc['id']}: expected must be a list")
        if not expected:
            negatives += 1
        total_spans += len(expected)
        for item in expected:
            entity = str(item.get("entity_type", "")).strip()
            value = str(item.get("value", ""))
            if not entity or not value:
                raise SystemExit(f"{doc['id']}: invalid expected item {item!r}")
            count = text.count(value)
            if count != 1:
                raise SystemExit(
                    f"{doc['id']}: expected value {value!r} occurs {count} times; "
                    "frozen exact-span documents require one occurrence"
                )

    if total_spans != EXPECTED_SPANS:
        raise SystemExit(f"Expected {EXPECTED_SPANS} spans, found {total_spans}")
    if negatives != EXPECTED_NEGATIVES:
        raise SystemExit(f"Expected {EXPECTED_NEGATIVES} negative documents, found {negatives}")
    return docs


def _expected_items(doc: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(doc["text"])
    items: list[dict[str, Any]] = []
    for item in doc["expected"]:
        value = str(item["value"])
        start = text.index(value)
        items.append(
            {
                "entity_type": str(item["entity_type"]),
                "value": value,
                "start": start,
                "end": start + len(value),
            }
        )
    return items


def _predicted_items(findings) -> list[dict[str, Any]]:  # noqa: ANN001
    return [
        {
            "entity_type": str(item.entity_type),
            "value": str(item.text),
            "start": int(item.start),
            "end": int(item.end),
            "score": float(item.score),
        }
        for item in findings
    ]


def _key(item: dict[str, Any]) -> tuple[str, int, int]:
    return str(item["entity_type"]), int(item["start"]), int(item["end"])


def _overlap_ratio(expected: dict[str, Any], predicted: dict[str, Any]) -> float:
    if expected["entity_type"] != predicted["entity_type"]:
        return 0.0
    left = max(int(expected["start"]), int(predicted["start"]))
    right = min(int(expected["end"]), int(predicted["end"]))
    overlap = max(0, right - left)
    length = max(1, int(expected["end"]) - int(expected["start"]))
    return overlap / length


def _metrics(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _display(item: dict[str, Any]) -> str:
    score = item.get("score")
    score_text = f" score={score:.3f}" if isinstance(score, (int, float)) else ""
    return (
        f"{item['entity_type']}={item['value']!r} "
        f"[{item['start']}:{item['end']}]{score_text}"
    )


def run(details: bool = False) -> int:
    docs = _load_corpus(CORPUS)
    service = PrivacyGateService()
    profile = _maximum_profile()

    rows: list[dict[str, Any]] = []
    overlap_hits = 0
    perfect_docs = 0
    negative_clean = 0
    group_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"docs": 0, "tp": 0, "fp": 0, "fn": 0, "negatives": 0, "negative_clean": 0}
    )
    entity_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for doc in docs:
        text = str(doc["text"])
        expected = _expected_items(doc)
        findings = service.analyze(
            service.document_from_text(text),
            profile,
            language="en",
        )
        predicted = _predicted_items(findings)

        expected_by_key = {_key(item): item for item in expected}
        predicted_by_key = {_key(item): item for item in predicted}
        matched_keys = set(expected_by_key) & set(predicted_by_key)

        misses = [item for key, item in expected_by_key.items() if key not in matched_keys]
        extras = [item for key, item in predicted_by_key.items() if key not in matched_keys]
        tp, fp, fn = len(matched_keys), len(extras), len(misses)
        precision, recall, f1 = _metrics(tp, fp, fn)
        perfect = fp == 0 and fn == 0
        if perfect:
            perfect_docs += 1

        is_negative = not expected
        if is_negative and not predicted:
            negative_clean += 1

        for exp in expected:
            if any(_overlap_ratio(exp, pred) >= RELAXED_OVERLAP for pred in predicted):
                overlap_hits += 1

        group = str(doc["group"])
        g = group_counts[group]
        g["docs"] += 1
        g["tp"] += tp
        g["fp"] += fp
        g["fn"] += fn
        if is_negative:
            g["negatives"] += 1
            g["negative_clean"] += int(not predicted)

        for key in matched_keys:
            entity_counts[key[0]]["tp"] += 1
        for item in misses:
            entity_counts[item["entity_type"]]["fn"] += 1
        for item in extras:
            entity_counts[item["entity_type"]]["fp"] += 1

        rows.append(
            {
                "case_id": doc["id"],
                "group": group,
                "title": doc["title"],
                "expected_count": len(expected),
                "predicted_count": len(predicted),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "perfect": perfect,
                "expected": expected,
                "predicted": predicted,
                "misses": misses,
                "extras": extras,
                "text": text,
            }
        )

    total_tp = sum(int(row["tp"]) for row in rows)
    total_fp = sum(int(row["fp"]) for row in rows)
    total_fn = sum(int(row["fn"]) for row in rows)
    precision, recall, f1 = _metrics(total_tp, total_fp, total_fn)
    overlap_recall = overlap_hits / EXPECTED_SPANS if EXPECTED_SPANS else 1.0

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "case_id", "group", "title", "expected_count", "predicted_count",
            "tp", "fp", "fn", "precision", "recall", "f1", "perfect",
            "expected", "predicted", "misses", "extras",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = {key: row[key] for key in fieldnames}
            for key in ("expected", "predicted", "misses", "extras"):
                payload[key] = json.dumps(payload[key], ensure_ascii=False)
            writer.writerow(payload)

    group_summary: dict[str, Any] = {}
    for group, counts in sorted(group_counts.items()):
        gp, gr, gf = _metrics(counts["tp"], counts["fp"], counts["fn"])
        group_summary[group] = {**counts, "precision": gp, "recall": gr, "f1": gf}

    entity_summary: dict[str, Any] = {}
    for entity, counts in sorted(entity_counts.items()):
        ep, er, ef = _metrics(counts["tp"], counts["fp"], counts["fn"])
        entity_summary[entity] = {**counts, "precision": ep, "recall": er, "f1": ef}

    summary = {
        "frozen_detector_sha": FROZEN_DETECTOR_SHA,
        "frozen_corpus_sha256": FROZEN_CORPUS_SHA256,
        "run_git_sha": _git_sha(),
        "documents": EXPECTED_DOCUMENTS,
        "expected_spans": EXPECTED_SPANS,
        "negative_documents": EXPECTED_NEGATIVES,
        "strict_exact": {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": total_tp,
            "fp": total_fp,
            "fn": total_fn,
        },
        "correct_category_overlap_recall": overlap_recall,
        "perfect_documents": perfect_docs,
        "negative_clean": negative_clean,
        "groups": group_summary,
        "entities": entity_summary,
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("PrivacyGate English realistic document pack v1")
    print(f"Frozen detector SHA: {FROZEN_DETECTOR_SHA}")
    print(f"Frozen corpus SHA256: {FROZEN_CORPUS_SHA256}")
    print(f"Run git SHA: {summary['run_git_sha']}")
    print(f"Documents: {EXPECTED_DOCUMENTS}")
    print(f"Expected spans: {EXPECTED_SPANS}")
    print(f"Negative documents: {EXPECTED_NEGATIVES}")
    print(
        f"Strict exact: P={precision:.3f} R={recall:.3f} F1={f1:.3f} "
        f"(TP={total_tp} FP={total_fp} FN={total_fn})"
    )
    print(f"Correct-category overlap recall: {overlap_recall:.3f}")
    print(f"Perfect documents: {perfect_docs}/{EXPECTED_DOCUMENTS}")
    print(f"Negative clean: {negative_clean}/{EXPECTED_NEGATIVES} ({negative_clean / EXPECTED_NEGATIVES:.3f})")
    print(f"CSV: {OUT_CSV}")
    print(f"Summary: {OUT_JSON}")
    print("\nBy group:")
    for group, counts in group_summary.items():
        extra = ""
        if counts["negatives"]:
            extra = f" negative-clean={counts['negative_clean']}/{counts['negatives']}"
        print(
            f"  {group:20s} docs={counts['docs']:2d} "
            f"P={counts['precision']:.3f} R={counts['recall']:.3f} F1={counts['f1']:.3f} "
            f"(TP={counts['tp']} FP={counts['fp']} FN={counts['fn']}){extra}"
        )

    affected = {
        entity: counts
        for entity, counts in entity_summary.items()
        if counts["fp"] or counts["fn"]
    }
    print("\nEntities with misses or false positives:")
    if not affected:
        print("  None.")
    else:
        for entity, counts in affected.items():
            print(
                f"  {entity:34s} "
                f"P={counts['precision']:.3f} R={counts['recall']:.3f} F1={counts['f1']:.3f} "
                f"(TP={counts['tp']} FP={counts['fp']} FN={counts['fn']})"
            )

    if details:
        print("\nNon-perfect documents:")
        for row in rows:
            if row["perfect"]:
                continue
            print(f"\n[{row['case_id']}] {row['group']} — {row['title']}")
            print(row["text"].rstrip())
            print("Expected:")
            for item in row["expected"]:
                print("  ", _display(item))
            print("Misses:")
            if row["misses"]:
                for item in row["misses"]:
                    print("  ", _display(item))
            else:
                print("   NONE")
            print("Extras:")
            if row["extras"]:
                for item in row["extras"]:
                    print("  ", _display(item))
            else:
                print("   NONE")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the frozen English realistic synthetic document pack v1."
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Print every non-perfect document with expected, misses and extras.",
    )
    args = parser.parse_args()
    return run(details=args.details)


if __name__ == "__main__":
    raise SystemExit(main())
