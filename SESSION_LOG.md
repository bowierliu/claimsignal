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
- 2026-10-20: Phase 9. `/workbench` static page (HTML, CSS, plain JS) in `src/claims_copilot/api/web/`, served by `api/workbench.py` with a strict content security policy, outside `docs/openapi.json`; page files open, data behind the key. Tests: headers, whitelist, no unsafe sinks, same-origin requests, `node --check`, and a Node fake-DOM run on real API payloads with hostile text. KF-051, KF-052. No provider call, no spend.
- 2026-10-20: Phase 10. `Dockerfile`, `.dockerignore`, `deploy/entrypoint.sh`, `deploy/compose.yaml`, `deploy/ecs-task-definition.json`, `docs/DEPLOYMENT.md`; 14 static tests. Not built (no container runtime, KF-053). Ran the server command locally with a generated key: 401 without key, 200 with, audit chain verified. `.gitignore` gained `data/audit/` and `data/traces/` (found while running: the audit file was untracked and not ignored). KF-053 to KF-055. No provider call, no spend.
- 2026-10-20: Phase 11. gitleaks over all 51 commits: no leaks (findings redacted; a scan of the working directory flags ignored local files such as `.env` and `data/`, which are untracked and not read). Tracked-content checks: no sqlite, PDF, csv or zip tracked; no absolute home paths; no named health-plan companies. README rewritten results-first; `RESUME_METRICS.md` extended (674 tests, spend $2.9890 of $50); `docs/FINAL_REPORT.md` written with the interview Q&A and the decisions made on the owner's behalf (label provenance A4 listed first). No provider call, no spend. Project complete pending owner items: licence, product name, public vs private, a human check of the labels (KF-041), a real-browser pass (KF-052), a container build (KF-053).
- 2026-10-20: Independent-author tool test (KF-018), step 1 and pre-registration. Wrote `eval/independent/BRIEF_for_sol.md` (no code, thresholds, tool column names or data rows from this repo). sha256 of the brief: `eb213864c5d8c6bcc0814d7c57a1f3c6e751ace09622b8adc7119d770e3c44a5`. Pre-registration in `DECISIONS.md` (same date). Waiting for the owner to run the brief in a Sol chat and drop `claims.jsonl`, `rules.json`, `labels.jsonl` into `eval/independent/`. No claims written by me, no provider call, no spend.
- 2026-10-20: Independent-author tool test, steps 3 to 6. Sol's three files copied from the agent store into `eval/independent/` (sha256 matched the values Sol reported; contents not edited). New `src/claims_copilot/evals/independent.py` (validate, mechanical id rename, temporary payer and label stores in `data/independent/`, unchanged `tools.score.score_dataset`, per-case Wilson table) and `tests/test_evals_independent.py`. Validation passed with no problems. Result: unbundling, excess units, date anomaly, duplicates each 10 of 10 true cases; 1 of 40 decoy cases raised (DUP-D-10); 0 clean raised; intensity 0 of 10 (all providers scored). Misses classified in `EVALUATION.md`; KF-056 to KF-059; KF-018 updated. No tool, test, threshold or label changed. No provider call, no spend. `claims.jsonl` is committed as `claims.jsonl.gz` because the large-file hook limits files to 1 MB (decompressed sha256 equals Sol's).
- 2026-10-20: Owner decision on the independent-author test: provider-intensity miss (0 of 10) recorded as an open limit, not tuned; wording corrected across KF-018, KF-056 to KF-059, EVALUATION, RESUME_METRICS, README, FINAL_REPORT; DECISIONS entry; ROADMAP follow-ups added. No code change, no spend.
- 2026-10-20 (later): Wording correction. "Partly produced by data shaped to fit the tool" replaced with "does not carry over to an independent author's data; the cause is not established" plus the unranked candidate causes; scope ("our own generated data") added where results were stated without it. Docs only; no tool, test, case or label change.

## 2026-11-03: KF-041 owner re-review sheet prepared (follow-up b)

- Owner chose follow-up (b): a human check of the model-drafted calibration labels. Built
  `evals/owner_review.py` (prepare/check/ingest; deterministic; no provider calls) plus 8 tests.
  Selection, computed from the committed labels and the recorded judgments: the 19 CANNOT_TELL
  statements, the 2 false-supported statements (L11.7: draft PARTLY, judge SUPPORTED; L24.3: draft
  CANNOT_TELL, judge SUPPORTED), and the 8 conflict answers; 19 items, 36 prompts, sources shown
  in full (no 900-character cut). Non-conflict items show only the reviewed statements; conflict
  items also show the answer's other labelled statements as context. Sheet and audit key:
  `eval/labeling/phase7_owner_review_sheet.md`, `phase7_owner_review_key.json`. Method fixed in
  `DECISIONS.md` before any owner label exists. 694 tests pass; ruff, format, mypy clean; no spend.
