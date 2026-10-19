# Data model

Status: **built in Phase 2** (code in `src/claims_copilot/synth/`). Everything here is synthetic
except the diagnosis codes, which are real ICD-10-CM codes from a verified public source.

## How to generate

```bash
uv run python -m claims_copilot.synth            # default dataset -> data/synth/ (gitignored)
uv run python -m claims_copilot.synth --small    # test-sized
uv run python -m claims_copilot.synth.icd_subset # rebuild the diagnosis subset (needs the raw zip)
```

A `(seed, config)` pair fully determines the data. The default seed is `20261019`. Two separate
processes produced byte-identical SQLite files. The expected counts and hashes of the default
dataset are recorded in `eval/synthetic_dataset.json`, and a test regenerates and compares.

## Two stores, on purpose

| File | Who opens it | Contents |
|---|---|---|
| `payer.sqlite` | Tools and the agent | Members, providers, claims, lines, flags, code and rule tables |
| `truth.sqlite` | Evaluations only | The seeded ground truth (`anomaly_truth` and its claim and line links) |

The tools' database contains no truth table and no column named `anomaly`, `decoy`, or `variant`;
a test checks this. A flag's screen code names the check that fired, not the verdict: decoys fire
the same screens, and 200 clean claims are flagged at random.

## Entities (`payer.sqlite`)

| Table | Fields | Notes |
|---|---|---|
| `member` | `member_id`, `age_band`, `sex`, `plan_type`, `region` | Coarse attributes only. No names, no dates of birth, no addresses |
| `provider` | `provider_id`, `specialty`, `region`, `group_id` | One id per provider (billing and rendering are not separated) |
| `procedure_code` | `code`, `code_system`, `category`, `family`, `level`, `typical_charge` | 37 fake codes `X0001` to `X0045`, no descriptors. `family = VISIT` with levels 1 to 3 for `X0001` to `X0003` |
| `diagnosis_code` | `code`, `code_system` | 420 real ICD-10-CM FY2027 codes, codes only, no descriptors |
| `bundle_pair` | `comprehensive_code`, `component_code`, `exception_modifier` | 14 invented rules (not NCCI) |
| `unit_limit` | `code`, `max_units` | Invented, per line (not MUE, which is per day) |
| `claim` | `claim_id`, `member_id`, `provider_id`, `service_from`, `service_to`, `place_of_service`, `total_billed` | Diagnoses are in `claim_diagnosis` (ordered) |
| `claim_line` | `line_id`, `claim_id`, `line_no`, `code`, `units`, `billed_amount`, `service_date`, `dx_pointer` | Modifiers are in `line_modifier` (ordered). `dx_pointer` is a 1-based index into the claim's diagnoses |
| `flag` | `flag_id`, `claim_id`, `screen_code`, `screen_text` | The investigator's queue: `SCR01` to `SCR05` |

Money is exact decimal text. Dates are ISO text. Place of service uses synthetic codes `PS1` to
`PS3`. Synthetic modifiers: `M1` lifts a bundle rule; `M2` and `M3` carry no rule and appear on
about 5% of baseline lines so modifiers are not a signal by themselves.

## Ground truth (`truth.sqlite`)

`anomaly_truth`: `anomaly_id`, `anomaly_type`, `is_decoy`, `variant`, `provider_id` (provider-level
cases only), `explanation`; linked to `truth_claim` and `truth_line` (ordered).

## Anomaly types, with decoys (default: 30 anomalies and 30 decoys each)

| Type | Seeded anomaly | Decoy (looks similar, is fine) |
|---|---|---|
| `duplicate_claim` | Same member, provider, window, codes, modifiers, units billed twice | Same services on a later date; same services by a different provider |
| `unbundling` | Component code billed with its comprehensive code, same claim and date, no modifier | Same pair with the exception modifier `M1` |
| `excess_units` | Units above the code's per-line limit | Units exactly at the limit |
| `intensity_outlier` | Provider's share of the highest visit code is 0.55 to 0.75 (baseline about 0.12) | Provider at 0.25 to 0.32 (high, but inside the spread) |
| `date_anomaly` | Line dated 7 to 90 days outside the claim window | Line dated exactly on the window boundary of a multi-day claim |

A claim belongs to at most one case. Providers used for outlier cases are excluded from the
claim-level cases, so the five checks stay independent.

## Default scale

4,000 members, 400 providers, 40,060 claims (40,000 baseline plus 60 injected duplicates), 64,098
lines, 618 flags (210 on real-anomaly claims, 208 on decoy claims, 200 false alarms), 300 labelled
cases. Generation takes about 3 seconds.

Scale was raised from the approved plan (2,000 members, 150 providers, 20,000 claims) because an
intensity outlier is a provider-level case: 30 outliers and 30 decoys need hundreds of
visit-billing providers or they stop being outliers (see `DECISIONS.md`).

## Reference checker (tests only)

`tests/synth_oracle.py` re-derives all five anomaly types from plain rows and the rule tables,
sharing no logic with the generator. Tests require exact set equality with the labels: every seeded
anomaly found, and no decoy or clean claim found. Baseline data (before injection) must produce no
findings at all. This shows the labels are consistent, not that the data is realistic (KF-011).

## Constraints that still hold

- No real member, provider, or claim data, and no employer-specific schemas, fields, or rules.
- Procedure codes are obviously fake. CPT descriptors never appear. Diagnosis descriptors are not
  stored either.
- Field names follow public concepts only. Any claim about a public standard must resolve to a
  manifest entry; the bundle and unit rules here are explicitly invented.
- Claim dates are fictional and fall inside the ICD-10-CM FY2027 window (2026-10-01 to
  2027-09-30), so each diagnosis code is valid on its service date (KF-016).

## Provenance of the diagnosis codes

`SOURCES/manifest.jsonl` row `icd10cm-fy27-code-descriptions` (CDC/NCHS zip, sha256
`93e3ad60...`). `src/claims_copilot/synth/data/icd10cm_fy27_subset.txt` holds a seeded sample of 20
codes per chapter letter (A to T and Z) in codes-only form, with the source hash in its header. The
builder refuses to run if the raw file's hash differs from the manifest. Codes whose second
character is not a digit (18 `QA` codes) are not sampled (KF-015).
