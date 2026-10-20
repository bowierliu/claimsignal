# Phase 3 report: deterministic tools

Status: **built, awaiting owner approval.** Phase 4 has not been started.

## 1. Executive summary

Phase 3 built the read-only tool layer that the Phase 5 agent will call, and measured it on data
it had not been built against.

- **Tools** (`src/claims_copilot/tools/`): lookups (claim, member history, provider profile, flag
  queue); bundle, unit-limit, and service-date checks; duplicate candidates; code validation
  (procedure codes, and diagnosis codes against the full FY2027 ICD-10-CM list); a provider
  visit-mix comparison with peers; and `claim_dossier`, which runs the checks for one claim and
  returns everything unranked.
- **No verdicts.** Every result is a finding with the claim, line, provider, and rule ids it rests
  on, plus what was examined and what could not be checked. A test scans all output on the generated
  data for verdict words. Near-misses (an exception modifier present, near-match duplicates) are
  shown as observations and never counted as findings.
- **Truth cannot leak.** The tools open `payer.sqlite` read-only through one module that refuses the
  truth file and any truth-like table or column, with writes and ATTACH disabled. Only the scorecard
  opens `truth.sqlite`, and a test enforces that.
- **Measured honestly.** Thresholds were fixed from definitions, one tuning round was used on the
  dev dataset, the code was committed, and only then was a second dataset (seed 20261020) generated
  and scored once.
- **Result.** The four claim-level checks found all 150 seeded claims on both datasets and raised
  no decoy and no clean claim. The provider-intensity check found 26 of 30 held-out outliers (28 of
  30 on dev) and raised no decoy. That 100% mostly shows the tools implement the same rules the
  data was made from (KF-018); the outlier misses are a real weakness (KF-017).

## 2. Metrics and spend vs cap

Held-out dataset (seed 20261020, 40,060 claims), parameters hash `d6536f635e00`, code `c79a9b3`:

| Check | Positives | Found | Precision | Decoys raised | Clean raised |
|---|---|---|---|---|---|
| exact duplicate (claims) | 60 | 60 | 100% | 0 of 60 | 0 of 39,940 |
| bundle pair without exception (claims) | 30 | 30 | 100% | 0 of 30 | 0 of 40,000 |
| units above line limit (claims) | 30 | 30 | 100% | 0 of 30 | 0 of 40,000 |
| line date outside claim window (claims) | 30 | 30 | 100% | 0 of 30 | 0 of 40,000 |
| visit mix above peer range (providers) | 30 | 26 | 100% | 0 of 30 | 0 of 135 |

Dev dataset (seed 20261019, untuned): identical except outliers 28 of 30.

| Item | Value |
|---|---|
| Tests | 209 passing (149 before; 60 new) |
| Quality gates | ruff, ruff format, mypy strict, gitleaks, pre-commit all green |
| Scoring time | about 20 seconds for 40,060 claims |
| Phase 3 spend | $0.00 against a $0.00 cap. Total $0.0166 of $50 |

Reminder: please check Cursor's own usage yourself; agents cannot see it.

## 3. Failures and open risks

- **KF-017 (new).** Provider outliers are missed when 33% to 40% of a specialty's providers are
  themselves seeded: 2 of 30 on dev, 4 of 30 held-out, scores 2.84 to 3.34 against a 3.5 cutoff.
  The one allowed tuning round (iterative trimming) did not fix it, so it was not adopted and I
  tried nothing else on dev. The contamination is higher than a real peer group would likely have.
- **KF-018 (new).** 100% on the claim-level checks is not a claim about real data. Tools and
  generator share rule definitions, and clean claims have no noise beyond the decoys.
- **KF-019 (new).** The near-match duplicate tiers fire on every decoy by design and on 25 to 34
  clean claims out of about 40,000; they are observations only.
- **Still open:** KF-009 and KF-012 (real NCCI/MUE tables are gated; the rules are invented and
  per line); KF-011 (shared author).
- **A scorecard gap, found by a test.** A seeded provider the tool declined to score was not listed
  as missed. Fixed before the held-out run; dev numbers unchanged.
- **Not covered:** per-day unit limits, claims across members, amounts and diagnosis-to-procedure
  plausibility, and any tool for retrieval over policy text (that is Phase 5 orchestration).

## 4. Decisions needed

1. **Provider-outlier weakness (KF-017).** Options: (A, recommended) accept the simple statistic and
   the recorded misses, and check it again on the Phase 7 hand-built cases where contamination is
   realistic; (B) spend another tuning round on a fresh dev dataset (for example a pooled
   cross-specialty reference), reported on a new held-out seed; (C) lower the cutoff, which will
   likely raise decoys.
2. **Near-match duplicate tiers (KF-019).** (A, recommended) keep them as labelled observations; (B)
   drop them from the tool output.
3. **Next phase.** Approve this report and I will propose the Phase 4 plan (typed FastAPI service
   over these tools) for your review before building anything.

## 5. Teach-me list

1. **Modified z-score, median, and MAD**, and the idea of a breakdown point: why a few outliers do
   not move a median, and why 40% of them still do.
2. **Held-out evaluation versus tuning on the test set:** why the second dataset was generated
   after the code was frozen, and what the discarded tuning round showed.
3. **Findings versus observations, and why decoys matter:** how to read recall, precision, and
   "decoys raised" together, and why 100% on self-generated data is weak evidence.

Please confirm you understand these (or say which to explain with `/teach`) before I propose
Phase 4.
