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
| KF-017 | The provider-intensity check misses seeded outliers when many of a specialty's providers are themselves seeded. Dev (seed 20261019): 2 of 30 missed (P0171, P0203, orthopedics: 11 of 33 eligible providers seeded, peer MAD 0.084, scores 2.96 and 2.95). Held-out (seed 20261020): 4 of 30 missed (P0136, P0141, P0157, P0170, all cardiology: 17 of 42 seeded, MAD 0.089, scores 2.84 to 3.34). Cutoff is 3.5. No decoy and no clean provider was raised in either run | `eval/scorecards/*.md`. One tuning round was allowed and used: iterative trimming of peers at the same cutoff, tried offline on dev, left both misses at about 3.2, so it was not adopted. No further variants were tried | Open. Owner accepted it on 2026-10-19 and ruled out another tuning round; Phase 7 hand-built cases are the unbiased check. The contamination (33% to 40%) comes from packing 60 seeded providers among about 190 eligible ones, higher than a real peer group would plausibly be. Phase 7 hand-built cases are the unbiased check |
| KF-018 | The four claim-level checks score 100% recall and 0 false alarms on both datasets. That is not evidence of real-world accuracy: the tools and the generator share rule definitions (KF-011, KF-012), clean claims contain no near-misses other than the decoys, and no field is missing, mistyped, or noisy | `eval/scorecards/*.md` | Open. Accepted by the owner 2026-10-19. Read the result as "the tools implement the stated rules and the labels are consistent" |
| KF-019 | The near-match duplicate tiers (other provider with overlapping window; same provider within 30 days) fire on every duplicate-type decoy by design, and on a few clean claims: dev 34 clean claims (28 and 6), held-out 25 (18 and 7), plus 1 true duplicate case on the nearby-date tier. They are observations, never findings, and are not counted in precision. The 30-day window was set without tuning | `eval/scorecards/*.md` | Open. Accepted by the owner 2026-10-19: they stay labelled observations only. The investigator sees them labelled as ordinary-repeat candidates; the window is a parameter |

## Tooling

| ID | Failure | Status |
|---|---|---|
| KF-010 | The Cursor docs do not document a project path or argument passing for custom slash commands. `/teach` and `/phase-report` are implemented as skills with `disable-model-invocation` instead | Mitigated (see `DECISIONS.md`) |

## API (Phase 4)

| ID | Failure | Evidence | Status |
|---|---|---|---|
| KF-020 | The API has no authentication, rate limiting, or audit log. It binds to loopback by default and refuses another host without `--allow-remote`, but anyone who can reach the port can read all synthetic data | Owner decision 3A (2026-10-19); `tests/test_api_main.py` | Open by design. Phase 8 (auth, limits, audit), Phase 10 (exposure). Not production-ready |
| KF-021 | `GET /policy/search` is lexical only, so reworded questions miss (BM25 recall@10 0.25 on the 8 paraphrase questions; 0.80 overall) | Same numbers as KF-002 | Open. Phase 6 replaces the ranking behind the same endpoint |
| KF-022 | Starlette's `TestClient` deprecates plain `httpx` in favour of `httpx2`, which is not a verified dependency here; the one warning is filtered in `pyproject.toml` | Warning text in the installed `starlette/testclient.py` | Open. Owner chose 1A (verify, adopt only if verified). `source-verifier` returned UNVERIFIED on 2026-10-20: the package is real and from Pydantic, but not from the `httpx` maintainers and about 5 months old. Owner decided 4B on 2026-10-20: keep `httpx` and the filter until Starlette drops the fallback (`DECISIONS.md`) |

## Agent (Phase 5)

Evidence: the live smoke runs `p5-smoke-20261020` (first) and `p5-smoke-20261020-r2` (after the
flag-id fix), 28 investigations each, records in `data/runs/` (local). Same prompt `agent_v1`, same
two models. Run 3 (`p5-smoke-20261020-r3`) followed the owner's decisions on KF-023 to KF-025. These are single samples, not an eval.

