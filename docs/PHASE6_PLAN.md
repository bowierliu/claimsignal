# Phase 6 plan: retrieval upgrades

Status: **proposed, awaiting owner approval.** No Phase 6 code, prompt, or paid call exists yet.

## Goal

Find out, with measurements, whether three standard upgrades improve retrieval over the verified
policy corpus: **hybrid search** (BM25 plus dense), **reranking**, and **contextual embeddings**
(each chunk indexed with a short description of where it sits in its document). Keep what helps,
record what does not, and let the agent's `search_policy` use the winner.

Why now: the Phase 0 baseline is weak where it matters (BM25 R@10 0.80 overall and 0.25 on
paraphrases; dense 0.82 and 0.62; R@1 0.33 and 0.38; KF-001 to KF-004, KF-021), and the Phase 5
agent can only be as good as what it retrieves.

## Scope

In scope:

- A retrieval evaluation that compares a fixed list of variants on the same gold questions, paired
  question by question.
- Hybrid fusion (reciprocal rank fusion) of BM25 and dense.
- A reranker over the top candidates.
- Contextual chunk descriptions, used only to build the indexes.
- A server option so the API's policy search can use the winning pipeline, with a safe fallback.
- A small agent re-check of the policy-related smoke cases.

Out of scope: new sources (the corpus stays the 1,913 verified chunks), the 100-case eval and judge
(7), tracing and auth (8), any change to the tools, the scope gate, or the answer boundary. The
agent prompt `agent_v1` is not changed. Re-extracting PDFs to fix the drop-cap artifact (KF-023) is
not needed now that quote matching ignores whitespace.

## The variants (fixed before any run)

