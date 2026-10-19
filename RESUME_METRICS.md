# Resume metrics

Only measured numbers belong here, each with how it was measured and the commit. Nothing is
projected or rounded up. Small samples are flagged. Add rows as phases complete.

| Metric | Value | n | How measured | Date / commit |
|---|---|---|---|---|
| Verified public sources in the corpus | 23 documents (26 fetched sources including 3 terms pages) | 26 | `SOURCES/manifest.jsonl` rows fetched by `sources.fetch` with sha256 | 2026-10-15, `59ca693` |
| Text chunks indexed | 1,913 | 1,913 | `ingest.chunk` over the 23 documents | 2026-10-15 |
| CPT descriptors redacted at ingest | 131 (logged by hash) | 131 | `SOURCES/redactions.jsonl` line count | 2026-10-15 |
| BM25 recall@10, all questions | 0.80 | 40 | `retrieval.dense --confirm` evaluation on `eval/phase0_retrieval_gold.jsonl` | 2026-10-16 |
| Dense recall@10, all questions | 0.82 | 40 | same run, `text-embedding-3-small` | 2026-10-16 |
| Dense recall@10, paraphrase questions | 0.62 (BM25 0.25) | 8 | same run; one question moves the rate by 0.125 | 2026-10-16 |
| Dense MRR@10, all questions | 0.513 (BM25 0.455) | 40 | same run | 2026-10-16 |
| Cost to embed the corpus and 40 queries | $0.0166 | 1,953 texts | `budget/ledger.jsonl` via `uv run python -m claims_copilot.budget` | 2026-10-16 |
| Synthetic claims generated (default seed 20261019) | 40,060 claims, 64,098 lines, 4,000 members, 400 providers | 40,060 | `uv run python -m claims_copilot.synth`; counts in `eval/synthetic_dataset.json` | 2026-10-19, `b22a9b4` |
| Labelled cases (5 anomaly types x 30 anomalies and 30 decoys) | 300 | 300 | `anomaly_truth` row count in `truth.sqlite` | 2026-10-19, `b22a9b4` |
| Seeded anomalies recovered by an independent reference checker | 150 of 150, 0 decoys flagged (checker rule adjusted after first run, KF-014) | 150 | `tests/test_synth_full.py` | 2026-10-19, `b22a9b4` |
| Reproducibility | identical hashes and byte-identical SQLite across 2 processes | 2 runs | `shasum` of `payer.sqlite` and `truth.sqlite`, plus the golden-summary test | 2026-10-19, `b22a9b4` |
| Tests | 149 passing | 149 | `uv run pytest` | 2026-10-19, `b22a9b4` |
| Phase 2 spend | $0.00 | n/a | `uv run python -m claims_copilot.budget` | 2026-10-19 |
