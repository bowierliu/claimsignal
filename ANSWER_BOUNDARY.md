# Answer boundary

Status: **implemented in Phase 5** (`src/claims_copilot/agent/`), tested without network, and
exercised live in two smoke runs (`EVALUATION.md`). Rules marked "from the brief" are the owner's
requirements. Known gaps are in `KNOWN_FAILURES.md` KF-023 to KF-027.

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
| `CONFLICTING_EVIDENCE` | `SOURCES_DISAGREE` | at least 2 valid citations from at least 2 distinct sources |
| `INSUFFICIENT_EVIDENCE` | `NO_RELEVANT_SOURCE`, `TOOL_ERROR`, `STEP_LIMIT`, `BUDGET_LIMIT` | no summary or quotes; says what was searched |
| `OUT_OF_SCOPE` | `REQUEST_BLOCKED` | no summary or quotes |
| `INVALID_OUTPUT` | `SCHEMA_VIOLATION`, `UNRESOLVED_CITATION`, `VERDICT_LANGUAGE`, `QUOTE_NOT_FOUND`, `PROVIDER_ERROR` | assigned by the runtime only; never shown as an answer; the record is kept |

The model may only choose the first four statuses; the limit and failure reasons are the runtime's.

## The checks, in order

1. **Request-scope gate, before any model call.** Deterministic patterns over normalised input
   (Unicode folded, invisible characters dropped). A blocked request returns `OUT_OF_SCOPE` and
   costs nothing.
2. **Schema.** One JSON object, exact keys, enum membership, length limits.
3. **Status and reason agree** (table above).
4. **Citations resolve.** The runtime names every citable id (`E1`, `E1.s1` for a flag,
   `E1.r2.f1` for a finding inside a dossier, or a policy `chunk_id`) after trimming oversized
   results, so only what the model was shown can be cited. A raw record id is not a citation.
5. **Counts per status and no uncited statement.**
6. **Quotes are verbatim** (whitespace-normalised) from a retrieved chunk.
7. **No verdict language** in what the model wrote. A word list is a floor, not a proof.

Retrieved text and tool output are data. Policy hits are marked `untrusted`, and nothing in them
is executed or followed as an instruction.

## Limits that remain

- The checks prove a citation exists and a quote is real, not that the sentence is a fair reading
  of it (KF-026). The Phase 7 judge and hand labels address that.
- A stricter-than-needed rule loses correct answers (KF-023, KF-024, KF-025). Those are recorded,
  not quietly relaxed.

## Testing it

Phase 7 includes safety and refusal cases (out-of-scope asks, prompt injection in retrieved text,
fabricated citations). Failures are recorded in `KNOWN_FAILURES.md`, never hidden by editing the
cases.