- Waiting: the owner labels the sheet (about 30 minutes), then `owner_review ingest` and a
  deterministic `evals.calibrate` re-run; KF-041, KF-043, EVALUATION.md and RESUME_METRICS.md are
  updated with the result either way. DUP-D-10 ruling asked at the same sitting (KF-057).

## 2026-11-03 (later): Owner decisions; container blocked on missing Homebrew; browser approved

- State check: commit 8a90a9f, clean tree; the owner review sheet is still empty (0 of 36); the
  reports were verified current against the repository.
- Six owner decisions (structured questions): container = install colima + docker CLI via Homebrew
  then build/run/test; browser = one-time local-only pass on `/workbench` approved (127.0.0.1, no
  external sites; the no-browser rule itself is unchanged); license = MIT (`LICENSE` added, holder
  `bowierliu`); name = keep `claims-copilot`, with the real USPTO search and PyPI/GitHub/domain
  re-checks to run before publishing; visibility = PUBLIC (owner read-through and a gitleaks
  re-run over full history still precede publishing; the owner publishes himself); DUP-D-10 =
  Sol's label is right (KF-057 updated; the false alarm stays counted).
- Container blocked the same day: no container runtime AND no Homebrew on this machine (macOS
  13.6.7 arm64; no MacPorts, nix, colima or lima leftovers). The approved colima path needs
  Homebrew installed first (a sudo system change) — presented to the owner as a separate gate.
  KF-053 stays open.
- DECISIONS.md, ROADMAP.md, KF-057, EVALUATION.md updated. No provider call, no spend.

## 2026-11-03 (later still): Browser pass done (KF-052 closed); name checks run; label sheet still empty

- Label sheet re-checked: 0 of 36 prompts filled. The human label review remains the owner's
  pending task; nothing was filled in, altered, or inferred.
- Browser: the owner reversed the no-browser decision ("approve reversing the existing browser
  decision and always run"). The cursor-ide-browser harness could not deliver click events (even
  a synthetic click on a fresh button in the same page did not fire its listener), so the pass ran
  in Playwright against `http://127.0.0.1:8000/workbench` served locally, no key, loopback.
  Results: `/v1/health` ok (40,060 claims, policy search on, 1,913 chunks). Flag queue loads 618
  flags, 50 shown, "Load next page" present. Claim C0000024 dossier renders claim, lines, flags,
  and all 6 checks with limits and the not-a-determination notice. Provider P0188 shows specialty,
  peer group (32 orthopedics peers, elevated 2) and intensity metrics; member M001703 lists 13
  claims. Policy search for "evaluation and management visit level documentation" returns cited
  CMS passages with chunk id, retrieval date and sha256, labelled untrusted source text.
  Keyboard: first Tab is the skip link; Enter moves focus to `<main tabindex="-1">`;
  `:focus-visible` outline 3px with 2px offset; `aria-current` tracks the active view; live
  regions on health and status. Contrast: body 15.6:1, muted 5.6:1. Error path: claim C9999999
  shows a `role="alert"` "Not found: No record with that id", no crash. Only console error in the
  pass was `favicon.ico` 404; fixed with an inline data-URI icon in `index.html`. KF-052 closed.
  No provider call, no spend.
- Name checks for `claims-copilot` (read-only public research): PyPI `claims-copilot` and
  `claims_copilot` return 404 (free); npm `claims-copilot` 404 (free). GitHub name search finds
  66 matches, at least 10 exact-name repos (all 0-1 stars), including `miravena/claims-copilot`
  ("helps people appeal health-insurance claim denials") and `zenmem-open/claims-copilot`
  (claims resolution advocate). USPTO: no live registration for "CLAIMS COPILOT" found; Office
  Ally's "CLAIM COPILOT" application (serial 98002799, filed 2023-05-18, classes 35/38, medical
  claim management) is dead (status 2024-02-22), but Office Ally still markets "Claim Copilot"
  for its clearinghouse, DENmaar markets "Claims Copilot" for behavioral-health billing, and Aon
  and ICICI Lombard use "Claims Copilot" for claims products. Domains: `claims-copilot.com`,
  `claims-copilot.ai` and `claims-copilot.io` show no A/NS records (appear unregistered);
  `claimscopilot.com` and `claimscopilot.ai` are registered (parked). Conclusion recorded in
  ROADMAP: the name is crowded in exactly this space; keep-vs-rename returns to the owner.
  Nothing published, no remote added.
- Container: still no runtime and no Homebrew (`brew`, `colima`, `docker`, `podman` all absent).
  KF-053 stays open; installing Homebrew (sudo) remains an owner gate.

## 2026-11-03 (rename): ClaimSignal

