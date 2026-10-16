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

## Planned

| Phase | Evaluation |
|---|---|
| 6 | Hybrid, reranking, contextual embeddings measured against the Phase 0 numbers above |
| 7 | About 100 gold cases: retrieval, tool, end-to-end, safety/refusal; LLM judge calibrated against hand labels; provider comparison (quality, latency, tokens, cost) |
