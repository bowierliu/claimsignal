# Phase 2 plan: synthetic payer data model

Status: **approved by the owner on 2026-10-19 and built.** Results and deviations from this plan
are in `docs/PHASE2_REPORT.md`.

Decisions made by the owner on 2026-10-19:
persistence = **SQLite**; diagnosis codes = **real ICD-10-CM** (changed from my recommendation, see
the added steps below); scope = the defaults.

## Goal

A reproducible synthetic payer dataset that the Phase 3 tools and the Phase 5 agent can be scored
against. Every seeded problem has recorded ground truth, and every benign look-alike ("decoy") is
labelled too, so false positives are measurable. Everything is synthetic: no real members,
providers, claims, codes, or employer-specific shapes (hard rules 1 and 3).

## Scope

**In:**

- Entities: `member`, `provider`, `procedure_code` (synthetic code table), `claim`, `claim_line`,
  `flag`.
- Synthetic rule tables the tools will consult: `bundle_pair` (pairs that should not be billed
  together unless a modifier applies) and `unit_limit` (max units per code per day). These are
  invented and labelled synthetic. They are not real NCCI or MUE values, which are gated (see the
  Phase 0 decisions) and stay out of scope until the owner decides in Phase 3.
- A seeded, deterministic generator for clean baseline claims.
- Anomaly injectors that write `anomaly_truth` records (type, claim and line ids, why).
- Decoys: legitimate cases that look like anomalies (for example a repeated service on different
  dates, or a bundled pair with a valid modifier).
- Persistence behind a small repository interface (decision 1).
- Validators and tests; a small committed fixture; `DATA_MODEL.md` filled in.

**Out (later phases):** the detection tools themselves (Phase 3), any LLM-generated data, the API
(Phase 4), real code sets or real rule tables.

## Proposed entities (minimal; refined while building)

| Entity | Key fields (all synthetic) |
|---|---|
| `member` | `member_id` (`M000001`), `age_band`, `sex`, `plan_type`, `region` (coarse). No names, birth dates, addresses |
| `provider` | `provider_id` (`P0001`), `specialty` (synthetic category), `region`, `group_id` |
| `procedure_code` | `code` (`X0001` style), `code_system` (`SYNTH`), `category`, `typical_units`, `typical_charge` |
| `claim` | `claim_id`, `member_id`, `billing_provider_id`, `rendering_provider_id`, `service_from`, `service_to`, `place_of_service` (synthetic), `total_billed` (`Decimal`) |
| `claim_line` | `line_id`, `claim_id`, `line_no`, `code`, `modifiers`, `units`, `billed_amount`, `service_date` |
| `bundle_pair` / `unit_limit` | the synthetic rule tables above |
| `flag` | `flag_id`, `claim_id`, `source` (`synthetic_screen`), `reason`; a mix of true and false alarms, because investigators receive both |
| `anomaly_truth` | `anomaly_id`, `type`, `claim_ids`, `line_ids`, `explanation`, `is_decoy`. Never visible to tools or the agent; used only by evaluations |

## Proposed anomaly types (aligned with the Phase 3 tool list)

1. **Duplicate claim**: same member, provider, date, and code billed twice.
2. **Unbundling**: a pair in `bundle_pair` billed together without the allowed modifier.
3. **Excess units**: units above the `unit_limit` for a code and day.
4. **Intensity outlier**: a provider whose share of the highest-intensity synthetic code is far above
   peers of the same specialty (needs a billing-pattern statistic, not a single-claim rule).
5. **Date anomaly**: lines dated outside the claim's service window.

Decoys: repeat services on different dates; bundled pair with a valid modifier; high units that
are still within the limit; a provider who is high but within the peer spread.

## Scale and reproducibility

- Default size: 2,000 members, 150 providers, about 20,000 claims (about 35,000 lines), one
  12-month window. At least 30 injected instances per anomaly type and at least 30 decoys per type.
  Flags cover the anomalies plus a similar number of false alarms.
- A tiny fixture (about 200 claims) is committed for tests. The full dataset is regenerated from a
  seed (`random.Random(seed)`, stdlib only) and is not committed.
- Same seed gives byte-identical output; the dataset hash is recorded in `SESSION_LOG.md`.

## Decisions I need from you

### 1. Persistence (owner chose A, SQLite)

