# Phase 2 report: synthetic payer data model

Status: **approved by the owner on 2026-10-19**, including the scale deviation and the KF-014
handling (decisions 1 to 3 below).

## 1. Executive summary

Phase 2 built a reproducible synthetic payer dataset that the Phase 3 tools and the Phase 5 agent
can be scored against.

- **Real diagnosis codes, verified source.** The FY2027 ICD-10-CM code file was fetched from CDC/NCHS
  with the project client, hashed, and recorded in the manifest as a new `data` source (kept out of
  the retrieval corpus). The repository holds a 420-code sample, codes only.
- **Synthetic claims.** 4,000 members, 400 providers, 40,060 claims, 64,098 lines, with fake `X0001`
  procedure codes. No names, no dates of birth, no descriptors.
- **Five anomaly types, each with decoys.** Duplicate claims, unbundling, excess units, provider
  intensity outliers, and service-date anomalies: 30 true cases and 30 look-alike decoys of each
  (300 labelled cases), plus a flag queue of 618 claims that includes decoys and 200 false alarms.
- **Truth is separated.** `payer.sqlite` (for tools) has no truth data; `truth.sqlite` is for
  evaluations only. A test enforces this.
- **Reproducible.** Same seed, two separate processes: byte-identical SQLite files.
- **Independent check.** A separately written reference checker recovers all 150 seeded anomalies
  and flags no decoy (our own generated data), but only after I adjusted one of its rules (see section 3).

## 2. Metrics and spend vs cap

| Item | Value | How measured |
|---|---|---|
| Tests | 149 passing (125 before; 24 new: 21 for the synthetic data, 3 for the `zip` source type) | `uv run pytest` |
| Quality gates | ruff, ruff format, mypy strict, gitleaks, all pre-commit hooks green | `uv run pre-commit run --all-files` |
| Default dataset | 40,060 claims, 64,098 lines, 618 flags, 300 labelled cases | `eval/synthetic_dataset.json` |
| Checker vs labels, default scale | 150 of 150 anomalies found; 0 of 150 decoys flagged; 0 findings in the clean baseline | `tests/test_synth_full.py`, `tests/test_synth_baseline.py` |
| Generation time | about 3 seconds | `uv run python -m claims_copilot.synth` |
| Phase 2 spend | $0.00 of the $1.00 cap | `uv run python -m claims_copilot.budget` |
| Total spend | $0.0166 of the $50 cap | same |

Commits: `bc0d534` (source step), `b22a9b4` (generator). Reminder: check Cursor's own usage
yourself; agents cannot see it.

## 3. Failures and open risks

Full list in `KNOWN_FAILURES.md` (KF-011 to KF-016). The ones that matter most:

- **The 150 of 150 result is on an adjusted rule (KF-014).** The checker's first outlier rule
  (share at least 3x the peer median) missed 2 of 30 labelled outliers at full scale, because 11 of
  33 orthopedics peers were seeded elevated cases and pulled the median up. The labels were right
  (shares about 0.56 against a baseline of about 0.12). I changed the multiple to 2x after seeing
  the failure, so this is not a clean first-try pass. It also teaches something real: a
  median-ratio peer screen degrades when many peers are elevated.
- **Circularity (KF-011).** I wrote both the generator and the checker. Agreement shows the labels
  are consistent, not that the data is realistic. Decoys and the separate truth store reduce the
  risk; hand-built cases in Phase 7 are the real answer.
- **Invented rules (KF-012, KF-013).** Bundle and unit rules are made up, not NCCI or MUE; unit
  limits are per line, not per day; diagnoses and procedures are paired at random.
- **ICD-10-CM terms (KF-015).** The CDC policy says "Most of the information" is public domain, and
  I found no notice specific to the code file. Treated as a US government work; re-check before
  publishing. The file also has 18 `QA` codes I did not research and excluded from the sample.
- **Process notes.** The auto-review twice blocked a command as "before plan approval" after you had
  approved; both went through the approval card. `curl` failed certificate verification once; I
  did not disable verification and used the project client instead.

## 4. Decisions needed

1. **Approve Phase 2 as built**, or tell me what to change.
2. **Scale deviation.** I raised scale from 2,000 / 150 / 20,000 to 4,000 / 400 / 40,000 so that 30
   provider-level outliers stay outliers. Recommend accepting; it costs nothing.
3. **KF-014 handling.** Recommend accepting the adjusted rule and relying on Phase 7 hand-built
   cases for an unbiased check, rather than reworking the data now.

## 5. Teach-me list

1. **Decoys (hard negatives).** A dataset with only true anomalies rewards a detector that flags
   everything. Decoys that look similar but are legitimate (a modifier that lifts a bundle rule, a
   repeat visit on a later date) are what measure precision and judgment.
2. **Oracle circularity.** If the same person writes the generator and the checker, agreement is
   weak evidence. What would make the check more independent, and why did a separate truth store
   and an exact set-equality test still matter?
3. **Peer-relative screens and contamination.** Why does a median-ratio outlier rule fail when a
   third of the peer group is elevated, and what would a more robust statistic do differently?

Please confirm you understand these (or say which to explain with `/teach`) before I propose
Phase 3.
