# English realistic document pack v1 — Pass A plan

Frozen first-run evidence remains unchanged:

- Detector before document-pack tuning: `18d95fe1ae3d16cc6a11175b0ec691eb8106fe0d`
- Official first-run repository state: `b10b89f11cfa995b32b3067d94fafc4a4b6f7e57`
- Corpus SHA256: `1c4865861beac2179426cba35953469965d348b7ac79918581ebac4d875adfbd`
- Strict exact: P=0.830 R=0.915 F1=0.870 (TP=225 FP=46 FN=21)
- Correct-category overlap recall: 0.943
- Perfect documents: 15/40
- Negative clean: 1/5

Pass A is intentionally structural and precision-first. It targets repeated/generalizable root causes only:

1. Context separators must not cross document lines and consume the next field label.
2. Statistical NER spans must not swallow a following structured field label across a newline.
3. Common uppercase document headings and recognized field-label fragments must not become PERSON/ORG/LOCATION values.
4. Explicit person-oriented business labels should recover the exact person value after multiline NER suppression.
5. Generic schema/document words must not be accepted as structured identifier values.
6. The PO label recognizer must not match the `PO` prefix inside `POL-...` insurance policy identifiers.
7. Prose words should not be accepted as vehicle-license-plate values; uppercase alphabetic plates remain allowed.

Not in Pass A:

- new money/amount recall aliases,
- address boundary changes,
- generic location suppression such as `New York State`,
- benchmark annotation changes,
- entity-category policy changes such as generic CASE_REFERENCE vs HOUSING_LEGAL_CASE_ID,
- tuning against plausible protective detections such as unit numbers that were omitted from the frozen expected set.

Production changes are applied locally first through `scripts/apply_english_document_pack_pass_a.py` and must be validated against the targeted regression tests plus the frozen historical benchmark sets before any production commit.
