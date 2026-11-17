# HANDOFF

Written 2026-11-16 (about 5 PM) for an agent who has not seen the conversation; updated the same
night (about 11:30 PM) after the Ask provider-outage fix and the edge-case review hardening
landed (three more commits on `workbench-refresh`). Everything below was checked against the
repo and a live gate run that day, except where marked UNVERIFIED.
Read `AGENTS.md` too (standing rules); this file is the current status.

## 1. Goal

**ClaimSignal** (Python package `claims_copilot`) is a claims investigation and payment integrity
copilot for a health plan (payer). It helps a human investigator assemble and assess evidence for a
flagged claim. It **never** decides fraud, denial, coverage, or medical necessity; the human decides.

It is a **portfolio project** (owner framing, 2026-11-07), not a product for other users. It uses
only synthetic data and verified public sources. Three layers:

1. Retrieval (RAG) over verified public policy/coding sources (CMS, CDC/NCHS, HHS-OIG, eCFR).
2. Deterministic, tested tools over a synthetic SQLite payer dataset.
3. A bounded LLM agent that orchestrates 1 and 2 and writes a cited evidence summary. Model output
   is untrusted and validated by plain code (`ANSWER_BOUNDARY.md`).

"Done" was defined by the phased roadmap (`ROADMAP.md`). **Phases 0-11 are all closed**, the repo was
published as a PRIVATE GitHub repo on 2026-11-08, and the last piece of work (an "Ask the agent"
workbench tab, 2026-11-15/16) is finished and measured but **not yet merged or pushed** (section 3).
There is no remaining mandatory work. Section 5 lists optional follow-ups and cleanup.

## 2. Current state

### Verified today (2026-11-16)

| Check | Result |
|---|---|
| `uv run pytest -q` | Passes; 995 tests collected (README previously said 946; fixed) |
| `uv run ruff check`, `ruff format --check`, `uv run mypy` (strict, 188 files) | Clean |
| `uv run python -m claims_copilot.api.snapshot --check` | OpenAPI snapshot current |
| `uv run python -m claims_copilot.budget` | $3.71 of $50 total (p5 $0.55/8, p6 $0.75/8, p7 $2.35/12, p0 $0.02/3; the rest $0) |
| `uv run pre-commit run --all-files` (includes gitleaks) | All hooks passed, run after the handoff doc edits |

### What exists and works

- **Corpus + retrieval:** 23 verified public documents, 1,913 chunks, BM25, dense, RRF fusion, LLM
  rerank. Hybrid + rerank R@1 0.82 / R@10 0.90 on 40 dev questions; 0.81 / 0.81 on 16 held-out.
- **Synthetic data:** 4,000 members, 400 providers, 40,060 claims, 64,098 lines, five seeded anomaly
  types (30 true + 30 decoys each), ground truth in a separate store that tools never open.
- **Deterministic tools:** claim/member/provider lookups, bundling, unit limits, service-date,
  duplicates, ICD-10-CM validation, provider visit-mix vs peers. Every result now has a `status`
  (`found` / `nothing_found` / `not_scored`) plus `status_reason`.
- **Typed read-only API** (FastAPI, `docs/openapi.json` is the committed contract).
- **Bounded agent:** scope gate (blocks "is this fraud?" before any model call), evidence registry,
  validator (citations must resolve, quotes verbatim, no verdict language), OpenAI + Anthropic
  adapters, a `CostGuard` on every paid call.
- **Eval system:** pre-registered, hash-based dev/test split, scorecards, judge calibration.
- **Observability/security:** payload-free traces, hash-chained audit log, secret scrubber, API key
  for non-loopback binds (`docs/SECURITY.md`).
- **Workbench** at `/workbench` (static HTML/JS, CSP, no innerHTML) with five tabs including the new
  **"Ask the agent"** (session memory, six-part cited answer, $0.25/session and $2.00/process caps).
- **Container/AWS artifacts:** written only.

### What does NOT work or is not established (see `KNOWN_FAILURES.md`, KF-001 to KF-074)

- Two published targets were **missed**: abstention (`INSUFFICIENT_EVIDENCE` in 64% of 13
  unanswerable cases vs 80% target) and judged faithfulness (0.789 vs 0.85 target).
- Provider-intensity check: 26/30 on own data but **0/10 on an independent author's data** (KF-056,
  cause not established). v2 is experimental and failed pre-registered gate G4 (KF-061); v1 is default.
