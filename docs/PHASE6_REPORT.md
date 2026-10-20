# Phase 6 report: retrieval upgrades

Status: **approved by the owner on 2026-10-20, with recommendations 2A, 3A and 4A.** No Phase 7 work has started.

## 1. Executive summary

I measured three standard retrieval upgrades against the Phase 0 baselines and kept the one that
works. **A hybrid search (BM25 + dense) followed by an LLM rerank of the top 20 raises recall at
rank 1 from 0.38 to 0.82 on the 40 development questions and from 0.38 to 0.81 on 16 fresh held-out
paraphrase questions.** Recall at 10 goes from 0.82 to 0.90 and from 0.69 to 0.81. The reranker did
almost all of the work. Hybrid fusion alone did not raise recall at 10, and contextual chunk
descriptions (the most expensive step, $0.36) added nothing once the reranker was in place, so I did
not adopt them.

What is built: the held-out gold set (written before any method ran), RRF fusion, a reorder-only
reranker whose output plain code validates, contextual descriptions (index-only), a paired
comparison harness, `--policy-mode hybrid` for the API with a visible fallback to BM25, and an
8-investigation agent re-check. The default API behaviour is unchanged.

## 2. Metrics and spend

Development set (n=40; 8 paraphrase) and held-out (n=16 paraphrase). Full tables, paired
gained/lost counts, and caveats: `EVALUATION.md`.

| Pipeline | R@1 dev | R@10 dev | R@1 held-out | R@10 held-out |
|---|---|---|---|---|
| V0 BM25 | 0.33 | 0.80 | 0.25 | 0.44 |
| V1 Dense | 0.38 | 0.82 | 0.38 | 0.69 |
| V2 Hybrid RRF | 0.38 | 0.80 | 0.38 | 0.75 |
| **V3 Hybrid + rerank** | **0.82** | **0.90** | **0.81** | **0.81** |
| V4 Dense contextual | 0.40 | 0.78 | not run | not run |
| V5 Hybrid contextual | 0.45 | 0.85 | not run | not run |
| V6 V5 + rerank | 0.78 | 0.88 | not run | not run |

- V3 lost no question that V2 found; rank improved on 16 development questions and worsened on none.
- Every V3 miss is a question whose answer was not in the top 20 candidates (development 4 of 4,
  held-out 3 of 3). The reranker is right whenever the answer is among its candidates.
- Cost: about $0.001 and about 3.5 s per uncached rerank. Phase 6 live spend **$0.4693** of the
  $2.00 ceiling and the $8 cap; total **$0.6383 of $50**. Breakdown: descriptions $0.3437 (1,913
  calls), their embeddings $0.0184, rerank $0.1071 (107 calls), agent re-check $0.0230 (counted in
  `p5`). Please check Cursor's own usage yourself; I cannot see it.
- Quality gates: 470 tests, ruff, ruff format, mypy strict, pre-commit all green. Code commit
  `0f203f2`.

Agent re-check (hybrid mode, 8 investigations, a smoke test): 7 of 8 as before. OpenAI answered the
unanswerable helicopter question `ANSWERED`, faithfully (it said the retrieved text does not cover
it and quoted prior-authorization text verbatim). That is KF-026 again, and KF-031 explains why
hybrid makes it more likely: dense search always returns something.

## 3. Failures and open risks

- **KF-030** The reranker can only reorder what fusion finds; the 7 misses are all outside the top
  20. A deeper list is untried to avoid tuning on the gold set.
- **KF-031** Hybrid search never returns "no hits", so "no relevant source" now rests on the model.
- **KF-032** Rerank adds a paid call and about 3.5 s; hybrid needs the key, the index, and cap
  headroom. Opt-in, with a visible fallback.
- **KF-033** Contextual descriptions did not help; recorded and not adopted.
- **KF-034 / KF-006** Both gold sets are assistant-drafted and small. A 12.5-point step on
  paraphrase and a 6.25-point step on held-out mean these are directions, not precise rates. The
  one large effect (the reranker) is large enough to trust; the small differences between V2, V4
  and V5 are not.
- Prompt-injection surface: the reranker reads untrusted chunk text. It can only return labels
  from the offered list, so it cannot add content; tests cover an injected instruction and
  malformed output. A rerank prompt change would need an eval comparison (AGENTS.md).
- Retrieval chunks sent to the model provider are public text with CPT descriptors redacted, as in
  Phase 0.

## 4. Decisions needed

1. **Approve Phase 6 as built?** Yes / change something.
2. **Make hybrid the API default later?**
   - A (recommended): keep it opt-in until Phase 7 measures unanswerable-question behaviour (KF-031)
     and the 100-case eval exists.
   - B: make it the default now (the API then depends on a paid key, cost, and 3.5 s per search).
3. **Candidate depth (KF-030).**
   - A (recommended): leave at 20 for now; revisit in Phase 7 with a larger gold set so tuning does
     not overfit 56 questions.
   - B: try depth 40 now and report both (about $0.2 more; a tuned setting on a small set).
4. **Contextual descriptions.**
   - A (recommended): keep the code as a documented negative result; do not use in the product.
   - B: remove the module and prompt to keep the repo smaller.

## 5. Teach-me list

1. **Reranking and candidate recall.** A reranker is a second, slower, smarter scorer applied to a
   short list from a fast retriever. It can fix the order but not the list, so its ceiling is the
   first stage's recall at the candidate depth (here 0.90 and 0.81). This is why "recall at 20" is
   the number to watch.
2. **Reciprocal rank fusion.** Combine ranked lists by summing 1/(k + rank) per document. It needs
   no score calibration between BM25 and cosine similarity, which is why it is the default fusion.
   It helped early ranks here but not recall at 10, so fusion is not automatically a win.
3. **Pre-registration on small eval sets.** Fixing variants, settings, and a held-out set before
   running (and reporting gained and lost questions, not only averages) is how a 40-question set
   avoids fooling you. One question is 2.5 to 12.5 points depending on the group.

Please confirm you understand these before I propose Phase 7.
