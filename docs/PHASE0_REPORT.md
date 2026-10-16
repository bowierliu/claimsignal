# Phase 0 report: source corpus and baseline RAG

Status: awaiting owner approval. Nothing in Phase 1 has started.

## What was built

- **Verified corpus:** 23 public documents (NCCI Policy Manual, Medicare Claims Processing Manual
  Pub 100-04, Program Integrity Manual Pub 100-08, OIG reports, eCFR Title 42, ICD-10-CM FY27
  guidelines) plus 3 terms pages. 26 fetched sources are recorded in `SOURCES/manifest.jsonl`
  with URL, retrieval date, sha256 and terms note.
- **CPT descriptor redaction:** 131 descriptors removed at extraction and logged by hash in
  `SOURCES/redactions.jsonl` (the removed text itself is never stored). The redactor is
  heuristic; a spot check by the owner before any publish is recommended.
- **1,913 chunks** (about 1,800 characters, 250 overlap) with section headings and PDF page
  ranges, so every retrieved passage can be cited to a document and page.
- **Retrieval baselines:** pure-Python BM25 and OpenAI `text-embedding-3-small` dense retrieval,
  both scored on the same gold set.

## Gold set

40 questions: 32 direct (reuse the source's wording) and 8 paraphrase. A retrieved chunk counts
as a hit only if it comes from the named source and contains the verbatim evidence quote. All 40
quotes resolve to a chunk. Gold is defined by quote, not chunk id, so re-chunking will not
invalidate it.

## Results

| Method | Group | n | R@1 | R@5 | R@10 | MRR@10 |
|---|---|---|---|---|---|---|
| BM25 | all | 40 | 0.33 | 0.62 | 0.80 | 0.455 |
| BM25 | direct | 32 | 0.41 | 0.75 | 0.94 | 0.555 |
| BM25 | paraphrase | 8 | 0.00 | 0.12 | 0.25 | 0.057 |
| Dense | all | 40 | 0.38 | 0.72 | 0.82 | 0.513 |
| Dense | direct | 32 | 0.44 | 0.81 | 0.88 | 0.588 |
| Dense | paraphrase | 8 | 0.12 | 0.38 | 0.62 | 0.213 |

## Reading the results

- Dense is better overall and much better on paraphrases (R@10 0.25 to 0.62).
- BM25 is still better on direct questions at R@10 (0.94 vs 0.88). The two methods fail on
  different questions, which is the usual case for combining them (hybrid retrieval).
- Neither is good enough to rely on alone: about 1 in 5 questions has no correct chunk in the top
  10 for either method, and R@1 is under 0.45. Phase 6 (hybrid, reranking, query rewriting) is
  where this gets addressed. The agent must cite retrieved passages and say when it found none.

## Caveats (please read)

- The paraphrase group has **8 questions**. A difference of one question moves recall by 0.125.
  Treat the paraphrase numbers as directional, not as a measured improvement.
- The gold set was written by the assistant from the fetched documents, not by a domain expert.
  Direct questions may favour lexical matching. An owner review of the questions is recommended
  before they are used for any claim in the portfolio.
- Corpus is 23 documents; the real retrieval problem will be harder with more near-duplicate text.
- Gated sources (Medicare Coverage Database LCDs/Articles, PTP and MUE tables) are excluded until
  Phase 3 as decided.

## Cost

Embedding the full corpus plus 40 queries: **$0.0166** (conservative estimate was $0.0244).
Phase 0 cap is $3. Total spend: $0.0166 of the $50 cap. Every call is in `budget/ledger.jsonl`.

## Reproduce

```
uv run python -m claims_copilot.sources.fetch      # fetch + verify sources
uv run python -m claims_copilot.ingest.extract     # extract + redact
uv run python -m claims_copilot.ingest.chunk
uv run python -m claims_copilot.retrieval.dense --confirm
```

## Decisions needed from the owner

1. Approve Phase 0 and move to Phase 1.
2. Review the gold set (`eval/phase0_retrieval_gold.jsonl`), or accept it as provisional.
3. Confirm hybrid BM25 + dense is the starting point for Phase 6 (recommended).
