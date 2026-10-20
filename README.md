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
[`KNOWN_FAILURES.md`](KNOWN_FAILURES.md). Spend to date: about $0.017 of a $50 cap.

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
(`GET /v1/tools`), and a free lexical policy search whose every hit names its manifest source. It
keeps the same two promises as the tools: no field states a conclusion, and the ground-truth store
is never opened (tests start it with only `payer.sqlite` present). Measured on a laptop over
loopback, one request at a time: dossier p50 3.0 ms and p95 3.6 ms. It has no authentication yet
and binds to `127.0.0.1` (KF-020).

```bash
uv run python -m claims_copilot.api            # http://127.0.0.1:8000/docs
```

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
