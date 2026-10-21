# Phase 7 report: the eval system

Status: complete under the owner's standing instruction of 2026-10-20 (no per-phase approval gate).
Phase 8 starts after this report.

## 1. Executive summary

I built and ran a pre-registered evaluation of the agent on synthetic data: 95 new agent cases
(unanswerable, hand-built tool scenarios, end-to-end claim investigations, safety), a development and
a test split fixed by a hash of the case id, both providers, three repeats, and a cross-provider LLM
judge for faithfulness. The test split was run once per configuration.

**The most important caveat: the calibration labels were drafted by another model (GPT Sol), not
written by a human, and the owner's review was a form check only (amendment A4, KF-041).** The judge
passed the registered acceptance rule against those labels, so its agreement means agreement with
another LLM. Faithfulness numbers are weaker evidence than they would be with human labels, and the
conflict judge is uncalibrated.

What the system does well, on test (assistant-written cases, synthetic data, cheap models):

- It finds the planted anomalies: 98.9% of seeded anomaly types reported (15 seeded claims, Wilson
  80% to 100%), no decoy reported, no fabricated citation in a shown answer, no verdict language in
  any model statement.
- It refuses decisions: 6 of 6 obfuscated decision asks blocked; a planted prompt injection was
  followed by the model in 0 of 3 test cases and reached the investigator in 0.
- The deterministic tools found 20 of 20 hand-built scenarios with no false alarm.

What it does not do well (targets missed, all logged):

- Unanswerable questions: `INSUFFICIENT_EVIDENCE` in 64% of cases against a target of 80%.
- Judged faithfulness: 0.789 case-mean (0.718 to 0.850) against a target of 0.85.
- Rejected answers: 17% of safety runs and 25% of hybrid end-to-end runs end as `INVALID_OUTPUT`.
- Hybrid search with rerank is not better on this suite and costs about twice as much, so the API
  default stays lexical.
- OpenAI and Anthropic (cheap models) are not detectably different at this n.

## 2. Metrics and spend

Full tables with intervals: `EVALUATION.md`. Scorecards: `eval/scorecards/p7_*`.

| Result | Value |
|---|---|
| Judge calibration (registered rule; C counts as not supported) | Accepted: kappa 0.7535, false "supported" 2 of 2 allowed, minority class 28 of 15 needed, agreement 92.3% on 169 statements |
| Conflict judge | Uncalibrated (8 labelled answers, 10 needed); reference labels only |
| End-to-end truth recall (test, lexical) | 0.989 (15 seeded cases) |
| Unanswerable `INSUFFICIENT_EVIDENCE` (lexical / hybrid) | 0.64 / 0.60 (target 0.80 missed); 0.87 / 0.83 counting a safe refusal |
| Judged faithfulness, case mean (lexical / hybrid) | 0.789 / 0.729 (target 0.85 missed; hybrid directional) |
| Safety invariants | fabricated citation 0; verdict language in a statement 0; verdict word inside a verbatim quote in 5 runs (KF-045) |
| Hybrid vs lexical, paired policy cases | gained 0, lost 1 of 19; default unchanged |
| Spend | Phase 7 $2.3508 of the $4.00 ceiling and the $12 cap; project $2.9890 of $50 |
| Tests | 607 passing; ruff, format, mypy strict green |

Cursor's own usage is separate from this ledger and I cannot see it. Please check it.

## 3. Failures and open risks

- KF-041: labels are model-drafted; false "supported" sits exactly on its limit; without the 19
  "cannot tell" statements (all caused by the 900-character display cut-off or omitted search hits)
  the rule would not accept the judge. A human check of those 19, the 2 false-supported statements
  and the 8 conflict answers would close most of the gap and takes about 20 minutes.
- KF-042 to KF-047: missed targets, validator rejections, verdict words inside quotes, conflict not
  measured, retrieval-only unanswerable layer not run.
- KF-011 and KF-006 stand: cases and generator share an author.
- 6 end-to-end hybrid cases and 3 planted-injection cases are very small samples. Read them as
  directional.

## 4. Decisions made on my behalf (listed for the owner)

All logged in `DECISIONS.md`. Under the standing instruction I chose the recommended option each time:

1. **Label provenance (A4).** The label source changed from owner hand labels to model-drafted labels
   (GPT Sol). The owner review field was left blank in the instruction, so I recorded it as "form
   check only, content review not stated, treated as unreviewed" and did not assume more. Rows carry
   `label_source` and `owner_review`; the owner's identity is not written on any row.
2. Counting "cannot tell" as not supported (the registered rule), with a sensitivity analysis shown.
3. Judge accepted, so the test split was judged (cost $0.23).
4. Default search mode stays lexical (E3 rule).
5. No `agent_v2` (conflict is rare and uncalibrated).
6. Missed targets reported, not tuned.
7. Starting Phase 8 without a separate approval, under the standing instruction.
8. Retrieval-only unanswerable layer not run (KF-047).

## 5. Teach me (2 or 3 concepts)

1. **Why agreement with a model-drafted label set is weaker than agreement with a human.** Two
   models can make the same mistake for the same reason (for example reading a truncated source as
   support) and still show high kappa.
2. **Pre-registration and why a missed target is not a bug to patch.** Fixing the case or the
   threshold after seeing the result would make the number meaningless.
3. **Case-level versus statement-level rates.** Statements in one answer are correlated, so a pooled
   rate with a Wilson interval is too tight. Averaging per case, then bootstrapping over cases, gives
   an honest interval.
