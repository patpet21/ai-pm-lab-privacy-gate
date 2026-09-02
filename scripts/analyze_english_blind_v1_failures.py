from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

CSV_PATH = Path("build/benchmarks/english_blind_v1.csv")


def _int(row: dict[str, str], key: str) -> int:
    try:
        return int(row.get(key, "0") or 0)
    except ValueError:
        return 0


def _pretty_json(value: str) -> str:
    if not value:
        return "[]"
    try:
        return json.dumps(json.loads(value), ensure_ascii=False)
    except Exception:
        return value


def main() -> int:
    if not CSV_PATH.exists():
        raise SystemExit(f"Missing blind CSV: {CSV_PATH}")

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    nonperfect = [row for row in rows if _int(row, "fp") or _int(row, "fn")]
    fp_entities: Counter[str] = Counter()
    fn_entities: Counter[str] = Counter()

    for row in nonperfect:
        extras = row.get("extras", "")
        misses = row.get("misses", "")
        try:
            for item in json.loads(extras or "[]"):
                fp_entities[str(item.get("entity_type", "?"))] += 1
        except Exception:
            pass
        try:
            for item in json.loads(misses or "[]"):
                fn_entities[str(item.get("entity_type", "?"))] += 1
        except Exception:
            pass

    print("PrivacyGate English blind v1 failure diagnosis")
    print(f"Cases: {len(rows)}")
    print(f"Non-perfect cases: {len(nonperfect)}")
    print(f"FP findings: {sum(_int(row, 'fp') for row in rows)}")
    print(f"FN findings: {sum(_int(row, 'fn') for row in rows)}")
    print()

    if fp_entities:
        print("Top false-positive entities:")
        for entity, count in fp_entities.most_common():
            print(f"  {entity:<32} {count}")
        print()
    if fn_entities:
        print("Top missed entities:")
        for entity, count in fn_entities.most_common():
            print(f"  {entity:<32} {count}")
        print()

    print("Case-level details:")
    for row in nonperfect:
        case_id = row.get("case_id") or row.get("id") or "?"
        group = row.get("group", "?")
        text = row.get("text") or row.get("input") or row.get("source_text") or ""
        print(f"\n[{case_id}] group={group} fp={_int(row, 'fp')} fn={_int(row, 'fn')}")
        if text:
            print(f"TEXT: {text}")
        if row.get("expected"):
            print(f"EXPECTED: {_pretty_json(row['expected'])}")
        if row.get("predictions"):
            print(f"PREDICTED: {_pretty_json(row['predictions'])}")
        if row.get("extras"):
            print(f"EXTRAS: {_pretty_json(row['extras'])}")
        if row.get("misses"):
            print(f"MISSES: {_pretty_json(row['misses'])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
