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
| Deterministic tools, claim-level recall on a held-out dataset | 150 of 150 true claims found (duplicates, unbundling, excess units, date anomalies); 0 of 150 decoys and 0 of 159,940 clean claim-checks raised | 150 positives, 40,060 claims | `tools.score` on seed 20261020, generated after the code was frozen at `c79a9b3`; shares rule definitions with the generator, so it checks implementation, not realism (KF-018) | 2026-10-19, `c79a9b3` |
| Provider-intensity check on the same held-out dataset | recall 26 of 30 (86.7%), precision 100%, 0 of 30 decoys raised; dev run 28 of 30 | 30 positives, 195 scored providers | same scorecard; misses explained by 40% peer contamination (KF-017); one tuning round tried and rejected | 2026-10-19, `c79a9b3` |
| API request latency, default dataset (40,060 claims), loopback, one request at a time | `GET /claims/{id}/dossier` p50 2.7 ms, p95 3.2 ms, max 3.9 ms; `GET /claims/{id}` p50 1.8 ms, p95 2.3 ms; `GET /providers/{id}/intensity` p50 1.7 ms, p95 2.1 ms | 200 requests per endpoint after 10 warm-up | `python -m claims_copilot.api.bench`: real uvicorn server on 127.0.0.1, keep-alive httpx client, sequential; macOS 13.6.7 arm64, Python 3.12.13. Service time on one laptop, not capacity under load | 2026-10-19, `d02b8d7` |
| API checked on the full flagged queue | All 618 flags paged by cursor with no gap or repeat; all 618 flagged-claim dossiers and all 400 provider intensity results contained 0 verdict-word matches | 618 claims, 400 providers | one-off script over the default dataset using the same word list as `tests/tool_fixtures.py` (not a stored artifact) | 2026-10-19, `d02b8d7` |
| Tests | 298 passing (209 before Phase 4; 86 API tests, 3 tool tests) | 298 | `uv run pytest` | 2026-10-19, `d02b8d7` |
| Tests (after Phase 3) | 209 passing | 209 | `uv run pytest` | 2026-10-19, `c79a9b3` |
| Phase 3 spend | $0.00 | n/a | `uv run python -m claims_copilot.budget` | 2026-10-19 |
| Tests (after Phase 5) | 429 passing (131 agent tests; no network, no spend) | 429 | `uv run pytest` | 2026-10-20, Phase 5 final commit |
| Agent smoke run, claim investigations shown after validation (smoke test, not an eval; shown means it passed the validator, not that it is correct) | Final run: OpenAI 10 of 10, Anthropic 10 of 10. Earlier runs on earlier code: 7 and 0, then 8 and 9 | 10 flagged claims per provider, seed 5, one sample | `uv run python -m claims_copilot.agent.smoke --confirm --run-id p5-smoke-20261020-r3` | 2026-10-20, Phase 5 final commit; models `gpt-6-luna`, `claude-haiku-5-5`; prompt `agent_v1` |
| Agent cost per investigation | OpenAI mean $0.0013, Anthropic mean $0.0022 (2 to 3 model turns, 1 to 2 tool calls) | 12 investigations each | same run, ledger | 2026-10-20, `133e3d4` |
| Phase 5 spend | $0.1294 against an $8.00 cap; total $0.1460 of $50 | n/a | `uv run python -m claims_copilot.budget` | 2026-10-20 |
| Retrieval R@1 and R@10, hybrid + LLM rerank vs the Phase 0 baselines, development set | V3: R@1 0.82, R@10 0.90, MRR@10 0.856. BM25: 0.33, 0.80, 0.455. Dense: 0.38, 0.82, 0.513 | 40 questions (assistant-drafted, KF-006) | `uv run python -m claims_copilot.retrieval.phase6 --rerank`; variants and settings fixed before the run | 2026-10-20, `0f203f2`; reranker `gpt-6-luna`, prompt `rerank_v1` |
| Same, on held-out paraphrase questions written before any method ran | V3: R@1 0.81, R@10 0.81. BM25: 0.25, 0.44. Dense: 0.38, 0.69 | 16 questions (one = 6.25 points) | `phase6 --gold heldout --rerank`, run once | 2026-10-20, `0f203f2` |
| Retrieval upgrades that did not help | Contextual embeddings: V6 (0.78 R@1, 0.88 R@10) below V3. Hybrid alone: R@10 0.80, no gain over BM25 | 40 questions | same runs | 2026-10-20, `0f203f2` |
| Reranker cost and latency | about $0.001 and about 3.5 s per uncached search (107 calls, $0.1071) | 107 calls | `budget/ledger.jsonl`; call time from the run output | 2026-10-20, `0f203f2` |
| Phase 6 spend | $0.4693 of the $2.00 live ceiling ($8 cap); total $0.6383 of $50 | n/a | `uv run python -m claims_copilot.budget` | 2026-10-20 |
| Tests (after Phase 6 build) | 470 passing | 470 | `uv run pytest` | 2026-10-20, `0f203f2` |
