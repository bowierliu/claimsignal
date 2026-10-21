# Phase 8 report: observability and security

Status: complete under the owner's standing instruction of 2026-10-20 (no per-phase approval gate).
Phase 9 starts after this report.

## 1. Executive summary

I added the controls an operator would ask about before running this near sensitive data: traces
that carry no payload, an audit log that shows if history was edited, a scrubber for credentials and
personal identifiers, and access control on the API. Nothing here calls a model, so it cost
nothing. The controls are tested; the limits are written down (`docs/SECURITY.md`, KF-048 to
KF-050) and are real: one shared key, a per-process rate limit, a tamper-evident (not tamper-proof)
log, and a pattern scrubber that is not a PHI scanner.

One behaviour change: the API runner now refuses to listen on a non-loopback address unless
`CLAIMS_COPILOT_API_KEY` is set. The Phase 4 decision ("no authentication, loopback only") assumed
the service would never face a network; Phase 10 changes that.

## 2. Metrics and spend

| Item | Value |
|---|---|
| New modules | `obs/redact.py`, `obs/trace.py`, `obs/audit.py`, `api/guard.py` |
| Tests | 649 total, 42 new (scrubber 11, tracer 7, audit 9, API access 9, loop wiring and injection 5, runner 1) |
| Provider calls, spend | none; Phase 8 spend $0.00. Project total about $2.99 of $50 |
| Static checks | pytest, ruff, ruff format, mypy strict all clean; `docs/openapi.json` unchanged |

No performance or accuracy number is claimed for these controls. The tests show the behaviour (a
wrong key is refused and not echoed; a changed entry breaks the chain at that entry; a question
containing a key reaches neither the trace nor the audit log). They do not show that the scrubber
catches every secret or identifier.

## 3. Failures and open risks

- KF-048: the audit log is tamper-evident only; a full rewrite by the host operator is undetectable
  without an external anchor.
- KF-049: one shared key, no per-user identity, per-process rate limit.
- KF-050: the scrubber is pattern-based, and payload omission works on key names.
- Carried from Phase 7: KF-036 (scope gate misses one plain decision ask), KF-039 and KF-040
  (injection resistance at the model level is weaker than at the system level).
- Not done, by decision: the eval runner and smoke CLI do not write traces or audit entries (their
  run records already hold everything).

## 4. Decisions made on the owner's behalf

Listed in `DECISIONS.md` ("Phase 8"): JSONL spans instead of an OpenTelemetry collector; metadata-only
traces; hash-chained audit log; optional API key with a mandatory key for any network bind; open
`/v1/health`; regex scrubber; tests of existing injection controls instead of a prompt change.

## 5. Teach-me list

1. **Tamper-evident vs tamper-proof.** A hash chain proves that nothing before entry N changed since
   N was written, but only against someone who cannot rewrite everything. What makes it stronger?
2. **Why constant-time comparison and why compare digests.** What does a normal string comparison
   leak, and what does hashing first add?
3. **Defence at the system level.** Why the validator, not the prompt, is what stops a forged
   citation, and what that says about trusting model output.
