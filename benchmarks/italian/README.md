# Italian PII benchmark workspace

This directory is for development-only evaluation of the PrivacyGate Italian Privacy Pack.

## Rules

- Do not bundle benchmark datasets in the PrivacyGate installer.
- Do not commit third-party datasets unless their license and redistribution terms have been reviewed.
- Rizzo/Ai4Privacy-derived material is an external benchmark input, not a runtime dependency.
- Store generated metrics/results here only when they contain no original sensitive document content.

## Current NLP baseline

PrivacyGate uses `xx_ent_wiki_sm` 3.8.0 as the distributable Italian NER baseline for `PERSON`, `ORGANIZATION` and `LOCATION`. It is a small multilingual spaCy model with MIT model licensing. The official `it_core_news_sm` 3.8.0 model is not bundled because its published license is CC BY-NC-SA 3.0.

## Planned workflow

1. Download an approved Italian validation set on the development machine.
2. Map source labels to PrivacyGate entities (for example `CF -> IT_FISCAL_CODE`, `PIVA -> IT_VAT_NUMBER`, `IBAN -> IBAN_CODE`).
3. Run the local detector with `language="it"`.
4. Measure precision, recall and F1 by entity category, including the NER baseline for person, organization and location.
5. Improve deterministic/context recognizers first; only evaluate a heavier optional NLP model if measured recall requires it and licensing is compatible with distribution.

No benchmark data is required for normal PrivacyGate runtime.