- The owner chose rename over keep, chose Homebrew installation for the container path, and
  picked **ClaimSignal** from three availability-checked candidates (PrepayLens recommended,
  FlagFolio, ClaimSignal; ClaimCanvas was dropped during checking: Guidewire owns a "Guidewire
  ClaimCanvas" mark and a consumer ClaimCanvas tool exists). ClaimSignal checks: PyPI
  `claimsignal`/`claim-signal` free, `claimsignal.com` shows no A/NS records, claimsignal.io is
  an unrelated live product (mass-arbitration claimant proof) — caveat shown to and accepted by
  the owner, noted in the README.
- Renamed: `PRODUCT_NAME` = "ClaimSignal", distribution name `claimsignal` (uv.lock updated),
  `claimsignal-api` image names in deploy files, fetch user-agent, README/AGENTS/ROADMAP/
  FINAL_REPORT/rule descriptions. `docs/openapi.json` regenerated ("ClaimSignal API").
  Unchanged: Python package `claims_copilot`, env vars, historical records. No spend.
- Container: waiting on the owner's Homebrew install (sudo, owner's hands), then colima + docker
  CLI, build, run, health/API checks (KF-053).

## 2026-11-03 (design): Warm workbench redesign

- Branch `design/warm-workbench`; commit `8e6c319`. Files: `api/web/index.html`,
  `style.css`, `app.js`, new `api/web/favicon.svg`, one allowlist line in `api/workbench.py`.
- Before/after checked in a real browser against a local server (127.0.0.1:8001, lexical
  policy mode): queue chip loads 50 real flag rows, claim chip opens the C0000001 dossier
  (7 result cards), policy chip returns 5 cited passages, typed hint cycles in the policy
  box and stops on focus/input. Zero console errors after the favicon fix.
- Viewports: 1440px (no page-level horizontal scroll) and 375px (page does not scroll
  sideways; tables scroll inside their rounded wrapper, 292px visible of 540px).
- Accessibility measured: contrast ink/cream 12.0:1, muted/cream 6.2:1, white/accent
  6.9:1, warning 6.3:1; `prefers-reduced-motion: reduce` disables animation and the
  typed hint; `:focus-visible` outline verified solid. Palette: cream #FAF6EF, panel
  #FFFDF9, sky #BDD9F0, ink #3E2E23, accent #1F5C99.
- `tests/test_api_workbench.py` 11 passed during the work; the commit's pre-commit run
  (gitleaks, ruff, mypy, full pytest) passed without `--no-verify`. No paid calls; $0.

## 2026-11-03 (evening): Session close-out — rename and warm redesign current; two owner gates open

- State: branch `design/warm-workbench`, HEAD `ec52790`, clean tree. This sitting's commits:
  `7130c24` (six owner decisions + MIT LICENSE), `8a90a9f` already prior (owner re-review sheet),
  `6c8c28f` (real-browser pass, KF-052 closed), `35bb0b7` (rename claims-copilot -> ClaimSignal),
  `8e6c319` (warm workbench redesign), `ec52790` (redesign decision + browser verification).
- Current web design (most updated, captured this sitting): the warm redesign in
  `src/claims_copilot/api/web/` — cream #FAF6EF background, panel #FFFDF9, sky #BDD9F0, ink
  #3E2E23, accent #1F5C99; signal-and-leaf SVG mark (also `favicon.svg`, same-origin); pill view
  nav; rounded cards; sky-tinted policy quotes; example chips and a typed policy hint that run
  the real forms; motion only under `prefers-reduced-motion: no-preference`.
- Re-verified this sitting in a real browser (Playwright, local 127.0.0.1:8000, lexical mode):
  title "ClaimSignal evidence workbench", flag queue loads with the redesign tokens applied,
  C0000024 dossier opens from the queue, zero console errors (favicon fix holds). Screenshots
  shown to the owner in chat (flag queue and claim dossier); not committed (no image assets
  are tracked in this repo).
- Verification at close: 694 tests, ruff, format, mypy, and pre-commit all green at the rename
  commit; workbench redesign commit also passed pre-commit without `--no-verify`. Spend
  unchanged: $2.9890 of $50; no paid calls in this sitting.
- Still open, both owner gates: (1) the KF-041 label sheet is 0 of 36 — re-checked this sitting,
  untouched; ingest + calibration rerun follow immediately once the owner completes it.
  (2) Homebrew not yet installed (`brew`, `colima`, `docker` all absent), so KF-053 container
  verification waits on the owner's sudo install. Nothing pushed or published; no remote.

## 2026-11-07: Stage 1 blind model re-review ingested

- Package `eval/labeling/blind_review_package/` (sha256 `7c4c52b3...`) built outside the repo copy
  at `/tmp/claimsignal_blind_review`; one fresh isolated Claude Sonnet 5.5 subagent (run
  `claude-review-2eef858c`) answered 36 of 36 prompts; response sha256 `dae50c7f...`; validated.
- Ingested with source `claude-sonnet-5-5-independent-review` (blind, model-generated, same
  family as the judge, not human). Views: original / mixed / consensus-only / consensus-retained
  base in `eval/scorecards/phase7_judge_calibration_views.json`. Results in `EVALUATION.md`;
  open item KF-060. Cursor model usage for this review is outside the project budget
  (`budget/ledger.jsonl` unchanged, no CostGuard calls).
