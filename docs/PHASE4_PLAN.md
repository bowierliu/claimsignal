# Phase 4 plan: typed API

Status: **proposed, awaiting owner approval and three decisions. No Phase 4 code has been written
and no dependency has been added.**

## Goal

A small FastAPI + Pydantic service that exposes the Phase 3 tools as typed, read-only HTTP
endpoints, so that the Phase 5 agent (as tool definitions), the Phase 9 workbench UI, and any
reviewer can use them through one documented contract. The API adds no new analysis. It keeps
the two guarantees from Phase 3: **no verdicts** and **no access to ground truth**.

## Scope

In scope:

- An app factory `create_app(payer_path, ...)` in `src/claims_copilot/api/`, run with `uvicorn`.
- Pydantic v2 request and response models for every Phase 3 result, a uniform error model,
  an auto-generated OpenAPI document committed as a snapshot, and a machine-readable tool manifest.
- Contract, guard, and determinism tests that run in-process (no server, no network, no spend).
- A measured local latency table for the dossier endpoint on the default dataset.

Out of scope (later phases): the LLM agent and provider adapters (5), retrieval upgrades (6), the
eval system (7), tracing, audit log, authentication and rate limiting (8), UI (9), deployment (10).
Writes are out of scope entirely: every endpoint is `GET`.

## Endpoint design (all under `/v1`, all read-only)

| Method and path | Returns | Backed by |
|---|---|---|
| `GET /health` | status, dataset hash, claim count, ruleset name, whether the full ICD list is loaded | repository meta |
| `GET /tools` | tool manifest: name, plain-language description, parameter JSON schema, path | the route table |
| `GET /claims/{claim_id}` | claim, lines, modifiers, diagnoses, flags | `get_claim` |
| `GET /claims/{claim_id}/dossier` | all check results for the claim, unranked | `claim_dossier` |
| `GET /claims/{claim_id}/checks/{check}` | one `ToolResult`; `check` is one of `bundling`, `unit-limits`, `service-dates`, `duplicates`, `codes` | the five claim checks |
| `GET /members/{member_id}/history?limit=` | the member's claims, oldest first, with truncation flag | `get_member_history` |
| `GET /providers/{provider_id}` | profile and counts | `get_provider_profile` |
| `GET /providers/{provider_id}/intensity` | the visit-mix result with its peer statistics | `provider_intensity` |
| `GET /providers/{provider_id}/peers?limit=` | the peer-group report | `provider_peer_group` |
| `GET /flags?screen_code=&limit=&after=` | the flag queue, cursor-paged by `flag_id` | `get_flags` |
| `GET /policy/search?q=&k=` | only if decision 1 is B (below) | BM25 over the verified corpus |

