# Answer boundary

Status: **design, not yet implemented** (built in Phase 5). The rules marked "from the brief" are
the owner's requirements; the enum names are a proposal to be finalised and tested in Phase 5.

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

## Proposed statuses and reasons (to finalise in Phase 5)

| Status | Meaning | Requirement |
|---|---|---|
| `ANSWERED` | Supported by retrieved evidence | at least 1 valid citation |
| `CONFLICTING_EVIDENCE` | Retrieved sources disagree | at least 2 valid citations |
| `INSUFFICIENT_EVIDENCE` | Nothing retrieved supports an answer | no citations; says what was searched |
| `OUT_OF_SCOPE` | Request asks for a blocked decision | refusal reason code; no evidence summary framed as a decision |
| `INVALID_OUTPUT` | Provider output failed validation (unresolvable citation, wrong schema) | not shown as an answer; logged |

## Testing it

Phase 7 includes safety and refusal cases (out-of-scope asks, prompt injection in retrieved text,
fabricated citations). Failures are recorded in `KNOWN_FAILURES.md`, never hidden by editing the
cases.
