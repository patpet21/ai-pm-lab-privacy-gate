# English realistic synthetic document pack v1

This pack is the second validation stage for PrivacyGate English Standard after the frozen Blind v2 Pass A.

## Purpose

- Measure generalization on document-shaped English inputs instead of isolated benchmark sentences.
- Keep the detector untouched while the corpus is created and frozen.
- Preserve an auditable first-run result before any additional tuning.
- Use only fictional/synthetic data.

## Frozen baseline

- Detector SHA before corpus creation: `18d95fe1ae3d16cc6a11175b0ec691eb8106fe0d`
- Corpus SHA256: `be98c2326c8e5abbc9a987e9e10a9c2a7dc2b6a8b0f905fbbad25d4aab4862df`
- Documents: 40
- Expected sensitive spans: 246
- Fully negative documents: 5

## Composition

The 40 documents are multi-line synthetic business artifacts, not one-line probes:

- 6 leasing / tenant documents
- 6 closing / finance documents
- 6 maintenance / vendor documents
- 5 project / renovation documents
- 4 insurance / legal documents
- 4 HR / operations documents
- 4 security / configuration documents
- 5 fully negative business documents

Positive documents intentionally mix several sensitive values with ordinary business language. Negative documents contain realistic labels, policy wording, placeholders, scheduling language, and schema/process terminology without live sensitive values.

## Run

```powershell
$env:PYTHONPATH = "$PWD\src"
& "C:\Users\pietr\Projects\PrivacyGate-UI-Redesign\.venv\Scripts\python.exe" scripts\benchmark_english_document_pack_v1.py
```

For diagnostics after the first untouched run:

```powershell
& "C:\Users\pietr\Projects\PrivacyGate-UI-Redesign\.venv\Scripts\python.exe" scripts\benchmark_english_document_pack_v1.py --details
```

Outputs:

- `build/benchmarks/english_document_pack_v1.csv`
- `build/benchmarks/english_document_pack_v1_summary.json`

Do not alter corpus annotations based on detector output. If an annotation is later proven objectively wrong, document the correction separately and preserve the original first-run evidence.