| Option | For | Against |
|---|---|---|
| **A. SQLite (recommended)** | Standard library, one file, real SQL for the Phase 3 aggregations (peer comparisons, duplicate detection), trivial to ship in a container or CI, and the FastAPI layer in Phase 4 can read it directly | Not what a production payer runs; weak for concurrent writes (we are read-mostly) |
| B. Parquet/CSV files + DuckDB | Excellent for analytics and large scans | New dependency; awkward for the API's per-claim lookups; less familiar to reviewers |
| C. PostgreSQL | Closest to production; strong for the later deployment story | Needs a server or Docker for development and CI; heavy for read-mostly synthetic data that can be regenerated from a seed |

Because the data regenerates from a seed, storage is effectively a cache, which favours A. A thin
repository interface keeps a later move to Postgres cheap.

### 2. Diagnosis codes (owner chose option B, real ICD-10-CM)

| Option | Notes |
|---|---|
| **A. Fake codes now, add a `code_system` field (recommended)** | No new sources to fetch and verify in Phase 2; real ICD-10-CM can be added later without a schema change |
| B. Real ICD-10-CM codes | The CDC/NCHS files are public domain, but need fetch, terms check, and manifest entries now; adds realism for the code-validation tool and retrieval links |
| C. No diagnosis codes in Phase 2 | Simplest; the code-validation tool would have less to check |

### 3. Anomaly set and scale (owner approved the defaults)

Approve the five types and decoys and the default scale above, or change them. Default I will use
unless you object: IDs and coarse attributes only (no names or birth dates), a single 12-month
window, and seed `20261019`.

## Budget check (`budget/caps.toml`)

- Phase 2 cap: **$1.00**. Planned paid calls: **none**, so the estimate is **$0.00**. Generation
  is plain seeded code; using an LLM would break reproducibility and add cost.
- Spend so far: $0.0166 of the $50 total (Phase 0 only). Phase caps sum to $40 plus a $10
  reserve, which matches the $50 total.
- No `caps.toml` change is requested. If a paid call turns out to be needed, I will stop and ask.

## What I will build first (after you approve)

0. **Source step for ICD-10-CM (new, because of decision 2).** Use the `source-verifier` agent to
   fetch the CDC/NCHS ICD-10-CM code file from the official site, read its terms, and record URL,
   retrieval date, sha256, and terms in `SOURCES/manifest.jsonl`. If the terms cannot be read, mark
   it UNVERIFIED and ask you. Never from memory. The diagnosis code table is then drawn from that
   file: a bounded subset of a few hundred codes, chosen for the claim categories. Procedure codes
   stay fake, so diagnosis-to-procedure pairings are not clinically meaningful; this is documented
   in `KNOWN_FAILURES.md`. ICD-10-CM descriptors are not AMA-copyrighted, but I will confirm that
   from the fetched terms before storing any descriptor.
1. Frozen dataclasses for the entities, the synthetic code table, and the two rule tables, with
   tests that no procedure code looks like a real procedure code (no 5-digit numeric, no `[0-9]{4}[FTU]`).
2. The clean baseline generator, deterministic by seed, with referential-integrity tests.
3. The anomaly injectors and decoys with `anomaly_truth`.
4. The persistence adapter chosen in decision 1.
5. An independent reference checker in the tests that re-derives each anomaly from the data
   (this becomes the seed of the Phase 3 tools), plus the committed fixture.
6. `DATA_MODEL.md`, `EVALUATION.md` notes, `KNOWN_FAILURES.md` entries, and the Phase 2 report.

## Exit criteria (all measured)

- Same seed produces an identical dataset hash on two runs.
- 100% referential integrity; no real procedure-code patterns; no PII-like fields; every diagnosis
  code present in the verified ICD-10-CM file recorded in the manifest.
- At least 30 seeded instances and 30 decoys per anomaly type, counted from `anomaly_truth`.
- The reference checker recovers 100% of seeded anomalies and flags 0 decoys.
- `ruff`, `mypy`, `pytest`, and `pre-commit` all green; spend still within the $1 cap.

## Risks to keep visible

- **Circularity:** I write both the generator and the checker, so passing proves consistency, not
  realism. Decoys, an independent checker, and disclosure in `KNOWN_FAILURES.md` limit this.
- **Synthetic rules are not real rules.** Results on them do not show performance on real NCCI or
  MUE tables.
- **Realism of billing patterns is limited.** The intensity outlier uses a simple distribution.
