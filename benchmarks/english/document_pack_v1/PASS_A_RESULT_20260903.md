# English realistic document pack v1 — Pass A result

Date: 2026-09-03

Production commit:

`cf498104ac0d1d0bea5b0597d240a09e95747b4d`

Checkpoint:

`checkpoint/freev1-english-document-pack-v1-pass-a-20260903`

## Validation status

The English Document Pack Pass A structural precision work was validated locally on Windows. GitHub Actions were not used.

Targeted and regression pytest sets were green before the production commit.

## Historical regression benchmarks

### English baseline

- Cases: 300
- Expected spans: 227
- Negative/adversarial cases: 75
- Strict exact: P=0.983 R=0.996 F1=0.989 (TP=226 FP=4 FN=1)
- Current coverage: P=0.982 R=0.995 F1=0.988 (TP=213 FP=4 FN=1)
- Roadmap coverage: P=1.000 R=1.000 F1=1.000 (TP=13 FP=0 FN=0)
- Correct-category overlap recall: 0.996
- Perfect cases: 296/300
- Negative clean: 75/75 (1.000)

The pre-Document-Pack baseline had P=0.978 R=0.996 F1=0.987 (TP=226 FP=5 FN=1), so Pass A preserved recall and reduced false positives by one.

### English blind validation v1

- Cases: 100
- Expected spans: 83
- Negative/adversarial cases: 30
- Strict exact: P=1.000 R=1.000 F1=1.000 (TP=83 FP=0 FN=0)
- Correct-category overlap recall: 1.000
- Perfect cases: 100/100
- Negative clean: 30/30 (1.000)

### English blind validation v2

- Cases: 180
- Expected spans: 171
- Negative/adversarial cases: 45
- Strict exact: P=0.957 R=0.912 F1=0.934 (TP=156 FP=7 FN=15)
- Correct-category overlap recall: 0.912
- Perfect cases: 166/180
- Negative clean: 45/45 (1.000)

This exactly restores the pre-Document-Pack-Pass-A Blind v2 benchmark level.

## Realistic Document Pack v1

Frozen detector SHA before document-pack tuning:

`18d95fe1ae3d16cc6a11175b0ec691eb8106fe0d`

Frozen corpus SHA256:

`1c4865861beac2179426cba35953469965d348b7ac79918581ebac4d875adfbd`

### Untouched first run

- Documents: 40
- Expected spans: 246
- Negative documents: 5
- Strict exact: P=0.830 R=0.915 F1=0.870 (TP=225 FP=46 FN=21)
- Correct-category overlap recall: 0.943
- Perfect documents: 15/40
- Negative clean: 1/5 (0.200)

### After Pass A

- Documents: 40
- Expected spans: 246
- Negative documents: 5
- Strict exact: P=0.963 R=0.959 F1=0.961 (TP=236 FP=9 FN=10)
- Correct-category overlap recall: 0.959
- Perfect documents: 30/40
- Negative clean: 4/5 (0.800)

### Improvement

- Precision: 0.830 -> 0.963
- Recall: 0.915 -> 0.959
- F1: 0.870 -> 0.961
- TP: 225 -> 236
- FP: 46 -> 9
- FN: 21 -> 10
- Perfect documents: 15/40 -> 30/40
- Negative clean: 1/5 -> 4/5

## Scope of Pass A

Pass A remained structural and precision-first. It addressed generalized multiline and document-structure behavior, including:

- context separators crossing document field boundaries;
- malformed statistical NER spans spanning into the next field;
- document-heading and field-label NER noise;
- explicit business-role PERSON recovery;
- schema/document words accepted as identifier values;
- purchase-order `PO` matching the prefix of `POL-...` policy IDs;
- ordinary prose incorrectly accepted as vehicle-license-plate values;
- preservation of intentional single-line-break label/value layouts;
- regression refinements for multiline passport, unit number and COI reference layouts;
- limiting field-label suppression so later colons in narrative lines do not suppress valid organizations.

## Deferred residuals

No further tuning was included in Pass A for:

- money/category recall aliases such as committed cost, contingency, seller net proceeds and some invoice amounts;
- address `Suite` boundary handling;
- housing case category arbitration;
- generic location suppression such as `New York State`;
- benchmark annotation changes for plausible privacy-protective detections such as unit numbers omitted from the frozen expected set.

These remain candidates for a later evidence-driven Pass B rather than being tuned into the frozen Document Pack v1.