- Ask agent (test split, run once): answered 34 of 44 answerable turns; the other 8 were withheld as
  `INVALID_OUTPUT` (data-id citations KF-065, quote attached to the neighbouring chunk id KF-066,
  topic words in statements KF-067). Safe failure, but a real usability gap.
- Scope gate misses paraphrased decision asks with no decision word (KF-068); English only (KF-072).
- All test labels are model-written, not human-reviewed (KF-041, owner-accepted). Authors share a
  model family with the system's judge, so independence is by context isolation only.
- Docker/Compose/Fargate files have **never been built or run** (KF-053); no container runtime here.
- Policy search is local-only (corpus license), so a deployed container has none (KF-055).

### Git state (important)

- **Merged and pushed 2026-11-16 night (owner-approved):** `main` = `origin/main` = `e7c472e`
  on the private repo `github.com/bowierliu/claimsignal`. The ten commits that were on
  `workbench-refresh` fast-forwarded in: `cc4b4a5` status field, `ffe87b7` minimal case-file
  look, `09f7d57` Ask tab (hardened after an adversarial review), `710bc0f`, `759bd22` small UI
  fixes, `8eb6f17` Ask layout + evidence-card polish + claim re-scoping, `4735a94`
  provider-failure framing (after the live Anthropic outage), `02976bf` edge-case hardening
  (claim-id regex boundaries, busy-session reset race, honest failed-run cost line), `14b2f68`
  this handoff's refresh, `e7c472e` the owner's decisions (no in-run retry — KF-073 closed;
  keep scope-plus-note on the two-claims ambiguity).
- Branch `workbench-refresh` is checked out and even with `main`; it can be deleted or kept.
  Local branch `design/warm-workbench` (`5c4e674`) is kept, not deleted.
- **Untracked only:** `docs/demo/INTERVIEW_DEMO.md`, `docs/demo/ask.py`, `docs/img/` (the work
  tree is otherwise clean; the spend ledger is committed).

## 3. Key decisions (and what was rejected)

Full tables with options: `DECISIONS.md`. The ones a new agent is most likely to re-litigate:

| Topic | Chosen | Rejected, and why |
|---|---|---|
| Retrieval | Hybrid (BM25 + dense, RRF) + LLM rerank of top 20, opt-in; BM25 default and fallback | BM25 alone (R@10 0.44 held-out), dense alone, and hybrid without rerank (rerank did nearly all the work). Contextual chunk descriptions: added nothing once rerank was in; not adopted |
| Ask-path retrieval | V3 hybrid+rerank with a two-tier relevance floor (withhold all hits unless best cos >= 0.51, then show >= 0.40) | LLM query rewrite (V7) and a plain 0.51 cut; floor 0.40 is post hoc, accepted cost: about 8% of answerable questions end as "not enough evidence" |
| Trust model | Model output untrusted; deterministic validator; failed output shown as invalid, never as an answer | Relaxing the verdict-word rule for policy-attributed sentences: needs the owner, not done |
| Ask memory | Server-side, in memory, last 8 turns as untrusted context, 30 min TTL; prior-turn text can never become a citation | Carrying the evidence registry across turns; no memory (owner rejected) |
| Ask prompt | `agent_v2` for Ask only; Phase 7 sealed runs keep `agent_v1` | Editing prompts after test-split failures: **never tune on the test split**; failures are recorded (KF-065..067) and stop |
| Ask surface | POST routes in `api/workbench.py`, outside `docs/openapi.json`; exact route allowlist in tests | New `/v1` route (would change the read-only contract); weakening the "GET only" tests |
| Not-scored vs nothing-found | `status` field on every tool result, derived from `status_reason` | Parsing the prose `limits` in the browser |
| Workbench look | Minimal case-file (owner) | The earlier warm/rounded look (branch `design/warm-workbench`) |
| Provider intensity | v1 default; v2 stays experimental | Shipping v2 after it failed registered gate G4; owner said no further v2 work |
| Labels | Model-drafted, owner accepted the human-review gap | Waiting for a human review sheet (still exists in `eval/labeling/`) |
| Name / visibility | ClaimSignal; PRIVATE repo; MIT | `claims-copilot` (trademark/GitHub collisions); public (owner reversed it) |
| Cost | Cheap models, recorded fixtures, `CostGuard`, caps never edited | Direct provider SDK calls; editing `budget/caps.toml` |
| Container | Files written, nothing installed or built | Installing a container runtime |

