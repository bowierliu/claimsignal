# Known failures

Failures stay visible. Never edit the corpus, gold sets, or tests to make a failing case pass; add
or update an entry here instead. Newest last within each section. Numbers come from the Phase 0
runs recorded in `docs/PHASE0_REPORT.md` (gold set `eval/phase0_retrieval_gold.jsonl`, n=40).

## Retrieval

| ID | Failure | Evidence | Status |
|---|---|---|---|
| KF-001 | Both BM25 and dense miss the correct chunk in the top 10 for 4 of 40 gold questions: g09 (`ncci-pm-ch11`), g21 (`ecfr-405-c`), p02 (`ncci-pm-ch11`), p03 (`clm104-ch01`) | Phase 0 run on 2026-10-16; chunk ids in the run output | Open. Phase 6 (hybrid, reranking, contextual embeddings) is the planned fix and is measured against Phase 0 |
| KF-002 | BM25 is near-useless on paraphrased questions: R@10 0.25 on 8 paraphrase questions | Phase 0 run | Open. Expected for lexical search; dense reaches 0.62 |
| KF-003 | Dense misses 3 questions BM25 finds (g19, g29, p06); dense direct R@10 is 0.88 versus BM25 0.94 | Phase 0 run | Open. Motivates hybrid in Phase 6 |
| KF-004 | R@1 is low for both methods (BM25 0.33, dense 0.38 over 40 questions) | Phase 0 run | Open. Reranking planned in Phase 6 |

## Evaluation quality

| ID | Failure | Status |
|---|---|---|
| KF-005 | The paraphrase group has only 8 questions; one question moves recall by 12.5 points, so paraphrase numbers are directional | Open. Phase 7 builds a larger gold set |
| KF-006 | The gold set was drafted by the assistant, not a domain expert, and was accepted by the owner as provisional on 2026-10-16. Direct questions may favour lexical matching | Open. Phase 7 adds hand-labelled cases and judge calibration |

## Data and ingest

| ID | Failure | Status |
|---|---|---|
| KF-007 | CPT descriptor redaction is regex-based and heuristic; it can miss a descriptor or over-redact. 131 redactions were logged for the Phase 0 corpus | Open. Spot-check before any publish (see the pre-publish checklist in `ROADMAP.md`) |
| KF-008 | Terms for OIG, eCFR, and NCBI could not be read (CAPTCHA or JavaScript pages); recorded UNVERIFIED in the manifest. Sources are US government works fetched for local use only, with raw files gitignored | Open. Owner accepted the risk; re-check before publishing |
| KF-009 | Gated sources (Medicare Coverage Database LCDs/articles, PTP and MUE tables) are not in the corpus | Deferred to Phase 3 with the owner |

## Tooling

| ID | Failure | Status |
|---|---|---|
| KF-010 | The Cursor docs do not document a project path or argument passing for custom slash commands. `/teach` and `/phase-report` are implemented as skills with `disable-model-invocation` instead | Mitigated (see `DECISIONS.md`) |
