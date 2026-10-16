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
