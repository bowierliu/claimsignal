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
