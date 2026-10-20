# Phase 7 plan: evaluation system and judge calibration

Status: **approved by the owner on 2026-10-20 with guardrails (see `DECISIONS.md`); building.** Step 1, the pre-registration (`docs/PHASE7_PREREGISTRATION.md`), is committed before any provider call.

## Goal

Replace "it ran and looked fine" with measured answers to four questions the earlier phases left
open:

1. **Is the agent's output correct?** Does a dossier summary report what the deterministic checks
   actually found (and nothing the checks did not find)?
2. **Is it faithful?** Does each cited quote support the sentence that cites it? The Phase 5
   validator proves a quote is real, not that it answers the point (KF-026).
3. **Does it stay inside the boundary?** Out-of-scope asks, prompt injection in retrieved text,
   fabricated citations, verdict language, and unanswerable questions (KF-026, KF-029, KF-031).
4. **How do the two providers compare** on quality, latency, tokens, and cost, with repeats so
   run-to-run variance is visible (KF-027)?

It also closes the "unbiased check" promised for the tool KFs (KF-011, KF-017) and tells us whether
hybrid search should become the API default (decision 2A in Phase 6).

## Scope

In scope: a versioned case suite, a runner that records every run, deterministic metrics,
an LLM judge **calibrated against hand labels before it is trusted**, repeated runs on both
providers, and a scorecard with uncertainty. Safety cases run through the real scope gate,
validator, and loop.

Out of scope: new sources or corpus changes, changes to tools or the answer boundary rules, tracing,
auth and rate limits (Phase 8), UI (9), deployment (10). The agent prompt `agent_v1` is not changed
(decision 4). `budget/caps.toml` is not edited.

## Principles (fixed now, before any run)

- **Pre-registration.** Case sets, metrics, pass thresholds, and the judge's acceptance threshold are
  written to this plan and committed before any provider is called on the test cases.
- **Cases are never edited to make a result pass.** A failing case goes to `KNOWN_FAILURES.md`.
- **Dev and test split.** About a third of the cases are a development split for fixing the runner,
  rubric, and judge prompt. The rest are a test split that is run once per configuration. Only the
  test split produces headline numbers.
- **Deterministic checks first.** Anything plain code can decide (status, finding recall against the
  truth store, citation resolution, verbatim quotes, verdict words) is not given to a judge.
- **Report uncertainty.** Wilson 95% intervals for rates, paired gained/lost counts for comparisons,
  and the plain statement "directional only" wherever n is small (see the Phase 6 lesson, KF-034).
- **Untrusted text.** Provider output, judge output, and retrieved text are data. Judge output is
  parsed against a schema; a bad parse is a recorded failure, never a guessed label.
- **Truth stays separate.** Only `score.py`-style scoring code opens `truth.sqlite`; the agent, API,
  and tools never do. The new scorer lives beside `score.py` and follows the same rule.

## Case suite

Existing layers are reused; about 95 new agent cases are added, giving roughly 100 end-to-end plus
the 56 retrieval questions that already exist.

| Layer | Cases | Ground truth | Judge needed? |
|---|---|---|---|
| Retrieval | 56 existing (40 dev, 16 held-out) plus 20 new unanswerable questions | verbatim-quote labels; unanswerable = no source in corpus supports it (checked by search, then confirmed by a human read) | No |
| Tools (hand-built) | 20 hand-built claim scenarios in a small separate fixture, with a realistic peer group (not 33-40% seeded) | built by hand so the expected result is known by construction | No |
| End-to-end | 30 flagged claims from a fresh seed, stratified over the 5 anomaly types, with both seeded anomalies and decoys | truth store: which finding should appear (or not appear, for decoys) | Faithfulness only |
| Unanswerable (agent) | 20, the same questions as the retrieval layer | expected `INSUFFICIENT_EVIDENCE` | Only for "honest non-answer" wording |
| Safety and refusal | 25: paraphrased and obfuscated decision asks (10), injection inside retrieved text via a test-only planted chunk, never added to the real corpus (6), fabricated or malformed citations requested (5), verdict-language elicitation (4) | expected status and absence of verdict language or fabricated ids | No (rule-checked), judge as a second opinion |

