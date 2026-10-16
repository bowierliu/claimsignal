---
name: phase-report
description: Write the end-of-phase report for owner approval. Run as /phase-report when a phase's work is complete.
disable-model-invocation: true
---

# /phase-report

Produce `docs/PHASE<N>_REPORT.md` and present the same content to the owner. Gather facts with
commands (spend, tests, counts, commit hashes); never estimate a number you can measure.

## Format

1. **Executive summary.** What happened, what changed versus before, and the justification for
   each change. Plain language first, then detail.
2. **Metrics and spend vs cap.** Tables with n per group, baselines, deltas, `uv run python -m
   claims_copilot.budget` output (phase and total vs caps). Remind the owner to check Cursor's own
   usage; agents cannot see it.
3. **Failures and open risks.** Everything that did not work or is weak, including small-n
   caveats. Mirror new items into `KNOWN_FAILURES.md`.
4. **Decisions I need from you.** Each with 2-3 options and a recommendation.
5. **Teach me.** A list of 2-3 concepts from this phase the owner can run `/teach` on.

Then update `ROADMAP.md`, `SESSION_LOG.md`, `RESUME_METRICS.md` (measured numbers only, with how
measured), and `EVALUATION.md`. Verify all quality gates are green before presenting. Ask the owner
to confirm understanding before proposing the next phase's plan. Do NOT start the next phase.
