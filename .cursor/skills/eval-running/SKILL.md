---
name: eval-running
description: Run retrieval or end-to-end evaluations safely inside the cost guard and report a metrics table. Use when measuring a change against a baseline or at a phase gate.
---

# Running evaluations

1. **State the plan and cost first.** Name the suite, the baseline it is compared against, the
   number of cases, the model(s), and an estimated cost from the dry run. Full evals run only at
   phase gates, after the owner has seen the estimate. Dev runs use small subsets or fixtures.
2. **Check the budget:** `uv run python -m claims_copilot.budget`. The eval-run cap is $5; pass an
   `eval_run_id` to every guarded call so that cap applies. Stop and ask at 90% of any cap.
3. **Dry run before spending.** Commands with a spend path print an estimate without `--confirm`
   (for example `uv run python -m claims_copilot.retrieval.dense`). Only add `--confirm` when the
   estimate is acceptable.
4. **Same data, same gold.** Compare against the previous result on the same gold set. Never edit
   the gold set or corpus to improve a number; failing cases go in `KNOWN_FAILURES.md`.
5. **Report a table** with n per group, the metric(s), the baseline, the delta, spend, and the
   commit. Flag small groups: with n=8, one case moves a rate by 12.5 points.
6. **Record** results in `EVALUATION.md`; only measured numbers go in `RESUME_METRICS.md`, with
   how they were measured. A prompt change is adopted only after an eval comparison with the
   previous version, logged in `DECISIONS.md`.
7. Tests and CI never run paid evals.
