# Provider-intensity v2: pre-registration

Committed **before any v2 evaluation data was generated or viewed.** The commit that adds this file
is the timestamp. Machine-readable form: `eval/provider_intensity_v2_preregistration.json`.

**Frozen hash (sha256 of that JSON file):**
`07c903f1704775031b33a83923fb720c1d67fbbd826ac66496c463fa24934033`

Data brief given to the fixture author: `eval/intensity_v2/BRIEF_for_author.md`, sha256
`de3a52def54179f8fe81097b7e076337fd81292dff55c6d907d8d6a7b23de251`.

Changes after this commit are allowed only as a dated amendment in `DECISIONS.md`; the earlier
values stay in git history. A test pins the constants to the code and both hashes to the files, so a
silent edit fails the suite.

## Why

KF-056: on a fresh independent delivery, the v1 intensity check (modified z-score against the
peer median and MAD, cutoff 3.5) found 0 of 10 outliers, and the cause was not established. Owner
decision 2026-10-20: do not tune v1. Any fix is a separate pre-registered change on fresh data from a
new author. This is that change.

## Controls and status

- **v1** (`tools/patterns.py`, `provider_intensity`) is unchanged and stays the product default.
- **v2** (`tools/patterns_v2.py`, `provider_intensity_v2`) is additive and experimental. It is not
  wired into the API, dossier or agent.

## Algorithm (v2), per subject provider

1. Peers: same specialty, at least `MIN_VISIT_LINES` visit lines, subject excluded.
2. Abstain (explicit reason) if the subject has fewer than `MIN_VISIT_LINES` visit lines
   (`subject_below_min_volume`), the subject is unknown (`subject_not_found`), fewer than `MIN_PEERS`
   peers exist (`too_few_peers`), or the peer median high-level share is at or above
   `PEER_MEDIAN_ABSTAIN_AT` (`peer_median_at_or_above_limit`).
3. `p0` = peer median high-level share, clamped to `[P0_FLOOR, P0_CAP]`.
4. Evidence: one-sided exact binomial upper tail `P(X >= x)`, `X ~ Binomial(n, p0)`, with `n` the
   subject's visit lines and `x` its highest-level lines.
5. Multiplicity: Bonferroni over the specialty's eligible providers, `m = peers + 1`,
   `alpha_adjusted = ALPHA_FAMILY / m`.
6. Practical size: subject share minus the peers' 75th percentile (`statistics.quantiles`, n=4,
   inclusive) must be at least `MIN_GAP_ABOVE_P75`.
7. Flag only if `p_value <= alpha_adjusted` and the gap rule holds. Otherwise no flag.

## Constants (fixed now, from the statistic's definition and practice, not from any ClaimSignal label or score)

| Constant | Value | Reason |
|---|---|---|
| `MIN_VISIT_LINES` | 40 | Same volume floor as v1, so abstentions are comparable |
| `MIN_PEERS` | 20 | A 75th percentile and a Bonferroni family need a reasonable group; v1's 10 was too few |
| `ALPHA_FAMILY` | 0.05 | Conventional family-wise level |
| `P0_FLOOR`, `P0_CAP` | 0.02, 0.98 | Keep the binomial test defined when the peer median is 0 or 1 |
| `MIN_GAP_ABOVE_P75` | 0.10 | A statistically clear excess must also be a practically meaningful share gap |
| `PEER_MEDIAN_ABSTAIN_AT` | 0.50 | If most peers bill the top level, the peer baseline cannot say what is unusual |

## Hypotheses

- H1: v2 finds at least 0.80 of scorable TRUE providers in the primary specialties.
- H2: v2 recall exceeds v1 recall on the same fixture by at least 0.20 (absolute).
- H3: v2 raises at most 5% of scorable ORDINARY and DECOY providers combined (primary).
- H4: v2 raises no more ORDINARY or DECOY providers than v1 on the same fixture.

## Data requirements

A fresh fixture from an isolated author model that sees only the brief (no earlier results, earlier
independent data, detector, constants or expected outcomes): three primary specialties, at least 30
ordinary providers each (the brief asks for 45 to 70), TRUE and DECOY each at most 15% of a primary
specialty, varied volumes including very low ones, mild and strong TRUE providers, hard and easy
decoys, and a separately declared high-contamination specialty (30% to 45% TRUE) reported on its own.
The four delivered files are hashed on receipt and the hashes committed before any detector runs;
labels are read only by the scorer. The preferred author is a model from a different family; the
author actually used is recorded with the result.

## Metrics

- **Primary** (primary specialties pooled; scorable means at least 40 visit lines): recall over
  scorable TRUE providers; false-positive rate over scorable ORDINARY plus DECOY providers; false-alarm
  count (the numerator of that rate). An abstention on a scorable TRUE provider counts as a miss.
- **Secondary:** recall by specialty, severity and volume band; false-positive rate for ORDINARY only,
  DECOY only and hard DECOY only; recall over all TRUE providers including those below the volume
  floor; every abstention with its reason by label; the contamination stratum (never pooled into a
  gate); a per-provider table of both versions.
- Wilson 95% intervals on every reported rate.

## Acceptance gates (all must pass)

| Gate | Condition |
|---|---|
| G1 | v2 recall >= 0.80 |
| G2 | v2 recall - v1 recall >= 0.20 |
| G3 | v2 false-positive rate <= 0.05 |
| G4 | v2 false-alarm count <= v1 false-alarm count |

## Failure handling

- If any gate fails: v2 stays experimental, v1 stays the product default, the miss goes in
  `KNOWN_FAILURES.md` with the numbers. No constant changes and the same fixture is not re-scored with
  different constants. A different v2 design needs a new pre-registration and a fresh fixture from a new
  author.
- Schema-invalid delivery: the author may be asked once to correct schema errors only; every problem
  is recorded. Requirement gaps (prevalence, volume bands, strata) are recorded as limits of the test,
  not repaired by the main agent.
- Both versions are scored on exactly the same fixture and both results are reported whatever the
  outcome. The main agent never edits the fixture.

## Limits stated in advance

- The brief was written by the main agent, which knows the v2 design. It contains no detector
  constants (a test checks for a few giveaway words), but the test is not blind on the brief side.
- The author is a model; labels are not human-reviewed.
- Aggregated visit counts replace claim-level data. Both versions run through the real repository path
  on single-line visit claims generated deterministically from the counts.
- A different-family author may be unavailable in this environment.
- One fixture of this size gives wide intervals. A pass is evidence on synthetic data only, not
  real-world performance.
