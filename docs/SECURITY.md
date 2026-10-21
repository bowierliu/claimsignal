# Security and observability

Scope: a portfolio system on synthetic and public data. It is built so the controls are real and
testable, but it has not been reviewed for use on real member data. Section 6 says what that would
still need.

## 1. What is protected, and from whom

| Asset | Threat | Control | Test |
|---|---|---|---|
| The answer boundary (no fraud, denial, coverage, or necessity decision) | A user, a retrieved chunk, or a tool result tells the model to decide | Scope gate before the model; evidence registry, citation, quote, and verdict-word checks after (`ANSWER_BOUNDARY.md`) | `test_agent_scope.py`, `test_agent_validator.py`, `test_agent_observability.py::test_an_injected_citation...`, Phase 7 safety cases |
| Citations | The model cites evidence it never retrieved, or a chunk it did not see | Every citation must resolve to an id in the run's evidence registry | `test_agent_validator.py` |
| API access | An unauthenticated or over-eager caller | `X-API-Key` (SHA-256 digest compare), per-caller token bucket, 401 and 429 bodies that never echo input | `test_api_access.py` |
| Network exposure | The service started on a network address with no key | `--host` outside loopback needs `--allow-remote` **and** a key; otherwise it refuses to start | `test_api_main.py` |
| Secrets | A key reaches a log, trace, audit entry, error, or commit | `.env` only; `obs.redact` on every logged string; payload-key omission; gitleaks in pre-commit; Cursor hook on shell commands | `test_obs_redact.py`, `test_obs_trace.py`, `test_obs_audit.py` |
| Personal identifiers | A phone, SSN, or email lands in a log | Same scrubber. All project data is synthetic; this is defence in depth | `test_obs_redact.py` |
| Audit trail | Someone edits, deletes, or reorders history | Hash chain with sequence numbers; `verify` names the first bad entry | `test_obs_audit.py` |
| Truth labels | The agent or API reads the answer key | `score.py` is the only module that opens truth; no agent, API, or obs module imports it | `test_agent_guards.py`, `test_tools_guards.py` |
| Spend | A loop or a caller runs up a bill | `CostGuard` on every paid call, per-investigation cap, hard caps in `budget/caps.toml` | `test_cost_guard.py`, `test_agent_loop.py` |

## 2. Observability

- **Traces** (`obs/trace.py`): one JSON line per finished span, in `data/traces/DATE.jsonl`
  (gitignored). Spans: `investigation` (root), `model_turn`, `tool_call`. Attributes are ids, names,
  versions, token counts, cost, status, and sizes. The loop passes the question's length, never its
  text. The field names map to OpenTelemetry (`OTEL_COMPATIBLE_FIELDS`) so a collector can be added
  without changing callers. A failed write is counted and never stops a run. The default is a no-op
  tracer.
- **Payload rule**: a key containing `question`, `prompt`, `text`, `content`, `body`, `answer`,
  `summary`, `quote`, `message`, `output`, `arguments`, `header`, `cookie`, `secret`, `password`,
  `key`, or `token` is replaced with `[omitted: payload key]` unless it ends in `_len`, `_count`,
  `_chars`, `_sha256`, `_version`, `_tokens`, `_usd`, or `_id`. Every string value is scrubbed and cut
  to 200 characters. An exception records its class only.
- **Audit log** (`obs/audit.py`, `data/audit/audit.jsonl`): one entry per guarded API request and one
  per investigation, including requests blocked by the scope gate. Fields: sequence, time, actor,
  action, subject, scalar details, previous hash, hash. Verify with
  `uv run python -m claims_copilot.obs.audit`. Appends take an exclusive file lock and fsync; an
  unreadable last line stops appending rather than forking the chain.
- **Run records** (Phase 5) still hold the full question, messages, and tool outputs for evaluation.
  They live in `data/runs/` (gitignored) and are the one place payload is kept on purpose.

## 3. API access control

- No key configured, loopback host: open, every request still audited (`anon:ADDRESS`). This is the
  development default.
- `CLAIMS_COPILOT_API_KEY` set: every route except `/v1/health` needs `X-API-Key`. The key is hashed
  at startup; comparison is `hmac.compare_digest` over digests, with no early exit.
- A refusal says "A valid API key is required." or "Too many requests." (with `Retry-After`). It never
  repeats the supplied key. The audit entry records the denial and the caller label, not the key.
- Rate limit: token bucket per caller, 120 requests per minute with a burst of 30 by default, at most
  10,000 callers tracked.
- All routes remain GET and read-only; `docs/openapi.json` is unchanged by the guard.

## 3a. Workbench page

Served at `/workbench` from three files in `src/claims_copilot/api/web/`, looked up in a fixed table
(no other file can be requested). Content security policy: `default-src 'none'`, scripts, styles,
and requests from this origin only, no framing, no inline code. The script writes API text only as
text nodes, uses a link only when it is `https:`, keeps the API key in the page field (not in
storage or a URL), and sends no ambient credentials. The page files are open because a browser
cannot send the key on a page load; they hold no data. Tests: `tests/test_api_workbench.py`.

## 4. Prompt-injection posture

The model is assumed to be steerable. The design does not rely on it refusing:

1. The user's question and all tool and retrieval text are passed as data in a delimited block, and
   the closing delimiter is stripped from the question.
2. The scope gate refuses decision requests before any model call.
3. The model has read-only tools from an allow-list; there is no write, send, or execute tool, so a
   hijacked model has nothing dangerous to call.
4. The answer is rejected unless every citation resolves to retrieved evidence, every quote is found
   verbatim in a retrieved chunk, and no statement contains verdict language.
5. Phase 7 measured this on planted chunks: on dev the model followed an injected instruction in 2
   of 6 runs of one case, and on test in 0 of 3 cases, and none reached the investigator (KF-039,
   KF-040). The scope gate has one known gap (KF-036).

## 5. Threats not covered, on purpose

- A malicious client of the API with a valid key can read everything the key allows. There is one
  role and no per-claim authorization.
- The rate limiter is per process. Behind several workers each has its own budget; limit at the load
  balancer too (Phase 10 sets this).
- The audit log is tamper-evident, not tamper-proof: someone who can rewrite the whole file can
  rebuild a valid chain. A deployment should also ship entries to storage the application cannot
  alter (for example write-once object storage), and record the latest hash elsewhere.
- Redaction is pattern-based. It will miss names, addresses, and free-text identifiers. Synthetic data
  has none; real data would need a reviewed scanner.
- No transport security: TLS terminates in front of the service (Phase 10).

## 6. What real member data would still need

A privacy and security review, a minimum-necessary access model with per-user identity (not one
shared key), encryption at rest, retention and deletion rules for traces and run records, a reviewed
PHI scanner, a business-associate agreement with every model provider, and logging that never
includes claim content. None of that is claimed here.
