# Pre-first-run corpus hash correction

The first attempted execution of `scripts/benchmark_english_document_pack_v1.py` stopped before detector analysis because the runner contained an incorrect frozen corpus SHA256 value.

- Incorrect metadata SHA256: `be98c2326c8e5abbc9a987e9e10a9c2a7dc2b6a8b0f905fbbad25d4aab4862df`
- Actual frozen corpus SHA256 from the clean Windows worktree: `1c4865861beac2179426cba35953469965d348b7ac79918581ebac4d875adfbd`
- Corpus content: unchanged
- PrivacyGate production detector: unchanged
- Benchmark predictions/results produced before correction: none

For the auditable first untouched run, use `scripts/benchmark_english_document_pack_v1_corrected.py`. It imports the frozen runner, replaces only the incorrect SHA metadata constant, and then executes the same benchmark logic.
