# Architecture

Status key: **built** (in the repo and tested), **planned** (phase noted). Nothing planned is
described as working.

## Principle

A human investigator decides. The system assembles and cites evidence; it never decides fraud,
denial, coverage, or medical necessity. Three layers, with the model last and least trusted.

```mermaid
flowchart LR
    subgraph Sources["Verified public sources (built)"]
        S1[CMS manuals] --- S2[OIG reports] --- S3[eCFR] --- S4[ICD-10-CM guidelines]
    end
    Sources --> F[fetch + verify + manifest]
    F --> X[extract + CPT redaction]
    X --> C[chunk]
    C --> R[(retrieval: BM25 + dense)]
    D[(synthetic payer data, Phase 2)] --> T[deterministic tools, Phase 3]
    R --> A[bounded agent, Phase 5]
    T --> A
    A --> V[answer-boundary validator, Phase 5]
    V --> U[investigator workbench, Phase 9]
```

## Layers

| Layer | Responsibility | Status |
|---|---|---|
| Source ingest | Fetch with a polite client, verify expected text and terms, hash, record in `SOURCES/manifest.jsonl`; extract page-anchored text; redact CPT descriptors and log by hash; chunk with section headings and page ranges | built (Phase 0) |
| Retrieval | BM25 (pure Python) and dense (`text-embedding-3-small`, cosine over a flat numpy index); gold-set evaluation by verbatim quote | built (Phase 0); hybrid, reranking, contextual embeddings planned (Phase 6) |
| Cost guard | Every paid call is priced, capped, refused if over a cap, and ledgered in `budget/ledger.jsonl` | built (bootstrap) |
| Synthetic data | Members, providers, claims, lines, flags with seeded anomalies and known ground truth, fake codes only | planned (Phase 2) |
| Deterministic tools | Edit checks, duplicate detection, code validation, billing-pattern statistics | planned (Phase 3) |
| API | FastAPI + Pydantic | planned (Phase 4) |
| Bounded agent | Tool calling with step limits and state, one swappable provider adapter (Claude and OpenAI) | planned (Phase 5) |
| Answer boundary | Deterministic validation of provider output (`ANSWER_BOUNDARY.md`) | planned (Phase 5) |
| Observability and security | Tracing, audit log, PII/secret scanning, prompt-injection tests | planned (Phase 8) |
| Workbench UI | Investigator-facing evidence view | planned (Phase 9) |

## Trust boundaries

- Retrieved text, fetched web content, and provider output are untrusted data, never
  instructions.
- Citations must resolve to retrieved `chunk_id`s, and chunks resolve to a manifest entry, so
  every claim traces to a fetched, hashed source and page.
- Secrets live only in the gitignored `.env`; a Cursor hook blocks credentials in shell commands
  and gitleaks runs in pre-commit.
- Third-party source files and everything derived from them stay local and gitignored
  (`data/raw`, `cache`, `text`, `chunks`, `index`). The repository holds code, the manifest,
  hashes, and logs.

## Open decision gates

Each is presented to the owner with 2-3 options and a recommendation when its phase is reached.

| Gate | Asked in |
|---|---|
| Persistence | Phase 2 |
| API packaging | Phase 4 |
| Raw tool calling vs graph orchestration | Phase 5 |
| Vector storage (flat numpy index is the Phase 0 baseline) | Phase 6 |
| Eval and judge policy | Phase 7 |
| Observability stack | Phase 8 |
| Frontend | Phase 9 |
| Deployment target (recommend AWS-compatible) | Phase 10 |
| License | Before publishing |
