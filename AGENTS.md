# AGENTS.md

Minimal bootstrap version. Phase 1 expands this with conventions, rules, skills, and subagents.

## Hard rules

1. No employer-specific schemas, fields, rules, data, or environment details anywhere. Everything
   is public or synthetic. Do not read anything outside this repository except the public sources
   being fetched.
2. No source is cited from memory. Every source is fetched with a real tool and recorded in
   `SOURCES/manifest.jsonl` (URL, retrieval date, sha256, license/terms note). Every citation in
   code, docs, or data must resolve to a manifest entry. If a source cannot be fetched, mark it
   UNVERIFIED and ask the owner. Never invent PMIDs, section numbers, or quotes.
3. CPT descriptors are AMA-copyrighted: never include them. Synthetic claims use obviously fake
   codes (X0001 style). Read and record dataset terms before ingesting; ask if unclear. Files with
   third-party license terms stay local in `data/raw/` (gitignored).
4. Secrets never go into files, logs, shell history, or commit messages. Use `.env` (gitignored).
   Pre-commit runs gitleaks; a Cursor hook blocks shell commands containing credentials.
5. Ask when unsure. At every open decision gate, present 2-3 options with a recommendation and wait.
6. Never run destructive commands (rm -rf, force push, history rewrite) without the owner's
   explicit typed confirmation.

## Cost discipline

Every paid API call goes through `claims_copilot.budget.CostGuard`. Never call a provider SDK
directly. Never edit `budget/caps.toml` (owner-approved caps). New model prices go in
`budget/prices.toml` only with a VERIFIED manifest source.

## Definition of done (every change)

`uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, and
`uv run pre-commit run --all-files` are all green. Decisions are logged in `DECISIONS.md`.
