# claims-copilot

A claims investigation and payment integrity copilot for a health plan, built only on synthetic
data and verified public sources. It helps a human investigator assemble and assess evidence for
flagged claims. It never decides fraud, denial, coverage, or medical necessity; the human decides.

The product name is a working name (`PRODUCT_NAME` in `src/claims_copilot/project.py`).

## Results so far (Phase 0: retrieval over a verified corpus)

Measured on 40 gold questions over 23 public documents (1,913 chunks). Method and caveats:
[`EVALUATION.md`](EVALUATION.md).

| Method | Recall@10 all (n=40) | Recall@10 paraphrase (n=8) | MRR@10 all |
|---|---|---|---|
| BM25 (lexical) | 0.80 | 0.25 | 0.455 |
| Dense (`text-embedding-3-small`) | 0.82 | 0.62 | 0.513 |

Neither is good enough alone (10% of questions are missed by both), which is why hybrid retrieval
and reranking are planned next. Known weaknesses are listed openly in
[`KNOWN_FAILURES.md`](KNOWN_FAILURES.md). Spend to date: see `RESUME_METRICS.md` (Phase 6 total $0.64 of a $50 cap).

## Retrieval upgrades (Phase 6)

I fixed seven pipelines and their settings before running anything, then measured them on the 40
development questions and, for the winner, on 16 fresh held-out paraphrase questions
([`EVALUATION.md`](EVALUATION.md)).

| Pipeline | R@1 dev | R@10 dev | R@1 held-out | R@10 held-out |
|---|---|---|---|---|
| BM25 | 0.33 | 0.80 | 0.25 | 0.44 |
| Dense | 0.38 | 0.82 | 0.38 | 0.69 |
| Hybrid (BM25 + dense, RRF) | 0.38 | 0.80 | 0.38 | 0.75 |
| **Hybrid + LLM rerank of the top 20** | **0.82** | **0.90** | **0.81** | **0.81** |

The reranker did nearly all the work; contextual chunk descriptions added nothing once it was in
place and were not adopted. What it misses is what fusion never surfaced (the reranker only
reorders), and it costs about $0.001 and 3.5 s per search, so the API serves it only as an opt-in
(`--policy-mode hybrid`) that falls back to free BM25 and says so. Small, assistant-drafted gold
sets: directional, not a precise rate (`KNOWN_FAILURES.md` KF-030 to KF-034).

## Synthetic data (Phase 2)

A reproducible synthetic payer dataset (4,000 members, 400 providers, 40,060 claims, 64,098 lines)
with five seeded anomaly types, each with 30 true cases and 30 look-alike decoys, and a separate
ground-truth store that tools never open. An independent reference checker recovers every seeded
anomaly and flags no decoy. That shows the labels are consistent, not that the data is realistic
([`DATA_MODEL.md`](DATA_MODEL.md), [`KNOWN_FAILURES.md`](KNOWN_FAILURES.md) KF-011 to KF-016).

## Deterministic tools (Phase 3)

Read-only tools over the payer data: claim, member and provider lookups; bundle, unit-limit and
service-date checks; duplicate candidates; code validation against the FY2027 ICD-10-CM list;
and a provider visit-mix comparison with same-specialty peers. They return findings with the row
ids they rest on, never a verdict. On a second dataset generated after the code was frozen, the
four claim-level checks found 150 of 150 seeded cases and raised no decoy, and the provider check
found 26 of 30. The 100% reflects shared rule definitions, not real-world accuracy, and the four
misses come from peer-group contamination ([`EVALUATION.md`](EVALUATION.md), KF-017 and KF-018).

## Typed API (Phase 4)

A read-only FastAPI service exposes the tools over HTTP with typed Pydantic responses, a committed
OpenAPI contract ([`docs/openapi.json`](docs/openapi.json)), a tool manifest for the future agent
(`GET /v1/tools`), and a policy search whose every hit names its manifest source (free lexical by default; opt-in hybrid + rerank from Phase 6). It
keeps the same two promises as the tools: no field states a conclusion, and the ground-truth store
is never opened (tests start it with only `payer.sqlite` present). Measured on a laptop over
loopback, one request at a time: dossier p50 2.7 ms and p95 3.2 ms. It has no authentication yet
and binds to `127.0.0.1` (KF-020).

```bash
uv run python -m claims_copilot.api            # http://127.0.0.1:8000/docs
```

## Bounded agent (Phase 5)

A plain tool-calling loop lets a model call the typed API and policy search, then write a short
evidence summary. Plain code checks the result before anyone sees it: a scope gate blocks "is this
fraud?" and "should we deny it?" before any model call, every citation must resolve to something the
run actually retrieved, quotes must be verbatim, and an answer that fails is shown as invalid, not
as an answer ([`ANSWER_BOUNDARY.md`](ANSWER_BOUNDARY.md)). It runs on OpenAI and Anthropic models
behind one interface. In three live smoke runs of 28 investigations each (14 per provider, about
$0.04 per run), validated answers for the 20 claim investigations went from 7 to 17 to 20 as I
fixed a defect and relaxed three rules on the owner's decision (`KNOWN_FAILURES.md`). "Validated" means it
passed the checks, not that it is correct. This is a smoke test of 14 cases per provider, not an
evaluation: it says the loop works, not how good the answers are.

## Design

1. **Retrieval** over verified public policy and coding sources (CMS, CDC/NCHS, HHS-OIG, eCFR).
   Every source is fetched, hashed, and recorded in `SOURCES/manifest.jsonl`; every citation must
   resolve to a manifest entry. CPT descriptors are redacted at ingest.
2. **Deterministic tools** for exact lookups and calculations (built, Phase 3), over the
   synthetic payer data above.
3. **A bounded LLM agent** that orchestrates both and writes a cited evidence summary, whose
   output is validated by plain code ([`ANSWER_BOUNDARY.md`](ANSWER_BOUNDARY.md), planned).

Details and status of each layer: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Plan:
[`ROADMAP.md`](ROADMAP.md). Why things are the way they are: [`DECISIONS.md`](DECISIONS.md).
Cost control: every paid call goes through a guard that refuses calls over a cap and logs to
`budget/ledger.jsonl`.

## Development

```bash
uv sync
uv run pytest
uv run ruff check && uv run ruff format --check
uv run mypy
uv run pre-commit run --all-files
uv run python -m claims_copilot.budget   # API spend vs caps
uv run python -m claims_copilot.api       # serve the API on 127.0.0.1:8000
```

Copy `.env.example` to `.env` and fill in keys locally. Never commit `.env`. Working agreement for
contributors and agents: [`AGENTS.md`](AGENTS.md).
