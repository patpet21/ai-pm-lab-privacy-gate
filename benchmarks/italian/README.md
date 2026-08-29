# Italian PII benchmark workspace

This directory is for development-only evaluation of the PrivacyGate Italian Privacy Pack.

## Rules

- Do not bundle benchmark datasets in the PrivacyGate installer.
- Do not commit third-party datasets unless their license and redistribution terms have been reviewed.
- Rizzo/Ai4Privacy-derived material is an external benchmark input, not a runtime dependency.
- Store generated metrics/results here only when they contain no original sensitive document content.

## Planned workflow

1. Download an approved Italian validation set on the development machine.
2. Map source labels to PrivacyGate entities (for example `CF -> IT_FISCAL_CODE`, `PIVA -> IT_VAT_NUMBER`, `IBAN -> IBAN_CODE`).
3. Run the local detector with `language="it"`.
4. Measure precision, recall and F1 by entity category.
5. Improve deterministic/context recognizers first; only evaluate a heavier optional NLP model if measured recall requires it.

No benchmark data is required for normal PrivacyGate runtime.
