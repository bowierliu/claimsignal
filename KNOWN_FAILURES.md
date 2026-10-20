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

## Synthetic data (Phase 2)

| ID | Failure | Status |
|---|---|---|
| KF-011 | Circularity: the same author wrote the generator and the reference checker. Agreement shows the labels are internally consistent, not that the data resembles real claims or that a real detector would score the same | Open. Decoys, a separate checker, and the separate truth store limit it; Phase 7 adds hand-built cases |
| KF-012 | The bundle and unit rules are invented, not NCCI or MUE. The unit limit applies per line, not per member per day as real unit limits do, so day-level excess-unit logic is not exercised | Open. Phase 3 decision (2026-10-19): keep the synthetic rules behind a swappable `RulesProvider`; real tables stay deferred (KF-009) |
| KF-013 | Procedure codes are fake while diagnosis codes are real ICD-10-CM, so diagnosis-to-procedure pairings are random and not clinically meaningful | Open. By design; a diagnosis-procedure plausibility tool cannot be tested on this data |
| KF-014 | Post-hoc change to the reference checker: the outlier rule first required share of at least 3x the peer median. At full scale, 2 of 30 labelled outliers (P0171, P0203, share 0.56) were missed because 11 of 33 orthopedics peers were seeded elevated cases, which pulled the peer median to 0.19 (threshold 0.57). The multiple was changed to 2x after seeing this, so the full-scale "100% recovered" result is on an adjusted rule | Open. Lesson for Phase 3: a median-ratio peer screen degrades when many peers are elevated; report peer-group composition and prefer a robust statistic |
| KF-015 | ICD-10-CM source: the CDC policy says "Most of the information" is public domain and no notice specific to the code file was found. The FY27 file also contains 18 codes with a `QA` prefix that were not researched and are excluded from the subset | Open. Re-check terms before publishing |
| KF-016 | Dates are fictional and fall inside the ICD-10-CM FY2027 window (2026-10-01 to 2027-09-30) so every diagnosis code is valid on its service date; some are after today | Accepted. Documented in `DATA_MODEL.md` |
| KF-017 | The provider-intensity check misses seeded outliers when many of a specialty's providers are themselves seeded. Dev (seed 20261019): 2 of 30 missed (P0171, P0203, orthopedics: 11 of 33 eligible providers seeded, peer MAD 0.084, scores 2.96 and 2.95). Held-out (seed 20261020): 4 of 30 missed (P0136, P0141, P0157, P0170, all cardiology: 17 of 42 seeded, MAD 0.089, scores 2.84 to 3.34). Cutoff is 3.5. No decoy and no clean provider was raised in either run | `eval/scorecards/*.md`. One tuning round was allowed and used: iterative trimming of peers at the same cutoff, tried offline on dev, left both misses at about 3.2, so it was not adopted. No further variants were tried | Open. The contamination (33% to 40%) comes from packing 60 seeded providers among about 190 eligible ones, higher than a real peer group would plausibly be. Phase 7 hand-built cases are the unbiased check |
| KF-018 | The four claim-level checks score 100% recall and 0 false alarms on both datasets. That is not evidence of real-world accuracy: the tools and the generator share rule definitions (KF-011, KF-012), clean claims contain no near-misses other than the decoys, and no field is missing, mistyped, or noisy | `eval/scorecards/*.md` | Open. Read the result as "the tools implement the stated rules and the labels are consistent" |
| KF-019 | The near-match duplicate tiers (other provider with overlapping window; same provider within 30 days) fire on every duplicate-type decoy by design, and on a few clean claims: dev 34 clean claims (28 and 6), held-out 25 (18 and 7), plus 1 true duplicate case on the nearby-date tier. They are observations, never findings, and are not counted in precision. The 30-day window was set without tuning | `eval/scorecards/*.md` | Open. The investigator sees them labelled as ordinary-repeat candidates; the window is a parameter |

## Tooling

| ID | Failure | Status |
|---|---|---|
| KF-010 | The Cursor docs do not document a project path or argument passing for custom slash commands. `/teach` and `/phase-report` are implemented as skills with `disable-model-invocation` instead | Mitigated (see `DECISIONS.md`) |
