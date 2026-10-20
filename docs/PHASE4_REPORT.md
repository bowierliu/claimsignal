# Phase 4 report: typed API

Status: **approved by the owner on 2026-10-20**, with KF-020 to KF-022 accepted and decision 1A
chosen. The `httpx2` check came back UNVERIFIED on one criterion; see `DECISIONS.md` (2026-10-20).

## 1. Executive summary

Phase 4 put the Phase 3 tools behind a small, typed, read-only HTTP service, so the Phase 5 agent,
the Phase 9 workbench, and a reviewer all use one documented contract.

- **What exists** (`src/claims_copilot/api/`): 11 `GET` routes under `/v1`: health, tool manifest,
  claim, dossier, five single checks (one parameterised route), member history, provider profile,
  intensity, peers, flag queue (cursor-paged), and BM25 policy search. Run it with
  `uv run python -m claims_copilot.api`; interactive docs at `/docs`.
- **Contract.** Response models are Pydantic and separate from the tool records, with a test that
  fails if either side gains a field the other lacks. The OpenAPI document is committed as
  `docs/openapi.json`, and a test fails if it is stale, so any change to the contract appears as a
  reviewable diff. `GET /v1/tools` lists the agent-callable operations, built from that same
  document, so arguments and descriptions have one source.
- **No verdicts.** No field is named for a conclusion (a schema walk enforces it). Analysis
  responses carry a fixed notice. The word scan ran over every flagged dossier on generated data
  in tests and, once, over all 618 flagged dossiers and 400 provider results on the real default
  dataset: 0 matches.
- **Truth isolation.** The API never imports the scorecard or mentions truth tables; the service
  answers every route when its directory holds only `payer.sqlite`; and opening the truth file is
  refused.
- **Safe errors.** Bad input returns 404 or 422 with a fixed-shape body that names the parameter
  and never repeats its value; unexpected errors return a generic 500. Tested with SQL text,
  500-character ids, Unicode digits, fullwidth letters, path traversal, and encoded newlines.
- **Policy search** (your choice 1B) returns cited chunks, each with its source, pages, and the
  manifest URL and hash, labelled `untrusted`. A chunk whose source is not a VERIFIED manifest row
  is never indexed.
- **Access** (your choice 3A): none; loopback by default, and another host needs `--allow-remote`.

## 2. Metrics and spend vs cap

| Item | Value |
|---|---|
| Tests | 298 passing (209 before; 86 API tests, 3 tool tests) |
| Quality gates | ruff, ruff format, mypy strict, gitleaks, pre-commit all green; no `--no-verify` |
| Latency | dossier p50 2.7 ms, p95 3.2 ms; claim p50 1.8 ms; intensity p50 1.7 ms; policy search p50 2.1 ms (200 requests each, loopback, sequential, one laptop; see `EVALUATION.md`) |
| Full-queue check | 618 flags paged without gap or repeat; 0 verdict-word matches in 618 dossiers and 400 provider results |
| Phase 4 spend | $0.00 against a $0.00 cap. Total $0.0166 of $50 |

Reminder: please check Cursor's own usage yourself; agents cannot see it.

## 3. Failures and open risks

- **KF-020 (new).** No authentication, rate limiting, or audit log. Loopback by default, but anyone
  who can reach the port reads all synthetic data. By your decision 3A; Phase 8 and Phase 10.
- **KF-021 (new).** Policy search is lexical: recall@10 0.80 overall, 0.25 on paraphrases. Phase 6.
- **KF-022 (new).** Starlette's `TestClient` deprecates plain `httpx` in favour of `httpx2`, which I
  did not add because I have not verified that package. One warning is filtered. See decision below.
- **Not production-ready.** Nothing here is a security review. `/docs` loads its page assets from a
  third-party CDN in the browser; it is fine locally and should be reviewed before any exposure.
- **A claim is not a conclusion.** The tools still reflect KF-017 to KF-019 (outlier misses, shared
  rule definitions, observation-only near-matches); the API passes those limits through in
  each result's `limits` field.
- **Measured latency is one client on one laptop**, not capacity. Policy search has a 20 ms outlier
  in each run; I did not investigate it.
- **Retrieved text is untrusted.** The API labels it, but the Phase 5 boundary must also treat it
  as data, not instructions.

## 4. Decisions needed

1. **`httpx2` (KF-022).**
   - A (recommended): have the `source-verifier` subagent check the package (publisher, release
     history, hash) and adopt it only if it verifies, then drop the warning filter.
   - B: keep plain `httpx` and the filter until Starlette removes support.
2. **Approve Phase 4 as built**, including KF-020 to KF-022, so I can propose the Phase 5 plan
   (bounded agent). I will not start Phase 5 before you approve that plan.

Changes from the approved plan are listed in `DECISIONS.md` (2026-10-19, Phase 4 build decisions):
manifest built from OpenAPI, notice also on health and manifest, identical-bytes test limited to
success responses, snapshot generated without data.

## 5. Teach me

1. **Why response models are separate from the tool records.** A web model is a published promise;
   an internal dataclass is not. Keeping both with a drift test lets the tools change without
   silently changing the contract.
2. **A contract as a tested file.** What `docs/openapi.json` is, why a test compares it with the
   live schema, and how the same document becomes tool definitions for an LLM agent.
3. **Read-only connection per request.** Why SQLite connections should not cross threads, and what
   the guard that refuses truth-like tables checks on every open.

Please confirm you understand these, or use `/teach <concept>`, before I propose Phase 5.
