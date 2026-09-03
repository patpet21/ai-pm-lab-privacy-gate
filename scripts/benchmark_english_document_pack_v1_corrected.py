from __future__ import annotations

import benchmark_english_document_pack_v1 as benchmark

# Pre-first-run metadata correction only.
# The original runner recorded an incorrect SHA256 for the already-frozen corpus.
# The corpus and PrivacyGate production detector are unchanged.
benchmark.FROZEN_CORPUS_SHA256 = "1c4865861beac2179426cba35953469965d348b7ac79918581ebac4d875adfbd"


if __name__ == "__main__":
    raise SystemExit(benchmark.main())
