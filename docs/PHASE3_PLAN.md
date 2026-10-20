# Phase 3 plan: deterministic tools

Status: **proposed, awaiting owner approval and three decisions. No Phase 3 code has been
written.**

## Goal

A set of plain, tested, read-only Python tools that answer exact questions about a flagged claim
from the synthetic payer data: what the claim contains, which rule checks it trips, who else
billed like this, and how the provider compares with peers. They are the layer the Phase 5 agent
will call. They report **findings with references**; they never say "fraud", "deny", or "not
medically necessary". The investigator decides.

## What the brief asks for, and how I would read it

The brief lists "NCCI/MUE checks, duplicate detection, code validation, billing-pattern stats".

| Tool family | Tools (proposed) | Reads |
|---|---|---|
| Lookups | `get_claim`, `get_member_history`, `get_provider_profile`, `get_flags` | `payer.sqlite` |
| Edit checks | `check_bundling`, `check_unit_limits`, `check_service_dates` | claim lines and the rule tables |
| Duplicate detection | `find_duplicate_candidates` (exact, plus near matches: same member and code within a window, different provider) | claims and lines |
| Code validation | `validate_procedure_codes` (in the code table), `validate_diagnosis_codes` (real ICD-10-CM, valid on the service date) | code tables, ICD file |
| Billing patterns | `provider_intensity` (visit-level mix against same-specialty peers), `provider_peer_group` (who the peers are) | claims and lines |
| Summary | `claim_dossier` (runs the relevant tools for one claim and returns all findings, unranked) | the tools above |

Every tool returns a frozen record with: the question asked, the findings, the line and claim ids
each finding rests on, the rule or statistic used (with its parameters), and what it could not
check. An empty result says so explicitly ("checked 3 lines against 14 pairs, none apply").

## Design constraints

- **Read-only, and blind to truth.** Tools open `payer.sqlite` with SQLite's read-only mode and
  only through one repository module. A test proves they cannot reach `truth.sqlite`. Only the
  scorecard opens it.
- **Parameterised SQL only**, no string-built queries. Tool inputs are validated (id shapes) and
  untrusted: the agent will supply them in Phase 5.
- **No verdict language.** Findings are named after what the data shows ("component code billed
  with comprehensive code, no exception modifier"), never after intent. A test scans tool output
  text for banned verdict words.
- **Typed, small, pure where possible**; I/O at the edges. No network, no paid calls.
- **Peer statistics are robust and show their peer group.** From KF-014: report peer-group size and
  how many peers are themselves elevated, use median and MAD (median absolute deviation), and
  refuse to score a provider with too few visit lines instead of returning a number.

## Decisions I need from you

1. **Where the bundle and unit rules come from.**
   - A (recommended): keep the invented synthetic rules, behind a small `RulesProvider` interface
     so a real table can be swapped in later. Real NCCI and MUE tables are keyed by real CPT
     codes, and the synthetic claims deliberately use fake `X0001` codes, so real tables could not
     be applied to this dataset anyway.
   - B: you accept the CMS click-through licenses and I ingest the real PTP and MUE tables
     locally, for a lookup-only tool that takes real code pairs typed by an investigator. It adds
     real-world credibility but cannot be scored on the synthetic claims, and it needs your
     licence acceptance (AGENTS rule 8).
   - C: A now, B as an optional later add-on.
2. **How the diagnosis-code validator knows what is valid.**
   - A: only the committed 420-code subset. Works in CI, but would call every other real code
     invalid, which is wrong.
   - B (recommended): the full FY2027 code list read from the verified local raw file (hash-checked
     against the manifest). Tests use a tiny fixture; a full-list test runs only where the raw
     file exists, and says so when skipped.
   - C: commit the full code list (about 75,000 codes, codes only). Works everywhere, but publishing
     it rests on the CDC "Most of the information" wording (KF-015).
3. **How I report tool accuracy honestly.** Phase 2 showed a rule tuned after seeing the answer
   inflates the result (KF-014).
   - A (recommended): generate a second dataset with a different seed (20261020) now; set tool
     thresholds from the rule definitions on the main dataset, allow one documented tuning round
     there, and report scores only on the untouched second dataset.
   - B: one dataset, no tuning, report as measured.
   - C: one dataset with tuning allowed, labelled as tuned.

## Build order (after approval)

1. Repository module and read-only guard, with the truth-isolation test.
2. Lookups, then code validation (including the ICD loader per decision 2).
3. Edit checks and duplicate detection, each with unit tests built from tiny hand-made claims,
   written before looking at the generated data.
4. Provider statistics (median and MAD, peer-group report, minimum-volume refusal).
5. `claim_dossier` and the no-verdict-language test.
6. Scorecard (`uv run python -m claims_copilot.tools.score`): per anomaly type, claim- or
   provider-level precision and recall over true cases, and the rate at which decoys are
   wrongly raised, per decision 3. Failures go to `KNOWN_FAILURES.md`; nothing is tuned to
   make a number look good.
7. Update `DATA_MODEL.md` (any change), `EVALUATION.md`, `RESUME_METRICS.md`, `DECISIONS.md`,
   `KNOWN_FAILURES.md`, and write `docs/PHASE3_REPORT.md`.

## Budget check against `budget/caps.toml`

Phase 3 cap is **$0.00**, and the plan needs **$0.00**: tools are plain code over local SQLite, with
no provider calls. Total spent so far is $0.0166 of $50. If you later want a paid step in this
phase, the cap must be raised by you first.

## Exit criteria

- All tools have unit tests that do not touch the network or truth.
- Truth isolation and no-verdict-language tests pass.
- Scorecard run on the dataset chosen in decision 3, with per-type results and decoy false-alarm
  rates in `EVALUATION.md`, and every miss listed.
- `pytest`, `ruff`, `mypy`, and pre-commit green; docs updated; phase report written.

## Risks

- **The tools and the generator share an author again (KF-011).** Mitigated by writing tool tests
  from hand-made claims first, the held-out seed (decision 3), and reporting misses.
- **Invented rules (KF-012)** mean "NCCI/MUE checks" are synthetic in this phase. I will name them
  "bundle checks" and "unit-limit checks" in code and docs, and never imply they are CMS values.
- **Per-line unit limits** are a simplification; a per-day limit tool is out of scope unless real
  tables are chosen in decision 1.
- **Near-duplicate rules are my invention.** I will document the window and fields and measure how
  many decoys they raise.
