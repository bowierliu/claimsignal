# Session log

Newest last. Facts only; decisions and their reasons live in `DECISIONS.md`.

## 2026-10-13 to 2026-10-15: Phase 0 kickoff and bootstrap

- Checked the environment: macOS 13.6.7 (arm64), uv with Python 3.12, no Homebrew, Go or gh.
  Source sites, NCBI and PyPI were reachable. CDC rejects bare browser user-agents (HTTP 403),
  so fetch clients must send a descriptive one.
- Old repo is at `~/Projects/hc_rag_proj` (7 commits, no remote, clean tree). No Desktop backup
  found. Its deletion gate is at the end of Phase 1 and is unchanged.
- Owner answered the kickoff questionnaire (see `DECISIONS.md`).
- Built the bootstrap: uv project, ruff, strict mypy, pytest, pre-commit with gitleaks v8.30.1, a
  Cursor `beforeShellExecution` hook that blocks credentials in shell commands, and the cost guard
  with caps and a ledger. First manifest entry: `openai-api-pricing`.
- All 36 tests, ruff, mypy and pre-commit were green. The commit was blocked by git 2.24.3.
- 2026-10-15: owner installed Command Line Tools 14.3.1 (git 2.39.2). Owner deferred GitHub until
  project end (see `DECISIONS.md`). Vault remote switched to SSH. `.env` created with empty keys.
- API spend: $0.00.

## 2026-10-15: Phase 0 corpus, chunking, retrieval baselines

- Owner approved the 23-document seed list; CPT descriptors are redacted at ingest (131 redactions
  logged by hash in `SOURCES/redactions.jsonl`). Two terms pages recorded as unverified.
- Fetched and verified 26 sources, extracted page-anchored text, chunked into 1,913 chunks.
- Built a 40-question gold set (32 direct, 8 paraphrase) defined by verbatim evidence quotes. All
  40 quotes resolve to a chunk of the named source.
- BM25 baseline (all n=40): R@1 0.33, R@5 0.62, R@10 0.80, MRR@10 0.455. Direct R@10 0.94;
  paraphrase R@10 0.25. The paraphrase gap is the case for dense retrieval.
- Added the dense baseline (`text-embedding-3-small`) behind CostGuard, with an incremental
  on-disk index and query cache. Request shape checked against the OpenAI OpenAPI spec. Dry run
  estimates about $0.024 for the full corpus (Phase 0 cap is $3).
- `OPENAI_API_KEY` is still empty in `.env`, so no embedding call has been made. Run
  `uv run python -m claims_copilot.retrieval.dense --confirm` once the owner has set the key.
- Commit `e679c5e` passed the full pre-commit gate (gitleaks, ruff, mypy, pytest) without
  `--no-verify`. 98 tests passing.
- API spend: $0.00.

## 2026-10-16: Dense baseline run and Phase 0 report

- Owner saved `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` in `.env` (checked for non-empty only,
  values never read or printed). `NCBI_API_KEY` is still empty and not needed yet.
- Ran `retrieval.dense --confirm`: embedded 1,913 chunks and 40 queries for $0.0166 total.
- Dense baseline (all n=40): R@1 0.38, R@5 0.72, R@10 0.82, MRR@10 0.513. Paraphrase R@10 0.62
  (BM25 0.25, n=8); direct R@10 0.88 (BM25 0.94).
- Wrote `docs/PHASE0_REPORT.md` for owner approval. Phase 1 not started.
- API spend: $0.0166.

## 2026-10-16: Phase 1 foundation

- Owner approved Phase 0, accepted the gold set as provisional, and confirmed hybrid retrieval as
  the Phase 6 starting point.
- Measured overlap at rank 10 from the cached index (no spend): both methods miss 4 of 40;
  BM25 finds 3 that dense misses; dense finds 4 that BM25 misses; union 36 of 40. Corrected the
  Phase 0 report, which had said "about 1 in 5" were missed by both methods.
- Checked Cursor docs via the cursor-guide subagent. Added `.cursor/rules` (5), `.cursor/skills`
  (6), `.cursor/agents` (file-scout, source-verifier), CI workflow, and the records
  (`ARCHITECTURE`, `EVALUATION`, `KNOWN_FAILURES`, `ANSWER_BOUNDARY`, `DATA_MODEL`,
  `RESUME_METRICS`, README results-first).