| ID | Failure | Evidence | Status |
|---|---|---|---|
| KF-023 | PDF extraction splits a drop-cap first letter from its word ("N CCI"), so a quote that reads correctly to a person fails the verbatim check and the answer becomes `INVALID_OUTPUT` / `QUOTE_NOT_FOUND` | OpenAI claim-03 (run 1) and claim-06 (run 2): the quoted text is in chunk `ncci-pm-ch01:17-18:0028` except for the split "N CCI". Run 1 claim-09 failed for a different, correct reason: the model joined two sentences that are not adjacent in the chunk | Fixed 2026-10-20 (owner chose A): quotes are compared with whitespace ignored; a test shows a changed word still fails. Run 3: no `QUOTE_NOT_FOUND`. The loosening is a small, named trade (`DECISIONS.md`) |
| KF-024 | A screen flag and a check inside one dossier are one "source", so `CONFLICTING_EVIDENCE` built from them is rejected; models also describe "flag says X, check found nothing" as a conflict | OpenAI claim-01 (run 2) and Anthropic claim-04 (run 2) `INVALID_OUTPUT`; Two other `CONFLICTING_EVIDENCE` answers (Anthropic claim-01 and claim-06, run 2) passed only because they also cited a second tool result or a policy chunk. Whether the flag-versus-check mismatch is a conflict at all is a judgement for Phase 7 labels | Fixed 2026-10-20 (owner chose A): a flag is its own source, tested. Run 3 accepted 4 `CONFLICTING_EVIDENCE` answers, which is a new concern (KF-029) |
| KF-025 | The model-written `searched` list is held to 200 characters per item, and a correct `INSUFFICIENT_EVIDENCE` answer was discarded for exceeding it | Anthropic `edge-unanswerable` in both runs (the answer text was right; one item was longer than 200 characters) | Fixed 2026-10-20 (owner chose A): the runtime fills `searched` from its tool log and ignores the model's; tested. Run 3: both providers returned `INSUFFICIENT_EVIDENCE` correctly on the unanswerable question |
| KF-026 | The validator checks that citations exist and quotes are verbatim, not that they answer the question, so a thin answer can pass | OpenAI answered the unanswerable helicopter question `ANSWERED` / `SUPPORTED` in both runs; the run 1 record shows two real quotes and an honest "does not state a helicopter-specific requirement". The corpus has no such rule, so `INSUFFICIENT_EVIDENCE` was the better status. In run 3 (after KF-025 was fixed) OpenAI chose `INSUFFICIENT_EVIDENCE` on the same question, so this is also run-to-run variance | Open, by design until the Phase 7 judge and hand labels |
| KF-027 | Results vary between runs, and the models differ in reliability: OpenAI `INVALID_OUTPUT` on 2 of 10 claims in run 2 (3 in run 1), Anthropic on 1 of 10 (10 of 10 in run 1, caused by KF-028 below) | Different claims failed in the two runs for OpenAI (claim-01 passed in run 1 and failed in run 2). Run 3 passed 20 of 20, but the code differed between runs, so it is not a repeat | Open. 14 cases per provider cannot rank the models; Phase 7 measures this with repeats |
| KF-028 | **Fixed defect, kept for the record.** The runtime registered ids for flags but never showed them, so Anthropic cited the raw `flag_id` (`F000319`) and all 10 of its claim investigations failed with `UNRESOLVED_CITATION`; one cited the prompt's example id `E1.f1` | Run 1. The fix shows each flag with an `evidence_id` (`E1.s1`); run 2 passed 9 of 10 | Fixed in `agent/evidence.py` with a test. The validator did what it should: it refused every one |
| KF-029 | After KF-024 was fixed, models report "flag says X, check found nothing" as `CONFLICTING_EVIDENCE` often: 4 of 20 claim investigations in run 3 (OpenAI 1, Anthropic 3), in run 2, when such answers were mostly rejected, 2 were accepted (Anthropic) and 2 rejected. Whether that mismatch is a real conflict is unlabelled | Run 3 records, `data/runs/p5-smoke-20261020-r3/` (claims 01, 04, 06 for Anthropic; claim 01 for OpenAI) | Open. Possible over-reporting of conflict; the Phase 7 hand labels decide, and the prompt may need a definition (a prompt change needs an eval comparison) |