Status codes: `200`, `404` (well-formed id, no such row), `422` (malformed input), `500` (generic).
Errors use one body shape (`type`, `title`, `status`, `detail`, `request_id`) and **never echo the
offending input** (FastAPI's default 422 body does, so the handler is replaced). The dataset hash is
returned in an `X-Dataset-Hash` header so any answer can be tied to the data it was computed on.

## Schema design

- **Response models are separate from the Phase 3 dataclasses**, with explicit converters in
  `api/schemas.py`. The tools stay free of web dependencies. A drift test fails if a dataclass
  field exists that no response model carries, or the reverse.
- Models: `Ref`, `Finding`, `ToolResult`, `ClaimRecord`, `ClaimLine`, `Dossier`, `MemberHistory`,
  `ProviderProfile`, `PeerGroupReport`, `FlagQueue`, `Health`, `ToolManifest`, `Problem`.
- Requests are path and query parameters validated against the same id patterns as
  `tools/errors.py` (one source of truth). Numbers use bounded integers; money stays a decimal string.
- Every analysis response carries a constant `notice`: "Findings describe the data. They are not
  determinations." This is for the UI and for agents reading the output.
- Responses are deterministic: the same request returns the same bytes (tested).

## How the guarantees are kept

**No verdicts**

1. No response field is named `verdict`, `decision`, `recommendation`, `risk`, `priority`, `rank`,
   or `severity`; a test walks the OpenAPI schema and fails on those names.
2. The Phase 3 verdict-word scan is re-run on live API responses for every flagged claim and every
   provider peer report on the generated data.
3. There is no combined score, and `/dossier` keeps its fixed, meaningless order.
4. `/tools` descriptions are written once, reviewed, and scanned with the same word list.

**Truth isolation**

1. The app opens only `payer.sqlite`, via the existing `Repository` (read-only, `query_only`, ATTACH
   disabled, refuses the truth file and truth-like tables or columns).
2. The API package may not import `tools/score.py`, `synth.store.load_dataset`, or contain truth
   tokens; the Phase 3 static test is extended to cover `api/`.
3. A test starts the app in a directory that contains **only** `payer.sqlite` and exercises every
   endpoint, proving the service never needs the truth file.
4. No route accepts a file path, SQL, or free-form filter; the `/flags` screen code is validated
   against `SCR\d\d`.

**Untrusted data**

- Ids are validated before any query; errors truncate and do not echo input.
- If decision 1 is B, every search hit is marked `untrusted: true`, carries `source_id`, pages and
  the manifest URL and hash it resolves to, and is returned as plain text, never as markup.

## Decisions I need from you

1. **Policy search in the API?** The brief puts retrieval in the product, and the agent will need
   citations, but retrieval is not a Phase 3 tool.
   - A: no retrieval endpoint; the Phase 5 agent calls the retrieval module directly.
   - B (recommended): a free `GET /policy/search` using the existing BM25 index (recall@10 0.80 on
     the Phase 0 gold set, but only 0.25 on the 8 paraphrase questions, so it misses reworded queries
     until Phase 6), returning cited chunks marked untrusted. Dense search is not exposed
     because each query would spend money on an embedding (cap `p4` is $0), and Phase 6 will replace
     the ranking behind the same endpoint.
   - C: include dense search through `CostGuard`; needs you to raise the `p4` cap (I will not edit
     `caps.toml`).
2. **Shape of the API surface.**
   - A (recommended): resource-style REST as tabled above, plus `GET /tools` that lists the same
     operations as tool definitions for the Phase 5 agent. Cacheable, easy for a UI, and one source
     of truth for schemas.
   - B: one uniform `POST /tools/{name}` call endpoint that mirrors how an agent invokes tools. Simpler
     for the agent, but weaker for a UI and for caching, and `POST` implies side effects.
3. **Access control for now.**
   - A (recommended): none in Phase 4; bind to `127.0.0.1` by default; data is synthetic and every
     route is read-only. Authentication, rate limits, and audit logging are Phase 8, and exposure is
     a Phase 10 decision.
   - B: a static API key from `.env` required on every request now (checked only with `has_secret`).
     Adds a secret to manage before there is anything to protect.
   - C: no auth, but bind to all interfaces so other devices can reach it. Not recommended.

## Build order (after approval)

1. Add `fastapi`, `pydantic` and `uvicorn` with `uv add`; check current docs for the versions
   installed (Context7), record the versions and licenses in `DECISIONS.md`. `httpx` is already
   present for the in-process test client.
2. `api/schemas.py`: models, converters, and the dataclass-drift test.
3. `api/app.py`: factory, startup (open the repository, load rules, build `PeerBook`, try the ICD
   list), per-request read-only connections, `X-Dataset-Hash` and request-id middleware.
4. Routes, one resource at a time, each with tests built from the Phase 3 hand-made fixtures
   before the generated data.
5. Error handlers (problem body, no input echo) and tests with hostile ids: SQL-like strings,
   500-character strings, unicode, path traversal.
6. `/tools` manifest, and the committed `docs/openapi.json` snapshot with a test that the live
   schema matches it.
7. Guard tests (no-verdict on schema and live responses, truth isolation, only-`payer.sqlite`
   start, determinism).
8. If decision 1 is B: `/policy/search` over the local chunk file with the untrusted marker and
   manifest resolution tests; the endpoint reports "index not available" when the local chunks are
   absent, and its tests use a tiny fixture index.
9. Measure latency on the default dataset (p50 and p95 for `/dossier`, `/claims/{id}`, and
   `/providers/{id}/intensity`, 200 requests each) and record it as measured, with the machine.
10. README run instructions, `docs/ARCHITECTURE.md`, `AGENTS.md` repo map and commands, and
    `docs/PHASE4_REPORT.md`.

## Budget check against `budget/caps.toml`

The Phase 4 cap is **$0.00** and the plan needs **$0.00**: no provider calls, and under option B of
decision 1 only the local BM25 index. Only option C of decision 1 would need money, and it needs you
to raise the cap first. Total spent so far is $0.0166 of $50.

## Exit criteria

- Every endpoint in the table is implemented, documented in `docs/openapi.json`, and tested
  in-process; the snapshot test passes.
- The no-verdict and truth-isolation tests pass, including the only-`payer.sqlite` start.
- Hostile-input tests pass and no error body echoes input.
- Identical requests return identical bytes.
- Latency table recorded with how it was measured.
- `pytest`, `ruff`, `mypy`, and pre-commit green; docs and `DECISIONS.md` updated; phase report
  written and no Phase 5 work started.

## Risks

- **Schema drift** between dataclasses and Pydantic models. Mitigated by the drift test and
  one-way converters.
- **SQLite and threads.** FastAPI runs sync routes in a thread pool; sharing one connection is
  unsafe. Mitigated by a read-only connection per request (cheap on a local file) and cached,
  immutable rules and peer statistics built at startup; a changed dataset needs a restart, and
  `/health` shows the hash.
- **Default error bodies leak input.** FastAPI's validation errors repeat the input; the handler
  replacement is tested.
- **Dependency churn.** FastAPI and Pydantic move quickly; versions are pinned by `uv.lock` and the
  OpenAPI snapshot will flag unintended contract changes.
- **Scope creep** into retrieval or the agent. Decision 1 fixes the boundary: only a free BM25
  search, if any.
- **A local-only API is not a security review.** Nothing here claims production readiness; that is
  Phase 8 and Phase 10.
- **Retrieved text is untrusted** and can contain instructions aimed at an agent. The API marks it
  and never interprets it; the Phase 5 boundary must treat it the same way.
