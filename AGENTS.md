# AGENTS.md

Working agreement for any agent (or person) changing this repository.

## What this is

A Claims Investigation & Payment Integrity Copilot for a health plan (payer), built only on
synthetic data and verified public sources. It helps a human investigator assemble and assess
evidence for flagged claims. It NEVER decides fraud, denial, coverage, or medical necessity. The
human decides. Three layers:

1. **Retrieval (RAG)** over verified public policy and coding sources.
2. **Deterministic tools**: plain tested code for exact lookups and calculations.
3. **Bounded LLM agent** that orchestrates 1 and 2 and writes a cited evidence summary. Provider
   output is untrusted and validated deterministically (see `ANSWER_BOUNDARY.md`).

Product name: `claims-copilot` is a working name. It lives only in
`src/claims_copilot/project.py` (`PRODUCT_NAME`); never hard-code it elsewhere.

## Hard rules

1. No employer-specific schemas, fields, rules, data, or environment details anywhere. Everything
   is public or synthetic. Do not read anything outside this repository except the public sources
   being fetched. Adjacent folders in the owner's vault are off-limits.
2. No source is cited from memory. Every source is fetched with a real tool and recorded in
   `SOURCES/manifest.jsonl` (URL, retrieval date, sha256, license/terms note). Every citation in
   code, docs, or data must resolve to a manifest entry. If a source cannot be fetched, mark it
   UNVERIFIED and ask the owner. Never invent PMIDs, section numbers, or quotes.
3. CPT descriptors are AMA-copyrighted: never include them. Synthetic claims use obviously fake
   codes (X0001 style). Real documents have descriptors redacted at ingest and logged in
   `SOURCES/redactions.jsonl`. Read and record dataset terms before ingesting; ask if unclear.
   Files with third-party license terms stay local in `data/raw/` (gitignored).
4. Secrets never go into files, logs, shell history, or commit messages. Use `.env` (gitignored).
   Never print or read secret values: to check a key, test only that it is non-empty
   (`claims_copilot.secrets.has_secret`). Pre-commit runs gitleaks; a Cursor hook blocks shell
   commands containing credentials. If a git remote URL embeds a credential, do not print it;
   tell the owner.
5. Ask when unsure. At every open decision gate, present 2-3 options with a recommendation and
   wait. Use the structured question tool, not prose lists.
6. Never run destructive commands (`rm -rf`, force push, history rewrite, deleting repos) without
   the owner's explicit typed confirmation.
7. GitHub is deferred by owner decision: do not add a remote, push, or touch GitHub in a browser.
   Read-only public API calls for research (for example name-collision checks) are allowed.
8. Gated content (Medicare Coverage Database LCDs/articles, PTP and MUE tables behind
   click-through licenses) is not accepted or fetched without the owner.

## Cost discipline

Every paid API call goes through `claims_copilot.budget.CostGuard`. Never call a provider SDK or
HTTP endpoint for a paid service directly. Never edit `budget/caps.toml` (owner-approved caps).
New model prices go in `budget/prices.toml` only with a VERIFIED manifest source. Caps: $50 total,
$5 per eval run, per-phase caps in `caps.toml`. Default to recorded fixtures, small subsets,
caching, and the cheapest adequate model. Full evals only at phase gates, after stating the
estimated cost. Check spend with `uv run python -m claims_copilot.budget`. Remind the owner at
each phase gate to check Cursor's own usage (agents cannot see it).

## Commands

```bash
uv sync                                   # install
uv run pytest                             # tests (no network, no paid calls)
uv run ruff check && uv run ruff format --check
uv run mypy                               # strict
uv run pre-commit run --all-files         # gitleaks + the above
uv run python -m claims_copilot.budget    # spend vs caps
uv run python -m claims_copilot.sources.fetch [source_id ...]    # fetch + verify (network)
uv run python -m claims_copilot.ingest.extract                   # extract + redact
uv run python -m claims_copilot.ingest.chunk                     # chunk
uv run python -m claims_copilot.retrieval.dense [--confirm]      # dry run; --confirm spends
uv run python -m claims_copilot.synth [--small]                  # synthetic dataset -> data/synth/
uv run python -m claims_copilot.tools.score --data DIR           # tool accuracy vs labels (opens truth)
```

