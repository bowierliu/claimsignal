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
