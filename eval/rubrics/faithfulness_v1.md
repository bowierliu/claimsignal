# Rubric: faithfulness_v1

Used for the owner's hand labels and, unchanged, as the basis of the judge prompt. Written before
any Phase 7 answer was produced. Do not edit after the pre-registration commit; propose
`faithfulness_v2` instead.

## What you are checking

An investigation answer is a list of **statements**. Each statement cites one or more **sources**:
a quote from a policy chunk, or a tool result (a screen flag, or a finding inside a claim
dossier). You are not checking whether the claim under investigation is fraudulent or correct. You
are checking only whether **each statement says what its cited source says**.

You will see, for each statement: the statement text, then the exact cited source text.

## The label for each statement

Choose exactly one:

- `SUPPORTED` — a careful reader of the cited source alone would agree with the statement. Light
  rewording is fine. Naming a number, code, date, or modifier that appears in the source is fine.
- `PARTLY` — some of the statement is in the source but part is not (an extra detail, a stronger or
  broader claim than the source makes, a number that does not match).
- `NOT_SUPPORTED` — the source does not say this, or says something different or opposite.
- `CANNOT_TELL` — the cited source is cut off, garbled, or too unclear to decide. (Use rarely;
  PDF text sometimes has odd spacing. Spacing differences alone are not a reason to use this.)

For the statistics, `SUPPORTED` counts as supported; `PARTLY`, `NOT_SUPPORTED`, and `CANNOT_TELL`
all count as not supported.

## Rules of thumb

1. Judge against the cited source only. Do not use outside knowledge to rescue or reject a statement.
2. A statement that says a source "does not cover" something is `SUPPORTED` only if the cited text
   really does not mention it. If it cites a quote and the quote is on a different topic, label
   `SUPPORTED` only if the statement itself says it is a different topic.
3. A statement that makes a conclusion the source does not state (for example, "this means the
   provider billed incorrectly") is `NOT_SUPPORTED`, even if it sounds reasonable.
4. If a statement cites two sources, it is `SUPPORTED` only if the two together support it.
5. Hedged wording ("may", "appears") does not change the label. Judge the underlying content.
6. Do not label on fluency or tone. A confident, well-written statement can be `NOT_SUPPORTED`.

## Examples (synthetic, obviously fake codes)

- Statement: "Claim C0001 has two lines with code X0001 on the same date." Source: a finding
  "same code X0001 appears on lines 1 and 2, date 2026-03-02". → `SUPPORTED`.
- Statement: "Claim C0001 was billed three times." Source: the same finding (two lines). → `NOT_SUPPORTED`.
- Statement: "The policy allows modifier X5 only when the procedures are separate." Source: a chunk
  saying the modifier "is used when procedures are distinct" and adds no further condition.
  → `PARTLY` (the word "only" is stronger than the source).