Total new agent cases: 20 (tool fixture, run through the agent as well) + 30 + 20 + 25 = 95.

## Metrics

Deterministic (plain code):

- **Status accuracy** against the expected status per case.
- **Finding recall and precision** on end-to-end dossiers: seeded anomaly types the summary cited
  from the dossier, and false findings reported on decoys.
- **Boundary compliance:** `OUT_OF_SCOPE` rate on blocked asks, verdict-language rate, rate of
  fabricated ids reaching an `ANSWERED` answer (target: zero).
- **Rejection cost:** how often a correct answer was rejected by the validator (false reject), found
  by comparing with the judge and hand labels.
- Latency, model calls, tokens, cost per case from the run records and `budget/ledger.jsonl`.

Judge-scored (after calibration):

- **Faithfulness:** per cited statement, is it supported by its quote or tool result (supported /
  partly / not).
- **Conflict appropriateness:** was `CONFLICTING_EVIDENCE` warranted (KF-029)?

## The judge and its calibration

1. **Rubric.** A one-page binary rubric for each judged question, written first.
2. **Hand labels.** 40 agent answers from the **development** split, labelled against the rubric
   (decision 1 says by whom). Stored in `eval/phase7_hand_labels.jsonl`.
3. **Pre-registered acceptance.** The judge is used for a headline number only if agreement with the
   hand labels reaches Cohen's kappa of at least 0.6 and it makes no more than 2 "supported" calls on
   answers the labeller marked unsupported. Otherwise the judge is reported as **uncalibrated** and
   the faithfulness numbers come from the hand-labelled subset alone. This is decided now, not after
   seeing the result.
4. **Self-preference control.** An answer from one provider is judged by the other provider's model
   (decision 2), so a model does not grade its own writing.
5. **Frozen before test.** The judge prompt (`prompts/judge_v1.md`) is fixed on the development
   split; the test split is judged once.

## Experiments

| ID | Question | Design |
|---|---|---|
| E1 | Provider quality | Both providers, all agent cases, 3 repeats, `agent_v1`, lexical search. Paired by case |
| E2 | Run-to-run variance | From E1: how often do repeats of one case change status or finding set? |
| E3 | Search mode | Policy-related and unanswerable cases only: lexical vs `hybrid_rerank`, one provider per case, paired. Decides the Phase 6 default-mode question and KF-031 |
| E4 | Safety | All safety cases, 3 repeats, both providers, rule-checked |
| E5 | Tool recheck | Hand-built fixture through `tools`: closes KF-011 and KF-017 on cases not shaped by the generator |

The unit of analysis is the **case**, not the run: repeats of a case are averaged first so that
one flaky case does not look like many.

## Build order (after approval)

1. Pre-register: commit the case schema, metric definitions, thresholds, and rubric.
2. Hand-built tool fixture and the E5 scorer (free).
3. Unanswerable questions and the retrieval layer extension (free, offline; E3 needs one paid pass
   later).
4. End-to-end case generator from a fresh seed, with the truth-based expected labels (free).
5. Safety cases including the planted-chunk test corpus (free, offline tests that the plant never
   reaches the real index).
6. Runner: records every run (input, tool log, answer, validator result, cost) to `data/runs/`;
   resumable and CostGuard-gated; dry run prints the estimate and waits for your go.
7. Judge prompt and schema; development-split runs; hand labelling; calibration decision.
8. Test-split runs (E1 to E4), scorecard in `eval/scorecards/`, `EVALUATION.md`.
9. Update `KNOWN_FAILURES.md` (KF-006, 011, 017, 026 to 029, 031, 034), `DECISIONS.md`,
   `RESUME_METRICS.md` (measured only, with commit), `ARCHITECTURE.md`, `README.md`,
   `PHASE7_REPORT.md`.

## Budget check against `budget/caps.toml`

Cap `p7` is $12.00 and the per-eval-run cap is $5.00. Spent so far: $0.6383 of $50, Phase 7 $0.
Estimates use the **measured** Phase 5 and 6 numbers (about $0.0013 per OpenAI investigation, $0.0022
per Anthropic one, $0.001 per rerank), not an assumption:

| Item | Estimate |
|---|---|
| E1 and E4 agent runs: about 95 cases x 2 providers x 3 repeats = 570 runs at about $0.0018 | about $1.00 |
| E3 hybrid+rerank pass over about 40 policy and unanswerable cases x 2 providers x 3 repeats, extra rerank per search | about $0.25 |
| Judge calls: about 570 answers x about 5k input tokens, plus calibration reruns | about $0.50 |
| Retrieval layer: 20 new unanswerable questions, embeddings and rerank | under $0.05 |
| **Total** | **about $1.80** |

I propose a **$4.00 ceiling for Phase 7 live spend** inside the $12 cap, which leaves room for one
full rerun. Out-of-scope cases stop at the gate and cost $0. I will state the dry-run number before
each paid step and wait for your go. Cursor's own usage is separate and not visible to me; please
check it at the gate.

## Exit criteria

- Case suite, metrics, thresholds, and rubric committed before any test-split run.
- Hand labels stored; judge calibration result (kappa, disagreements) reported, pass or fail.
- E1 to E5 reported on the test split with intervals and gained/lost counts; development-split
  numbers are labelled as such.
- A written answer on the Phase 6 default-mode question (E3) and on KF-029 (conflict over-reporting)
  and KF-031 (unanswerables), as measured, even if the answer is "cannot tell at this n".
- Every failure is in `KNOWN_FAILURES.md`; no case edited to pass.
- `pytest`, `ruff`, `ruff format --check`, `mypy`, and pre-commit green; docs updated; phase report
  written; no Phase 8 work started.

## Risks

- **Circularity.** The same author writes the cases and the generator (KF-011). The hand-built
  fixture and the owner's labels are the partial defence; the report says what remains.
- **Hand labels are few and subjective.** 40 labels give a wide kappa interval. A pass means "agrees
  well enough on this sample", not that the judge is validated in general.
- **Cheap models.** Both providers are the cheap tier. Rankings say nothing about stronger models,
  and 3 repeats per case still leave wide intervals on rare events such as a fabricated citation.
- **Rule checks are a floor.** The verdict-word list and scope patterns can miss unusual phrasings;
  the obfuscated asks are meant to find that, and misses will be recorded.
- **Judge failure modes.** Self-preference, leniency toward fluent text, and sensitivity to prompt
  wording. Mitigated by cross-provider judging, calibration, and a frozen prompt, not removed.
- **Over-fitting by repetition.** Rerunning the test split after fixes turns it into a dev set.
  Any rerun is labelled as such and a fresh seed is used for a new test split.

## Decisions needed

1. **Who writes the calibration labels?**
   - A (recommended): you label 40 answers against a one-page rubric (about an hour, in a simple
     file I prepare), so the judge is checked against a human other than the author.
   - B: I draft labels and you review a random 15. Faster, but the judge is then checked against
     the same author as the cases (circular).
   - C: no hand labels; deterministic metrics only and the judge reported uncalibrated.
2. **Which model judges?**
   - A (recommended): each answer is judged by the other provider's cheap model (`gpt-6-luna` and
     `claude-haiku-5-5`, both with verified prices). Avoids self-grading; both judges get calibrated.
   - B: one judge (`gpt-6-luna`) for everything. Cheaper and simpler but it grades its own answers.
   - C: a stronger judge model. Needs a verified price and a manifest entry first, so more work
     and likely a larger bill.
3. **Suite size.**
   - A (recommended): about 95 new agent cases plus the existing 56 retrieval questions, as above.
   - B: about 60 agent cases. Cheaper and faster to review, with wider intervals.
4. **Prompt change for KF-029.**
   - A (recommended): measure only. If the data shows conflict over-reporting, the report proposes an
     `agent_v2` and its eval comparison as a separate gated step.
   - B: pre-register an `agent_v2` (a definition of conflict) and compare it with `agent_v1` inside
     this phase. More informative, and more scope and spend.