- Tests: 125 passing. Pre-commit all hooks passing. API spend still $0.0166.
- Naming research delegated to a subagent (PyPI, GitHub API, RDAP, web search).
- Old-repo gate, steps (a) and (b) (read-only listing, then archive; nothing deleted):
  `~/Projects/hc_rag_proj` has 7 commits, 50 tracked files, no remote, clean working tree, 198 MB
  (156 MB `.venv`, 40 MB `.mypy_cache`). No Desktop backup was searched for (owner said none).
  Archive `~/Projects/hc_rag_proj_archive_2026-10-16.zip` (366 KB, 302 entries, excludes `.env`,
  `.venv`, caches, `.DS_Store`; `unzip -t` clean; sha256
  `bd53c73cb26d6130386e4421c7efa135b44f1287eb6c5f529148039c6cf36263`). The old git history
  includes a commit that replaced real CPT codes with placeholders, so keep the archive outside
  this repository.
- Name research: two subagent batches (20 candidates) plus a manual re-check of the two batch-one
  survivors. Owner chose to keep `claims-copilot` and decide before publishing.

## 2026-10-19: Old repo deleted, Phase 1 approved

- Owner typed `DELETE OLD REPO`. Checks before deletion: archive sha256
  `bd53c73cb26d6130386e4421c7efa135b44f1287eb6c5f529148039c6cf36263` matched; `unzip -t` passed;
  old repo clean at HEAD `7a1a8e6`; ignored `docs/INTERVIEW_NOTES.md` (20,434 bytes) identical in
  the archive.
- Deleted `~/Projects/hc_rag_proj`. Verified it is gone and the archive remains with the same
  hash. `~/Projects/cli_mentor` was not touched.
- Phase 1 approved by the owner. Phase 2 plan written for review; no Phase 2 code started.

## 2026-10-19: Phase 2 step 0 (ICD-10-CM source)

- URL read from the official CDC/NCHS FY2027 directory listing; fetched with the project client.
  `icd10cm-code-descriptions-2027.zip`: 2,192,779 bytes, sha256
  `93e3ad6004badf470c55bfe679b748ae88fd9b2b421851e409eec382c7713b9a`, VERIFIED.
- Contents (read, not assumed): `icd10cm-codes-2027.txt` (about 74,900 lines: code, then long
  title), an order file, two addenda files, and two file-format PDFs. No license notice inside.
- `curl` failed certificate verification once in the sandbox. I did not disable verification; the
  project `httpx` client (which verifies certificates) worked.

## 2026-10-19: Phase 2 build

- Code in `src/claims_copilot/synth/`, tests `tests/test_synth_*.py` and `tests/synth_oracle.py`;
  commits `bc0d534` (source step) and `b22a9b4` (generator, anomalies, store).
- Default dataset: 40,060 claims, 64,098 lines, 300 labelled cases, 618 flags (210 on real-anomaly
  claims, 208 on decoy claims, 200 false alarms). Generation about 3 seconds.
- First full-scale checker run recovered 28 of 30 outlier labels; cause and fix in KF-014.
- Found that `data/synth*` was not gitignored (`git check-ignore` returned 1) before committing;
  added the ignore rules, then deleted my own scratch outputs file by file. Nothing large was
  staged.
- The auto-review blocked two commands as "before plan approval" although the owner had approved
  the plan; both were retried through the approval card and went through.
- Phase 2 spend: $0.00.

## 2026-10-19: Phase 3 (deterministic tools)

- Code in `src/claims_copilot/tools/` (repository, rules, icd, lookups, edits, duplicates, codes,
  patterns, dossier, score); tests `tests/test_tools_*.py` and `tests/tool_fixtures.py`; frozen
  commit `c79a9b3`.
- Dev run (seed 20261019, untuned): claim-level 100%, outliers 28 of 30. Held-out (seed 20261020,
  generated after the freeze): claim-level 100%, outliers 26 of 30. Scorecards in `eval/scorecards/`.
- The full ICD-10-CM file loads from `data/raw/` with its hash checked against the manifest and
  contains the whole committed subset; that test is skipped, visibly, where the file is absent.
- Held-out data lives in `data/synth_heldout/` (gitignored, regenerate with `--seed 20261020`).
- Phase 3 spend: $0.00. Total $0.0166 of $50.

## 2026-10-19: Phase 3 approved, Phase 4 plan proposed

- Owner approved Phase 3 (commit 4370358 records it) and chose 1A, 2A. Phase 4 plan written in `docs/PHASE4_PLAN.md`; three decisions open; no Phase 4 code or dependencies added. Phase 4 cap $0.00; total spend unchanged at $0.0166 of $50.

## 2026-10-19: Phase 4 built (commit `d02b8d7`)

- Owner approved the Phase 4 plan with 1B, 2A, 3A. Built `src/claims_copilot/api/`: `schemas.py`
  (Pydantic models and converters), `app.py` (routes, handlers, tool manifest), `policy.py` (BM25
  over verified chunks), `snapshot.py` (`docs/openapi.json`), `bench.py`, `__main__.py` (loopback).