Process rules that shape every change: no source cited from memory (manifest only), CPT descriptors
never included, failures recorded in `KNOWN_FAILURES.md` rather than "fixed" by editing tests or gold
sets, and an open decision gets 2-3 options with a recommendation via the question tool.

## 4. File map

Top level:

| Path | Responsibility |
|---|---|
| `AGENTS.md` | Standing rules and command list (read first) |
| `HANDOFF.md` | This status file |
| `README.md` | Human summary and the results table |
| `ANSWER_BOUNDARY.md` | What the agent may and may not say; the validator rules |
| `DECISIONS.md` / `SESSION_LOG.md` | Why things are the way they are / dated facts. Log every decision and fact |
| `KNOWN_FAILURES.md` | KF-001..072. Open problems stay visible |
| `EVALUATION.md` / `RESUME_METRICS.md` | Method and numbers / only measured numbers with commit |
| `DATA_MODEL.md` / `ROADMAP.md` | Synthetic schema / phases and follow-ups |
| `pyproject.toml`, `uv.lock`, `.python-version` | Python 3.12 via uv; strict mypy, ruff (100 cols), pytest |
| `Dockerfile`, `deploy/` | Container, compose, ECS task: written, never built (KF-053) |
| `.github/workflows/ci.yml`, `.pre-commit-config.yaml` | CI and pre-commit (gitleaks, ruff, mypy) |
| `.cursor/` | Rules (`security`, `cost`, `provenance`, `python-style`, `testing`), skills, subagents, secret-blocking hook |
| `.claude/skills/claimsignal-*` | UI design/workflow skills (untracked) |

`src/claims_copilot/`:

| Package | Responsibility |
|---|---|
| `project.py`, `secrets.py` | `PRODUCT_NAME` (only place the name lives); `has_secret` (non-empty test only) |
| `budget/` | `CostGuard`, caps, ledger. All paid calls go through it |
| `sources/`, `ingest/` | Catalog/fetch/verify/manifest; extraction, CPT redaction, chunking |
| `retrieval/` | BM25, dense, fusion, rerank, rewrite, relevance floor, eval harness |
| `synth/` | Synthetic payer data generator, anomalies, stores |
| `tools/` | Deterministic read-only tools; `score.py` is the only module that opens ground truth |
| `api/` | FastAPI app; `api/web/` and `api/workbench.py` serve `/workbench` (not in OpenAPI) |
| `agent/` | `scope.py` gate, `evidence.py`, `answer.py` + validator, `loop.py`, `ask.py`/`ask_search.py`/`ask_setup.py`/`session.py` (Ask), providers, `smoke.py` |
| `evals/` | Case schema, splits, metrics, runners, scorecards, calibration, independent tests |
| `obs/` | Scrubber, tracer, audit log |

Data and docs: `SOURCES/` (catalog, manifest, redactions), `eval/` (gold sets, Ask cases, labels,
scorecards, independent fixtures), `prompts/` (versioned runtime prompts: `agent_v1`, `agent_v2`,
`judge_v1`, `rerank_v1`, `contextualize_v1`, `query_rewrite_v1`), `budget/` (`caps.toml` owner-only,
`prices.toml`, `ledger.jsonl`), `data/` (gitignored, local: raw, text, chunks, index, synth, runs),
`docs/` (`ARCHITECTURE.md`, `SECURITY.md`, `DEPLOYMENT.md`, `FINAL_REPORT.md`, phase plans/reports,
`openapi.json`, `demo/` interview guide and `ask.py`, `img/`), `tests/` (80 files, no network, no
spend).

## 5. Next steps (ordered)

Nothing here is required by the roadmap; items 1-4 are housekeeping and need owner input where noted.

1. ~~Decide the branch~~ — done 2026-11-16 night: merged to `main` and pushed (private repo,
   fast-forward, `e7c472e`). Remaining: whether to keep or delete `workbench-refresh`, and the
   untracked `docs/demo/` + `docs/img/` files (see open question 2).
2. **Fix stale docs:** `docs/demo/INTERVIEW_DEMO.md` says 770 tests and "four views" (now 987 tests
   and five tabs); `ROADMAP.md` has no Ask entry until this handoff added one; the README test count
   was corrected in this handoff. Re-check any other count you cite.
