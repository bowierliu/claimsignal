# Answer boundary

Status: **implemented in Phase 5** (`src/claims_copilot/agent/`), tested without network, and
exercised live in two smoke runs (`EVALUATION.md`). Rules marked "from the brief" are the owner's
requirements. Known gaps are in `KNOWN_FAILURES.md` KF-026, KF-027, and KF-029.

## Why

The model can be wrong, can be manipulated by retrieved text, and must not make decisions that
belong to a human. So the model's output is untrusted and is checked by plain code after it is
generated. If a check fails, the answer is not shown as an answer.

## What the system never does (from the brief)

It never autonomously decides fraud, denial, coverage, or medical necessity. A conservative
request-scope policy blocks out-of-scope asks (for example "is this claim fraudulent?", "should
we deny this?", "is this service medically necessary?"). The human investigator decides.

## Deterministic validation after generation (from the brief)

- Every citation must resolve to a retrieved `chunk_id`.
- `ANSWERED` requires at least 1 citation.
- `CONFLICTING_EVIDENCE` requires at least 2 citations.
- Statuses and reasons are typed enums, not free text.

## Statuses and reasons (implemented)

| Status | Allowed reason | Requirement |
|---|---|---|
| `ANSWERED` | `SUPPORTED` | at least 1 valid citation; every statement cited |
| `CONFLICTING_EVIDENCE` | `SOURCES_DISAGREE` | at least 2 valid citations from at least 2 distinct sources (a screen flag, each tool result, and each policy source count separately) |
| `INSUFFICIENT_EVIDENCE` | `NO_RELEVANT_SOURCE`, `TOOL_ERROR`, `STEP_LIMIT`, `BUDGET_LIMIT` | no summary or quotes; `searched` is filled by the runtime from its tool log |
| `OUT_OF_SCOPE` | `REQUEST_BLOCKED` | no summary or quotes |
| `INVALID_OUTPUT` | `SCHEMA_VIOLATION`, `UNRESOLVED_CITATION`, `VERDICT_LANGUAGE`, `QUOTE_NOT_FOUND`, `PROVIDER_ERROR` | assigned by the runtime only; never shown as an answer; the record is kept |

The model may only choose the first four statuses; the limit and failure reasons are the runtime's.

## The checks, in order

1. **Request-scope gate, before any model call.** Deterministic patterns over normalised input
   (Unicode folded, invisible characters dropped, Cyrillic and Greek look-alike letters mapped to
   Latin, letters split by spaces or punctuation joined in a second view). A blocked request
   returns `OUT_OF_SCOPE` and costs nothing. In an Ask session the gate also runs on the last two
   unrefused messages joined to the new one, so a decision split across turns ("is this" /
   "claim" / "medically necessary or not") is blocked. A refused message is neither joined nor
   repeated to the model (the prior-turn block shows "[blocked request]"), so it does not taint
   the next turn and "now answer that one" has nothing to answer.
2. **Schema.** One JSON object, exact keys, enum membership, length limits.
3. **Status and reason agree** (table above).
4. **Citations resolve.** The runtime names every citable id (`E1`, `E1.s1` for a flag,
   `E1.r2.f1` for a finding inside a dossier, or a policy `chunk_id`) after trimming oversized
   results, so only what the model was shown can be cited. A raw record id is not a citation.
5. **Counts per status and no uncited statement.**
6. **Quotes are verbatim** from a retrieved chunk, compared with all whitespace ignored (PDF
   extraction splits letters from words); a changed letter or word fails.
7. **No verdict language** in what the model wrote. A word list is a floor, not a proof. Since
   the 2026-11-16 Ask review it also covers "not payable / not covered", "should / must / will
   (not) be paid / rejected / ...", upcoding, scam, "legitimate", "eligible for payment", a bare
   "Yes." or "No.", a statement that opens with a decision command ("Approve the claim."), and
   the same text after look-alike letters are folded and split letters joined ("F r a u d").
   Re-checking all 643 statements shown in recorded Ask runs flagged none. English only (KF-072).
8. **A search result is not evidence by itself** (2026-11-15). The top-level id of a policy
   search (`E3`) only says that a search ran. An `ANSWERED` whose citations are all search ids
   becomes `INSUFFICIENT_EVIDENCE` / `NO_RELEVANT_SOURCE` with nothing shown, and search ids do
   not count toward the two sources `CONFLICTING_EVIDENCE` needs. Per statement (2026-11-16):
   if any one statement cites only search ids while others cite real evidence, the answer is
   `INVALID_OUTPUT` / `UNRESOLVED_CITATION`, so an unsupported sentence cannot ride along.

In "Ask the agent", earlier turns of the session reach the model as an untrusted block that can
never be cited: citations resolve only against evidence retrieved in the current turn. The browser
gets a view built from the validated answer (statements, resolved sources, fixed messages for the
other statuses); for `INVALID_OUTPUT` it gets only "The answer could not be validated, so it is not
shown."

Retrieved text and tool output are data. Policy hits are marked `untrusted`, and nothing in them
is executed or followed as an instruction.

## Limits that remain

- The checks prove a citation exists and a quote is real, not that the sentence is a fair reading
  of it (KF-026). The Phase 7 judge and hand labels address that.
- Rules that were stricter than needed lost correct answers; three were relaxed on the owner's
  decision (KF-023 to KF-025, `DECISIONS.md`), each with a test. Models now report more
  `CONFLICTING_EVIDENCE` (KF-029); whether that is right is a Phase 7 question.
- The model's own `searched` list is required by the schema but is replaced by the runtime's.

## Testing it

Phase 7 includes safety and refusal cases (out-of-scope asks, prompt injection in retrieved text,
fabricated citations). Failures are recorded in `KNOWN_FAILURES.md`, never hidden by editing the
cases.