- Added `fastapi` 0.150.0, `pydantic` 2.14.1, `uvicorn` 0.54.0. Small Phase 3 changes: flag cursor
  (`after`, `next_after`), `Repository.meta` and `count_claims`, id patterns use `[0-9]`.
- 298 tests pass (86 new API tests). Latency and full-queue scan recorded in `RESUME_METRICS.md`.
- An automatic commit check briefly blocked the commit because of the earlier "do not start Phase 4
  before approval" instruction; the owner's approval had already been given, and the commit went
  through after confirming it.
- Phase 4 spend: $0.00 against a $0.00 cap. Total $0.0166 of $50.

## 2026-10-20: Phase 4 approved

- Owner approved Phase 4 as built (KF-020 to KF-022 accepted) and chose 1A for `httpx2`.
- `source-verifier` checked `httpx2` over read-only PyPI and GitHub lookups: UNVERIFIED on the
  same-maintainers criterion (Pydantic-stewarded continuation, first release 2026-05-11). Details in
  `DECISIONS.md`. No dependency changed. Spend: $0.00; total $0.0166 of $50.
- Phase 5 plan drafted in `docs/PHASE5_PLAN.md`; no Phase 5 code written.

## 2026-10-20: Phase 5 plan approved; step 1 (source verification)

- Owner approved `docs/PHASE5_PLAN.md`. `source-verifier` fetched and recorded 11 VERIFIED
  operational sources in `SOURCES/manifest.jsonl`: OpenAI and Anthropic pricing, tool-calling,
  structured-output, request-reference and (Anthropic) model-overview and deprecation pages. I
  spot-checked the gpt-6-luna and Claude Haiku 5.5 prices and the `claude-haiku-5-5` id against the
  raw pages. No `prices.toml` entry yet: the owner approves the two model ids first. No spend.

## 2026-10-20: Phase 5 built; smoke runs done

- Built `src/claims_copilot/agent/` (types, answer schema, evidence registry, validator, scope
  gate, tool runner over the in-process app, bounded loop, run records, two provider adapters over
  `httpx`, `smoke.py`) and `prompts/agent_v1.md`. 128 new tests; 426 in total; ruff, mypy strict,
  and pre-commit green. Commit `133e3d4`.
- Live smoke, `uv run python -m claims_copilot.agent.smoke --confirm`: two probes (2 cases per
  provider), run 1 (28 investigations) and run 2 (28, after showing flags with citable ids).
  Records in `data/runs/p5-*` (gitignored). Spend $0.0877 on `p5`; total $0.1043 of $50.
- Run 1 found a real defect (flag ids never shown to the model), fixed with a test. Remaining
  failures are in `KNOWN_FAILURES.md` KF-023 to KF-027.
- One fix to a test I wrote: a guard test matched the word "CostGuard" in a docstring; it now
  checks imports.

## 2026-10-20: Phase 5 approved; decisions 1A 2A 3A applied

- Owner approved Phase 5 as built (KF-023 to KF-028 accepted) and chose 1A, 2A, 3A. Implemented
  whitespace-insensitive quote matching, flags as their own source, and a runtime-filled `searched`;
  changed 1 validator test for the new rules and added 3 tests. 429 tests pass.
- Smoke run 3 (`p5-smoke-20261020-r3`): 20 of 20 claim investigations shown; $0.0417. Phase 5
  spend $0.1294 of $8; total $0.1460 of $50. New KF-029 (possible over-reporting of conflict).
- Phase 6 plan drafted in `docs/PHASE6_PLAN.md`; awaiting owner approval. No Phase 6 code written.

## 2026-10-20: Phase 6 started (build steps 1 to 4, no paid call yet)

- Owner approved the Phase 6 plan (rerank A, held-out A, API A; $2.00 live ceiling).
- Wrote `eval/phase6_retrieval_gold.jsonl` (16 paraphrase questions) before running any variant.
  The wording avoids the quote's key terms. Writing it found one item (`h16`) whose quote spans
  interleaved PDF columns and matched no chunk; it was replaced by a different passage before any
  method ran. Test added that every quote resolves to a chunk.
- Added `retrieval/fusion.py` (RRF k=60, paired gained/lost compare), `retrieval/phase6.py`
  (offline V0 to V2 runner, cached query embeddings only), `retrieval/contextual.py` (guarded
  description generator, cache by prompt/model/chunk hashes, $2.00 ceiling) and
  `prompts/contextualize_v1.md`. All covered by tests with fakes. No paid call made.
- V0 and V1 recompute to the Phase 0 numbers exactly. V2 (hybrid) on the 40 dev questions:
  R@10 0.80, R@5 0.78, MRR@10 0.533 (see EVALUATION.md).

