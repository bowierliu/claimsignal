# Rubric: conflict_v1

For answers whose status is `CONFLICTING_EVIDENCE` (KF-024, KF-029). Written before any Phase 7
answer exists. Do not edit after the pre-registration commit.

## The question

Is `CONFLICTING_EVIDENCE` warranted here? Two fields per answer:

1. `label`: `WARRANTED` or `NOT_WARRANTED`.
2. `pattern`: `FLAG_VS_CHECK` if the only disagreement the answer reports is "a screen flag says X
   but the checks found nothing to support it"; otherwise `OTHER`.

## Why the owner decides, not the rubric

Whether a flag that the checks do not confirm is a real "conflict" is an open judgement
(`ANSWER_BOUNDARY.md`, KF-029). This rubric does not decide it. Use your own judgement for the
`label`, and always fill `pattern`, so the report can show the label rates **separately for
`FLAG_VS_CHECK` and `OTHER`** and the definition can be fixed from your labels rather than from the
assistant's view.

## Guidance

- Clearly warranted: two cited sources state things that cannot both be true of the same fact (for
  example two tool results that give different dates for the same service, or two policy chunks
  that allow and forbid the same thing under the same stated conditions).
- Clearly not warranted: a policy source that does not address the point, or two sources that cover
  different aspects and do not contradict.
- Judge only from what the answer cites. Do not use outside knowledge.
- When unsure, pick the closer label and write a one-line note. Notes are for improving the
  definition later; they do not change the label.

## Output

`label`, `pattern`, and an optional one-line `note`.