## Repository map

| Path | Purpose |
|---|---|
| `src/claims_copilot/budget/` | Cost guard, caps, ledger |
| `src/claims_copilot/sources/` | Catalog, polite HTTP client, fetch, verify, manifest |
| `src/claims_copilot/ingest/` | Extraction, CPT redaction, chunking |
| `src/claims_copilot/retrieval/` | BM25, dense retrieval, evaluation harness |
| `src/claims_copilot/synth/` | Synthetic payer data: models, generator, anomalies, SQLite stores |
| `src/claims_copilot/tools/` | Deterministic tools over `payer.sqlite` (read-only); `score.py` is the only module that opens truth |
| `SOURCES/` | `catalog.toml` (what to fetch), `manifest.jsonl` (evidence), `redactions.jsonl` |
| `eval/` | Gold sets (verbatim-quote labels), `synthetic_dataset.json` (golden summary) |
| `budget/` | `caps.toml` (owner-only), `prices.toml`, `ledger.jsonl` |
| `data/` | Local only, gitignored: `raw/`, `cache/`, `text/`, `chunks/`, `index/` |
| `docs/` | Architecture and phase reports |
| `.cursor/` | Rules, skills, subagents, hooks |

Records kept current: `README.md` (problem, design, results first), `docs/ARCHITECTURE.md`,
`DECISIONS.md`, `EVALUATION.md`, `KNOWN_FAILURES.md`, `ANSWER_BOUNDARY.md`, `DATA_MODEL.md`,
`ROADMAP.md`, `SESSION_LOG.md`, `RESUME_METRICS.md`.

## Conventions

- Python 3.12 via uv. Strict mypy, ruff (line length 100), pytest. Typed, small modules, frozen
  dataclasses for records, `pathlib`, `httpx`. Libraries do not `print`; CLIs may.
- Tests never touch the network or spend money. Use `httpx.MockTransport`, recorded fixtures, and
  fake embedders. Use obviously fake codes (`X0001`) in synthetic data.
- Failures stay visible. Never edit the corpus, gold sets, or tests to make a failing case pass;
  record it in `KNOWN_FAILURES.md` instead.
- Only measured numbers go in `RESUME_METRICS.md`, each with how it was measured and the commit.
- Runtime prompts live in `prompts/` as versioned files. A prompt change needs an eval comparison
  against the previous version, recorded in `DECISIONS.md`.

## Working method

- One phase at a time. Do not start the next phase until the owner approves the phase report
  (`/phase-report`). Report format: (1) executive summary, (2) metrics and spend vs cap,
  (3) failures and open risks, (4) decisions needed, (5) a teach-me list of 2-3 concepts. Then ask
  the owner to confirm understanding before proposing the next phase.
- Prompts: write a structured prompt (role, context, inputs, constraints, output schema, one or
  two examples, failure behavior) for subagent delegations, runtime provider prompts,
  extraction/classification prompts, and judge prompts. For file edits, test runs, and small
  refactors, just do the work.
- Delegation: use `file-scout` (read-only, cheap) when finding files, symbols, or conventions
  would take more than about 3 file reads, and do not run broad glob/grep sweeps yourself. Use
  `source-verifier` for fetching, hashing, and checking that a cited claim is supported. Use your
  strongest reasoning for architecture, design review, and safety logic; delegate bulk or
  mechanical work to cheaper subagents.
- Log every decision in `DECISIONS.md` (options, choice, why) and facts in `SESSION_LOG.md`.
- Teaching: the owner can run `/teach <concept>`; that command never modifies code.

## Definition of done (every change)

`uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, and
`uv run pre-commit run --all-files` are all green; docs and `DECISIONS.md` are updated; commits
pass pre-commit without `--no-verify`.
