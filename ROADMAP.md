# Roadmap

Work one phase at a time; the owner approves each phase report before the next starts.

| Phase | Scope | Status |
|---|---|---|
| 0 | Source corpus and baseline RAG (fetch, verify, manifest, chunk, embed, retrieval eval) | Approved 2026-10-16 (see `docs/PHASE0_REPORT.md`) |
| 1 | Project foundation (structure, CI, rules, skills, subagents, naming, old-repo deletion gate) | Approved 2026-10-19 (see `docs/PHASE1_REPORT.md`) |
| 2 | Synthetic payer data model | Approved 2026-10-19 (see `docs/PHASE2_REPORT.md`) |
| 3 | Deterministic tools | Approved 2026-10-19 (see `docs/PHASE3_REPORT.md`) |
| 4 | Typed API | Approved 2026-10-20 (see `docs/PHASE4_REPORT.md`) |
| 5 | Bounded agent workflow | Approved 2026-10-20 (see `docs/PHASE5_REPORT.md`) |
| 6 | Retrieval upgrades | Approved 2026-10-20 (see `docs/PHASE6_REPORT.md`) |
| 7 | Eval system | Done 2026-10-20 under the owner's standing instruction (see `docs/PHASE7_REPORT.md`); labels are model-drafted (amendment A4, KF-041) |
| 8 | Observability and security | Done 2026-10-20 under the owner's standing instruction (see `docs/PHASE8_REPORT.md`, `docs/SECURITY.md`) |
| 9 | Workbench UI | Done 2026-10-20 under the owner's standing instruction (see `docs/PHASE9_REPORT.md`) |
| 10 | Deployment | Done 2026-10-20 as artifacts, not built or deployed (see `docs/DEPLOYMENT.md`, KF-053) |
| 11 | Interview hardening | Done 2026-10-20 under the owner's standing instruction (see `docs/FINAL_REPORT.md`) |
| End | **Publish to GitHub at project end** (owner does this himself) | Deferred |

## Possible follow-ups (not started)

(a) A pre-registered provider-intensity redesign tested on fresh independent data, with a brief that gives each specialty enough ordinary providers; (b) a human check of Sol's labels and the 19 model-drafted calibration labels (KF-041) — PARTLY DONE 2026-11-07: a blind Claude Sonnet 5.5 model re-review was ingested (KF-060; model-generated, not human, human gap still open); earlier 2026-11-03: blind review sheet prepared (`eval/labeling/phase7_owner_review_sheet.md`), waiting for the owner to label it, then `evals.owner_review ingest` + `evals.calibrate`; (c) a line-level independent test.

## Publish to GitHub at project end: pre-publish checklist

- [x] Run gitleaks over the FULL git history (2026-10-20: no leaks in 51 commits; re-run before publishing).
- [x] License: MIT (owner decision 2026-11-03); `LICENSE` added, holder is the git author handle
      (changeable before publishing).
- [x] Product name decision: keep `claims-copilot` (owner decision 2026-11-03), superseded by
      the rename below.
- [x] Run the real USPTO trademark search and re-check PyPI, GitHub, and domains for
      `claims-copilot` before publishing (done 2026-11-03; results in `SESSION_LOG.md`).
- [x] Name re-decision: the checks found collisions (a dead USPTO application for CLAIM COPILOT,
      active commercial use of "Claims Copilot" in health-claims billing, 10+ exact-name GitHub
      repos). Owner chose to rename and picked **ClaimSignal** on 2026-11-03 from three checked
      candidates (PrepayLens, FlagFolio, ClaimSignal). Renamed the same day: `PRODUCT_NAME`,
      distribution name, deploy image names, and current-facing docs; the Python package and env
      vars keep the internal name `claims_copilot`. Known caveat, accepted by the owner:
      claimsignal.io is an unrelated live product (claimant proof for mass arbitrations);
      claimsignal.com appears unregistered and PyPI `claimsignal` is free.
- [x] Confirm `data/raw/` is still gitignored and no third-party source files are committed (2026-10-20).
- [x] Public vs private: PUBLIC (owner decision 2026-11-03). The owner publishes himself.
- [ ] Scan docs and data for any employer-specific content. Assistant scan done 2026-10-20 (no named
      companies, no home paths); the owner must still read it once for terms the assistant cannot recognise.
