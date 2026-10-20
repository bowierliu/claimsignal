# Evaluation

Measured results only. Failures are listed in `KNOWN_FAILURES.md`; headline numbers with how they
were measured are in `RESUME_METRICS.md`.

## Method (Phase 0 retrieval)

- Gold set: `eval/phase0_retrieval_gold.jsonl`, 40 questions (32 direct, 8 paraphrase). Each item
  names a source document and a verbatim evidence quote.
- A retrieved chunk is a hit only if it comes from the named source AND its text contains the
  quote (whitespace and quote-normalised). Defining gold by quote, not chunk id, keeps results
  valid when chunking changes. All 40 quotes resolve to a chunk (test:
  `test_every_gold_quote_exists_in_the_chunked_corpus`).
- Metrics: recall@1/5/10 and MRR@10, overall and per group.
- The gold set was drafted by the assistant and accepted by the owner as provisional on
  2026-10-16 (see `KNOWN_FAILURES.md`, KF-006).
- Reproduce: `uv run python -m claims_copilot.retrieval.dense --confirm` (about $0.017 from a
  cold cache; the dry run without `--confirm` estimates the cost first).

## Phase 0 results (2026-10-16)

| Method | Group | n | R@1 | R@5 | R@10 | MRR@10 |
|---|---|---|---|---|---|---|
| BM25 | all | 40 | 0.33 | 0.62 | 0.80 | 0.455 |
| BM25 | direct | 32 | 0.41 | 0.75 | 0.94 | 0.555 |
| BM25 | paraphrase | 8 | 0.00 | 0.12 | 0.25 | 0.057 |
| Dense (`text-embedding-3-small`) | all | 40 | 0.38 | 0.72 | 0.82 | 0.513 |
| Dense | direct | 32 | 0.44 | 0.81 | 0.88 | 0.588 |
| Dense | paraphrase | 8 | 0.12 | 0.38 | 0.62 | 0.213 |

Overlap at rank 10: both methods miss 4 questions; BM25 finds 3 that dense misses; dense finds 4
that BM25 misses. The union of the two top-10 lists would find 36 of 40 (0.90). That is an upper
bound for hybrid retrieval, not a measured result. With n=8, one paraphrase question moves a rate
by 0.125.

## Phase 2 checks (synthetic data, 2026-10-19)

These are consistency checks on the generated data, not detector accuracy. Run: `uv run pytest`.

| Check | Result |
|---|---|
| Baseline (before injection) has no anomaly of any type, per the independent checker | 0 findings |
| Seeded anomalies recovered by the independent checker, default scale | 150 of 150 (30 per type), no decoy or clean claim flagged (exact set equality) |
| Decoys per type | 30 each, none flagged by the checker |
| Same seed, two processes | identical payer and truth hashes and byte-identical SQLite files |
| Tools' database contains no truth tables or columns | checked by a test |

Caveats: the checker was written by the same author as the generator (KF-011), and its outlier
rule was changed from 3x to 2x the peer median after the first full-scale run missed 2 of 30
labelled outliers (KF-014). The 150 of 150 result is on the adjusted rule.

## Phase 3 results: deterministic tools (2026-10-19)

Run: `uv run python -m claims_copilot.tools.score --data DIR`. The tools run on every claim (and
every provider with at least 40 visit lines) and are compared with `truth.sqlite`. Full output:
`eval/scorecards/`.

Protocol (decision 3A in `DECISIONS.md`): thresholds fixed from the definitions; the scorecard was
run on the dev dataset (seed 20261019) untuned; one tuning round was allowed on dev and used
(iterative trimming of the peer baseline, tried offline, no improvement, not adopted); the code
was committed (`c79a9b3`); only then was a second dataset (seed 20261020) generated and scored,
once. Parameters hash `d6536f635e00` on both runs.

Held-out dataset (seed 20261020; 40,060 claims, 64,247 lines, 620 flags, payer sha256 `fe43c393...`):

| Check | Unit | Positives | Found | Recall | Precision | Decoys raised | Clean raised |
|---|---|---|---|---|---|---|---|
| `exact_duplicate` | claim | 60 | 60 | 100% | 100% | 0 of 60 | 0 of 39,940 |
| `bundle_pair_without_exception` | claim | 30 | 30 | 100% | 100% | 0 of 30 | 0 of 40,000 |
| `units_above_line_limit` | claim | 30 | 30 | 100% | 100% | 0 of 30 | 0 of 40,000 |
| `line_date_outside_claim_window` | claim | 30 | 30 | 100% | 100% | 0 of 30 | 0 of 40,000 |
| `visit_mix_above_peer_range` | provider | 30 | 26 | 86.7% | 100% | 0 of 30 | 0 of 135 |

Dev dataset, untuned (seed 20261019): same table, except the outlier row is 28 of 30 (93.3%).
Line localisation (every labelled line cited by a finding) was 30 of 30 for the three line-level
types on both datasets. Of the queue screens, `SCR01` to `SCR03` and `SCR05` confirmed every flag on
a true case; `SCR04` confirmed 79 of 91 such flags held-out (87 of 93 on dev), the gap being the
missed providers.

Caveats: 100% on the claim-level checks only shows that the tools implement the stated rules over
labels made from the same rules (KF-018). The outlier misses are KF-017. The near-match tiers are
observations and are not in these numbers (KF-019). Diagnosis validation raised nothing on either
dataset (all claim diagnoses come from the FY2027 list). Scoring 40,060 claims takes about 20 seconds.

## API (Phase 4)

No accuracy claim: the API adds no analysis. What is measured is the contract and the cost of a call.

| Check | Result |
|---|---|
| Models match tool records | a test fails on any dataclass field with no model field, or the reverse (14 pairs) |
| No conclusion-named field | test walks `docs/openapi.json` schemas and parameters for `verdict`, `decision`, `recommendation`, `risk`, `priority`, `rank`, `severity`, `score` |
| No verdict language in live output | every flagged claim's dossier on generated data in tests; on the real default dataset, all 618 flagged dossiers and 400 provider results, 0 matches |
| Truth isolation | static scan of `api/`; the service answers every route with only `payer.sqlite` in its directory; opening the truth file raises |
| Hostile input | 9 path-id shapes (SQL text, 500 characters, Unicode digits, fullwidth letters, traversal, encoded newline) across 6 routes and 9 query shapes: always 404 or 422, value never echoed |
| Determinism | identical bytes for repeated success responses on 9 URLs |

Latency (loopback, sequential, 200 requests after 10 warm-up, macOS arm64, `d02b8d7`):

| Endpoint | p50 ms | p95 ms | max ms |
|---|---|---|---|
| `GET /claims/{id}` | 1.8 | 2.3 | 2.5 |
| `GET /claims/{id}/dossier` | 2.7 | 3.2 | 3.9 |
| `GET /providers/{id}/intensity` | 1.7 | 2.1 | 2.3 |
| `GET /providers/{id}/peers` | 1.8 | 2.1 | 2.2 |
| `GET /policy/search` | 2.1 | 2.5 | 20.1 |

This is service time for one client, not throughput. Policy search quality is the Phase 0 BM25 result
(recall@10 0.80, paraphrases 0.25; KF-002, KF-021).

## Planned

| Phase | Evaluation |
|---|---|
| 6 | Hybrid, reranking, contextual embeddings measured against the Phase 0 numbers above |
| 7 | About 100 gold cases: retrieval, tool, end-to-end, safety/refusal; LLM judge calibrated against hand labels; provider comparison (quality, latency, tokens, cost) |