| ID | Pipeline |
|---|---|
| V0 | BM25 (Phase 0 baseline, recomputed with today's code as a check) |
| V1 | Dense `text-embedding-3-small` (Phase 0 baseline, recomputed) |
| V2 | Hybrid: reciprocal rank fusion of V0 and V1, k = 60 |
| V3 | V2, then rerank the top 20 |
| V4 | Dense over contextualised chunks |
| V5 | Hybrid of BM25 and dense, both over contextualised chunks |
| V6 | V5, then rerank the top 20 |

Settings (RRF k = 60, candidate depth 20, top 10 returned) are fixed now. I will not tune them on
the gold questions. Seven variants, no grid search: the point is to compare ideas, not to fit
numbers.

## Design notes

- **Reranker (default proposal).** One call to the cheap `gpt-6-luna` per query: the question and
  the 20 candidate chunks go in, and the model returns candidate ids in order. Plain code accepts
  only a list of ids that were in the candidate set (no repeats, no new ids) and otherwise keeps the
  fused order. The reranker can reorder text but never add or change it, so a prompt injection in a
  chunk cannot put new content in front of the agent. It adds one model call (about 5 to 10 seconds,
  about $0.001) per search; I will report that latency honestly.
- **Contextual descriptions.** For each of the 1,913 chunks, one `gpt-6-luna` call sees the document
  title, the section path, the previous and next chunk, and the chunk, and writes one or two
  sentences saying what the chunk is about. The text embedded is `description + chunk`. The
  description is used for indexing only. It is never shown to the agent, cited, or used by the quote
  check, which still runs against the original chunk text. Descriptions are cached by chunk hash,
  prompt version, and model so a rerun costs nothing, and the cache hash goes in the results.
- **Query-time cost and the API.** Dense search needs a paid query embedding (about $0.00002). The
  API stays free and offline by default; hybrid is opt-in at server start (`--policy-mode hybrid`),
  goes through `CostGuard` with the existing query cache, and falls back to BM25 with the response
  saying so if the key, the cap, or the index is missing. The response gains a field naming the mode
  used, so `docs/openapi.json` changes as a reviewable diff.
- **Prompts** (`prompts/contextualize_v1.md`, `prompts/rerank_v1.md`) are written as structured
  prompts with role, inputs, constraints, output schema, an example, and failure behaviour.
- **Source text goes to the model providers**, as it already does for Phase 0 embeddings. It is
  public (CMS, OIG, ICD-10-CM) with CPT descriptors redacted at ingest. Files with third-party terms
  stay local.

## Evaluation protocol

- Phase 0 gold set (`eval/phase0_retrieval_gold.jsonl`, 40 questions) is never edited. It is the
  development set: all 7 variants run on it, and the winner is chosen from it.
- New held-out set (decision 2): 16 more paraphrase questions in a new file
  `eval/phase6_retrieval_gold.jsonl`, each with a document and a verbatim quote, written **before
  any Phase 6 method is run**, wording chosen to avoid copying the quote's key terms. A test checks
  every quote resolves to a chunk. The winner (and V0 and V1) is run on this set once. It is still
  assistant-drafted (KF-006), so it supports a direction, not a precise rate.
- Metrics: R@1, R@5, R@10, MRR@10, overall and by direct versus paraphrase. For each variant versus
  V0 and V1, the **number of questions gained and lost**, not only the averages. With 8 paraphrase
  questions one question moves a rate by 12.5 points; the report says so next to every
  paraphrase number.
- All results go in `EVALUATION.md`, including variants that do not help. A negative result is
  recorded in `KNOWN_FAILURES.md`, not hidden.
- Agent re-check: rerun the 3 policy smoke cases plus the unanswerable question on both providers
  (8 investigations) with the winning pipeline. Not an eval.

## Build order (after approval)

1. Gold set: draft and test the 16 held-out questions (no method run yet).
2. Evaluation harness: fusion (RRF) and the variants list, tested with fakes. Recompute V0 and V1.
3. V2 (free, uses the cached Phase 0 embeddings).
4. Contextualiser with a dry run that prints the estimate; run only after you say go.
5. Contextual embeddings and V4, V5.
6. Reranker prompt, validator, and tests; V3 and V6.
7. Choose the winner on the development set; run once on the held-out set.
8. `--policy-mode hybrid` in the API (with fallback), snapshot update, and the agent re-check.
9. Update `DECISIONS.md`, `EVALUATION.md`, `KNOWN_FAILURES.md` (KF-001 to KF-004, KF-021),
   `ARCHITECTURE.md`, `README.md`, `RESUME_METRICS.md` (measured only), then `PHASE6_REPORT.md`.

## Budget check against `budget/caps.toml`

Cap `p6` is $8.00. Total spent so far is $0.146 of $50. Estimates from the corpus (1,913 chunks,
about 1,900 characters each, about 0.9M tokens) and the verified `gpt-6-luna` price ($0.10 input,
$0.50 output per 1M tokens):

| Item | Estimate |
|---|---|
| Contextual descriptions, one pass | about 3M input tokens and 0.2M output tokens: about $0.40 |
| Embeddings of 1,913 contextualised chunks and about 60 queries | about $0.03 |
| Rerank calls, 2 variants x 56 questions, 20 candidates each | about $0.12 |
| Agent re-check, 8 investigations | about $0.02 |
| **Total** | **about $0.60** |

I propose a **$2.00 ceiling for Phase 6 live spend** inside the $8 cap, which leaves room for one
rerun. The earlier Phase 5 estimate was 3 to 6 times too high, so I will state the number from
verified prices and the dry run before each paid step and wait for your go. I will not edit
`caps.toml`. As always, please check Cursor's own usage yourself; I cannot see it.

## Exit criteria

- All 7 variants measured on the development set and the winner measured once on the held-out set,
  with gained-and-lost counts, in `EVALUATION.md`.
- Hybrid search available in the API as an opt-in mode with a tested fallback; the contract diff
  reviewed; the default API behaviour unchanged.
- Reranker output validated by plain code (ids only, no additions); contexts never reach the agent
  or the quote check; both verified by test.
- `pytest`, `ruff`, `ruff format --check`, `mypy`, and pre-commit green; docs and `DECISIONS.md`
  updated; phase report written; no Phase 7 work started.

## Risks

- **Small gold set.** 40 plus 16 questions, assistant-drafted. A real difference of a few points
  cannot be shown; the report will say which differences are directional only.
- **Gains may not appear.** Contextual descriptions and reranking may add little on this corpus. That
  is a result, and the simpler pipeline is kept if so.
- **Reranker latency and cost** add a model call per search for the agent. Reported, not hidden.
- **Generated descriptions can be wrong.** They only influence ranking, never what is shown or
  cited, but a bad description could pull a wrong chunk up; the held-out set is the check.
- **Hit definition.** A chunk counts if it comes from the named source and contains the quote
  (Phase 0 rule). A reranker or fusion can promote a near-duplicate chunk that does not contain the
  quote; that counts as a miss and is a harder test than topic match.

## Decisions needed

1. **Reranker.**
   - A (recommended): LLM rerank with `gpt-6-luna`, ids only, validated. No new vendor or
     dependency; costs about $0.001 and a few seconds per search.
   - B: a local cross-encoder. Free per query but adds a heavy dependency (PyTorch) and model weights
     from a third party that I would have to verify first.
   - C: no reranker; measure hybrid and contextual only.
2. **Held-out questions.**
   - A (recommended): 16 new paraphrase questions, written before any method is run, used only to
     confirm the winner.
   - B: use only the 40 Phase 0 questions (no unbiased check on the chosen pipeline).
   - C: 40 new questions (a better check, but more drafting for you to review; KF-006 still applies).
3. **API integration.**
   - A (recommended): hybrid opt-in at server start, default stays free lexical, fallback to BM25.
   - B: make hybrid the default, which makes the API depend on a paid key and the cap.
   - C: keep the API lexical only; hybrid lives in the library and the agent re-check.
