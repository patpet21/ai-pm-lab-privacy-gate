# English baseline benchmark

This directory contains the development-only English baseline for PrivacyGate.

The goal is to measure the current central English detector before tuning it. The benchmark is intentionally separate from production recognizers and is not bundled with the PrivacyGate installer.

## Baseline v1

`benchmarks/english/v1/` contains **300 frozen synthetic cases** split into JSONL shards for reviewability:

| Group | Cases |
| --- | ---: |
| identity / semantic / contact / address | 55 |
| government identifiers / DOB | 30 |
| financial / banking / payment | 45 |
| business / legal / operational identifiers | 35 |
| real estate / property / construction | 45 |
| credentials / secrets / technical | 15 |
| negative / adversarial | 75 |
| **Total** | **300** |

The corpus contains **227 expected sensitive spans**. Seventy-five cases contain no expected sensitive span and exist specifically to measure false positives.

Most cases are marked `coverage: "current"`. Thirteen cases are deliberately marked `coverage: "roadmap"` for capabilities PrivacyGate does not currently expose, including IBAN and universal-secret/native-entity candidates. These cases are supposed to show misses in the first baseline; they must not be removed merely to improve the score.

## Ground truth

Each JSONL row stores a stable case ID, group, document genre, source kind, current-vs-roadmap coverage, formatting/adversarial tags, either one `text` string or explicit `pages`, and every expected final finding with `entity_type`, `value`, `page_number`, exact `start` and exact `end`.

The runner validates the annotations before analysis starts. A correct entity with the wrong boundary is not an exact hit. A finding with the right characters but the wrong category is also not an exact hit.

## What is measured

The benchmark runs through the real `PrivacyGateService`, not an isolated regex or a standalone Presidio analyzer. The score therefore includes the same English guardrails, overlap resolution, propagation and document-level recovery used by the product.

The runner reports strict exact precision/recall/F1, current-coverage metrics, roadmap-gap metrics, correct-category overlap recall, perfect-case count, negative/adversarial clean rate, per-group and per-entity metrics, misses/extras/wrong-category overlaps, and runtime metadata including Git SHA, Python, Presidio, spaCy and `en_core_web_sm` versions.

Per-case details are written to CSV and aggregate metrics to JSON.

## Run locally

From the repository root:

```powershell
$env:PYTHONPATH = "$PWD\src"
python scripts\benchmark_english_baseline.py
```

Default outputs:

```text
build/benchmarks/english_baseline_v1.csv
build/benchmarks/english_baseline_v1_summary.json
```

No network calls are required.

## Anti-overfitting rules

This is the pre-tuning baseline. After the first measured run:

1. Do not delete a case because PrivacyGate misses it.
2. Do not rewrite a negative case because PrivacyGate produces a false positive.
3. Do not weaken an exact span to make a partial match pass.
4. Correct an annotation only when the ground truth itself is wrong, and document the reason in the commit.
5. New tuned examples belong in a later corpus version rather than silently changing v1.
6. A separate blind English corpus must be created after tuning and must not reuse these sentences or values.
7. Third-party datasets must not be committed until license and redistribution terms have been reviewed.
8. Never store real customer or personal data in benchmark fixtures.

## Scope of this phase

This baseline evaluates detector behavior on synthetic text and extracted-text shapes, including punctuation, line wraps and an Office-style segmented case. It does not replace later end-to-end validation of real PDF, DOCX, XLSX, PPTX, image/OCR and browser-extension flows. Those surfaces should be tested only after the central English detector has been tuned against this frozen baseline and then validated on a blind corpus.