3. **Stale local servers:** port 8000 still runs pre-re-scoping code (its Ask answers come back
   with the session claim unset) and port 8001 has no Ask routes; both predate 2026-11-16 night.
   Port 8002 is held by an Ask-enabled process (PID 74395) of unknown provenance — not started in
   the fix session; ask the owner before touching it. Check with `lsof -i :8000` and ask before
   killing anything.
4. **Refresh `RESUME_METRICS.md`** only with measured numbers and the commit hash (the Ask numbers
   in the README table come from `EVALUATION.md`; confirm they are recorded there).
5. Optional quality work, each needing a pre-registration or owner gate because the test split is
   spent: reduce `INVALID_OUTPUT` on Ask (KF-065..067) with a new prompt version evaluated on a
   fresh split; improve abstention (64% vs 80%) and faithfulness (0.789 vs 0.85); investigate the
   provider-intensity 0/10 failure (KF-056); multilingual scope gate (KF-072).
6. Optional, owner-gated: human review of labels (owner said not needed); building the container
   (owner said install nothing).

## 6. Open questions / blockers (need the owner)

1. **Merge and push** `workbench-refresh` to `main` / GitHub? (Not pushed; owner's call.)
2. **`docs/demo/INTERVIEW_DEMO.md` names a specific prospective employer and role in its title.**
   The repo rules forbid employer-specific schemas/rules/data; a name in a demo guide is not clearly
   that, but it is the owner's call whether it belongs in a repo (even a private one). It is
   untracked and I did not edit it.
3. Scan of docs/data for employer-specific terms: the assistant scan was done 2026-10-20; the
   owner still has to read it once (open item in `ROADMAP.md`).
4. Whether to spend on any new eval (each run states estimated cost first; spend is $3.71 of $50).
5. Human review of labels remains an accepted gap (KF-041); no action unless the owner reverses it.
6. ~~KF-073 in-run retry~~ — decided 2026-11-16 night: **no automatic retry** (KF-073 closed).
7. ~~Two-claims ambiguity~~ — decided 2026-11-16 night: **keep the field/session claim with the
   plain-words note** (DECISIONS.md 2026-11-16 late night).

## 7. How to run / test

Setup (Python 3.12, `uv` required):

```bash
uv sync
cp .env.example .env     # fill keys locally; .env is gitignored. Never print or commit keys.
```

Keys: an OpenAI key (embeddings, hybrid search, rerank) and an Anthropic key (default Ask model).
Check presence only with `claims_copilot.secrets.has_secret`. A Cursor hook blocks shell commands
containing credentials.

Gates (all must be green for a change to be "done"):

```bash
uv run pytest                      # no network, no spend
uv run ruff check && uv run ruff format --check
uv run mypy
uv run python -m claims_copilot.api.snapshot --check
uv run pre-commit run --all-files  # gitleaks + the above
```

Run:

```bash
uv run python -m claims_copilot.budget                  # spend vs caps
uv run python -m claims_copilot.api                     # http://127.0.0.1:8000/docs and /workbench
uv run python -m claims_copilot.api --policy-mode hybrid
uv run python -m claims_copilot.api --ask               # enables Ask (paid; $0.25/session)
uv run python docs/demo/ask.py --claim C0000493 "Is claim C0000493 fraudulent? Yes or no."  # free: blocked pre-model
```

Evals and paid steps are dry runs unless `--confirm` is passed (see the command list in
`AGENTS.md`). State the estimated cost to the owner before any `--confirm`.

Environment notes:

- The sandbox segfaults on numpy matrix-vector products (`@`, exit 139; `einsum` works). Run the
  retrieval and eval harnesses outside the sandbox.
- `data/` is gitignored and local. If `data/synth/payer.sqlite`, `data/chunks/` or `data/index/` is
  missing on a fresh clone, rebuild with `claims_copilot.synth` and the fetch/ingest/chunk commands
  in `AGENTS.md`; fetching needs network and the corpus is license-restricted, so it stays local.
  UNVERIFIED: a from-scratch rebuild was not re-run in this session.
- Never run a `--confirm` command twice concurrently (it double-spent and corrupted a cache once;
  `SESSION_LOG.md` 2026-11-15).