## 2026-10-20: Phase 6 built; report written, awaiting owner approval

- Ran the 1,913 contextual descriptions after a 10-chunk pilot and an owner go ($0.3437, about 23
  minutes with 4 workers); embedded them ($0.0184); added the reranker and ran V3 and V6 on the
  development set; ran the winner (V3) and references on the held-out set once.
- Built `retrieval/rerank.py`, `retrieval/pipeline.py`, `--policy-mode hybrid` (response fields
  `mode`, `fallback_reason`; `bm25` nullable; `docs/openapi.json` regenerated) and
  `agent.smoke --policy-mode/--kinds`. 470 tests pass; no test uses the network.
- Agent re-check: 8 investigations, $0.0230. Phase 6 live spend $0.4693 of $2.00; total $0.6383.
- Wrote `docs/PHASE6_REPORT.md`; KF-030 to KF-034 added; KF-001 to KF-004 and KF-021 updated.

## 2026-10-20: Phase 6 approved

- Owner approved Phase 6 and recommendations 2A, 3A, 4A. Roadmap and report status updated. Phase 7
  not started; waiting for the owner to confirm the Phase 6 teach-me list before it is proposed.

- Owner answered the Phase 6 teach-me list (reranker ceiling, RRF, pre-registration). Drafted docs/PHASE7_PLAN.md (proposed; no Phase 7 code or spend).
- Owner chose 1A, 2A, 3A, 4A on the Phase 7 plan. Build has not started; waiting for the go.
- Phase 7 step 1: pre-registration (docs/PHASE7_PREREGISTRATION.md, eval/phase7_preregistration.json, eval/rubrics/, src/claims_copilot/evals/, tests/test_evals.py). No provider call, no spend.
- Phase 7 steps 2 to 5 committed (hand-built fixture and E5, unanswerable, e2e, safety cases). Step 6: `evals/runner.py` (resumable, locked guard, per-thread stacks, dry run) and `tests/test_evals_runner.py`; `phase` arguments added to `Investigator`, `Reranker`, `load_pipeline`, `load_policy_index`. Dry-run estimates: dev lexical $0.30, dev hybrid $0.23, test lexical $0.63, test hybrid $0.37. Found KF-037 (gate blocks four unanswerable questions) from the dry run.
- 2026-10-20: Phase 7 step 7. Dev runs done: lexical 192 jobs ($0.3981; 168 paid, 24 scope-gated at $0), hybrid 66 jobs ($0.2233). Judge (`evals/judge.py`, `prompts/judge_v1.md`) run over the 122 dev lexical answers that have statements to judge ($0.108). Scorecards written to `eval/scorecards/p7_dev_lexical.json` and `p7_dev_hybrid.json` (deterministic metrics only; dev is not the reported result). Label sheet built (`evals/labels.py`): 40 items, 169 statements, seed 7, amendment A3. `evals/calibrate.py` + tests written; it refuses non-owner rows. KF-038 to KF-040 added. Phase 7 live spend about $0.85 of the $4.00 ceiling. STOP: waiting for the owner's hand labels; test split and calibration not run.
- 2026-10-20: Labels arrived as a GPT Sol draft (not owner hand labels). Amendment A4 and KF-041 recorded. Pipeline changed: rows carry `label_source` and `owner_review`; file is `eval/phase7_model_drafted_labels.jsonl`; `calibrate.read_labels` refuses the assistant, judge models and unknown sources. Ingested the draft unchanged (185 rows: 169 statements S141 P9 C19 N0, conflict W6 N2, pattern F6 O2, honest Y8). Calibration by the registered rule: judge accepted (kappa 0.7535, false supported 2, minority 28); conflict not calibrated (8 < 10). No provider call.
- 2026-10-20: Phase 7 step 8 and 9. Test split run: lexical 378 jobs $0.6814, hybrid 114 jobs $0.5898; judged 229 + 39 answers ($0.2). Phase 7 spend $2.3508. Judge accepted by the registered rule vs model-drafted labels (A4). Targets missed: unanswerable 0.64, judged faithfulness 0.789. Hybrid not better (gained 0, lost 1 of 19), default stays lexical. KF-042 to KF-047. Report: `docs/PHASE7_REPORT.md`. 607 tests.
- 2026-10-20: Phase 8. Added `obs/redact.py`, `obs/trace.py`, `obs/audit.py`, `api/guard.py`; `Investigator` takes optional `tracer` and `audit`; `create_app` takes an optional `Guard`; the API runner refuses a non-loopback bind without `CLAIMS_COPILOT_API_KEY`. 649 tests (42 new), no provider call, no spend. `docs/SECURITY.md`, `docs/PHASE8_REPORT.md`; KF-048 to KF-050.
