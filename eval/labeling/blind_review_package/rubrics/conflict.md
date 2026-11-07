# Rubric: conflict_v1

## The question

Is `CONFLICTING_EVIDENCE` warranted here? Two fields per answer:

1. `label`: `WARRANTED` or `NOT_WARRANTED`.
2. `pattern`: `FLAG_VS_CHECK` if the only disagreement the answer reports is "a screen flag says X
   but the checks found nothing to support it"; otherwise `OTHER`.

## Guidance

- Clearly warranted: two cited sources state things that cannot both be true of the same fact (for
  example two tool results that give different dates for the same service, or two policy chunks
  that allow and forbid the same thing under the same stated conditions).
- Clearly not warranted: a policy source that does not address the point, or two sources that cover
  different aspects and do not contradict.
- Judge only from what the answer cites. Do not use outside knowledge.
- When unsure, pick the closer label.

## Output

`label` (W or N) and `pattern` (F or O), as set out in `INSTRUCTIONS.md`. Use your own judgement for the label, and always give the pattern.
