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

(a) A pre-registered provider-intensity redesign tested on fresh independent data, with a brief that gives each specialty enough ordinary providers; (b) a human check of Sol's labels and the 19 model-drafted calibration labels (KF-041); (c) a line-level independent test.

## Publish to GitHub at project end: pre-publish checklist

- [x] Run gitleaks over the FULL git history (2026-10-20: no leaks in 51 commits; re-run before publishing).
- [ ] Make the license decision (open gate).
- [ ] Choose the product name: run a real USPTO trademark search and re-check PyPI, GitHub, and
      domains (candidates and evidence in `DECISIONS.md`, 2026-10-16).
- [x] Confirm `data/raw/` is still gitignored and no third-party source files are committed (2026-10-20).
- [ ] Decide public vs private (owner earlier said private; a resume showcase normally needs public).
- [ ] Scan docs and data for any employer-specific content. Assistant scan done 2026-10-20 (no named
      companies, no home paths); the owner must still read it once for terms the assistant cannot recognise.
