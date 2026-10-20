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
| 7 | Eval system | Not started |
| 8 | Observability and security | Not started |
| 9 | Workbench UI | Not started |
| 10 | Deployment | Not started |
| 11 | Interview hardening | Not started |
| End | **Publish to GitHub at project end** (owner does this himself) | Deferred |

## Publish to GitHub at project end: pre-publish checklist

- [ ] Run gitleaks over the FULL git history.
- [ ] Make the license decision (open gate).
- [ ] Choose the product name: run a real USPTO trademark search and re-check PyPI, GitHub, and
      domains (candidates and evidence in `DECISIONS.md`, 2026-10-16).
- [ ] Confirm `data/raw/` is still gitignored and no third-party source files are committed.
- [ ] Decide public vs private (owner earlier said private; a resume showcase normally needs public).
- [ ] Scan docs and data for any employer-specific content.
