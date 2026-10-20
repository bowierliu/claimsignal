# Phase 5 plan: bounded agent workflow

Status: **proposed, awaiting owner approval.** No Phase 5 code or dependencies have been added.
Four decisions are open (see "Decisions I need from you").

## Goal

Given one flagged claim (or one investigator question about it), a model reads the Phase 3 tool
results and Phase 4 policy search through a small, bounded loop and writes a **cited evidence
summary**. Plain code then checks the model's output. If the checks fail, the output is not shown
as an answer. The agent never decides fraud, denial, coverage, or medical necessity; it assembles
and describes evidence for the human.

This phase delivers the loop, the two provider adapters, the answer boundary, a first versioned
prompt, and a small live smoke run. It does not deliver the full eval (Phase 7) or better
retrieval (Phase 6).

## Scope

In scope (all under `src/claims_copilot/agent/`, plus `prompts/`):

- A bounded tool-calling loop over the 10 analysis operations that `GET /v1/tools` lists. The model
  can call only those; every call goes through the Phase 4 contract and its input validation.
- One swappable provider interface with an OpenAI adapter and an Anthropic adapter. Every paid call
  goes through `CostGuard`.
- The answer boundary from `ANSWER_BOUNDARY.md`, finalised and implemented: typed output, evidence
  registry, deterministic validator, request-scope gate.
- One versioned runtime prompt, `prompts/agent_v1.md`.
- Run records: every investigation writes one JSON file (messages, tool calls, evidence, usage,
  validation result) to gitignored `data/runs/`.
- Tests with a scripted fake provider: no network, no spend.
- A small live smoke run to show both providers work end to end (cost below).

Out of scope: dense or hybrid retrieval and reranking (6), the 100-case eval, LLM judge, and
calibrated provider comparison (7), tracing UI, audit log, auth and rate limits (8), the workbench
(9), deployment (10). No tool is added; no write operations exist anywhere.

## Design

```
investigator question + claim id
        |
  [1] scope gate (plain code)  -- blocked ask --> OUT_OF_SCOPE, no model call
        |
  [2] loop (max 8 model turns, max 12 tool calls)
        model turn -> tool calls -> API (in-process) -> results -> evidence registry
        |
  [3] model returns ONE structured answer (JSON schema)
        |
  [4] validator (plain code) -- fail --> INVALID_OUTPUT (not shown as an answer)
        |
  cited evidence summary + run record
```

### Trust boundary

The model's output and all retrieved or tool text are untrusted. The model has no write path, no
shell, no file access, and no free-text query path to data: its only abilities are the allow-listed
read-only operations, whose arguments are validated by the same patterns as the API. Retrieved
policy text is passed inside clearly delimited blocks with the instruction that it is data. A
prompt injection can at worst change the wording of the model's answer, so the validator, not the
prompt, is the defence.

### Evidence registry

The runtime, not the model, names evidence. Every tool result gets an id (`E1`, `E2`, ...) and each
finding or observation inside it an id (`E1.f1`, `E1.o1`). Every policy hit keeps its `chunk_id`.
The model may cite only ids that exist in this run's registry. This is what "every citation must
resolve to a retrieved id" means in practice, and it extends the brief's `chunk_id` rule to tool
results (the brief only mentions chunks).

### Output contract (what the model must return)

```
status:     ANSWERED | CONFLICTING_EVIDENCE | INSUFFICIENT_EVIDENCE | OUT_OF_SCOPE
reason:     typed enum (below)
summary:    short list of statements; each statement = {text, citations[]}
policy_quotes: optional list of {chunk_id, quote}   # quote must be verbatim from that chunk
searched:   what was searched/looked up (required when INSUFFICIENT_EVIDENCE)
```

`INVALID_OUTPUT` is never produced by the model; only the validator assigns it. Reason enum
(proposal): `SUPPORTED`, `SOURCES_DISAGREE`, `NO_RELEVANT_SOURCE`, `TOOL_ERROR`, `STEP_LIMIT`,
`BUDGET_LIMIT`, `REQUEST_BLOCKED`, `SCHEMA_VIOLATION`, `UNRESOLVED_CITATION`,
`VERDICT_LANGUAGE`, `QUOTE_NOT_FOUND`.

### Validator rules (all plain code, all tested)

| # | Rule | On failure |
|---|---|---|
| 1 | Output parses against the schema; status and reason are enum members | `INVALID_OUTPUT` / `SCHEMA_VIOLATION` |
| 2 | Every citation id exists in this run's registry | `UNRESOLVED_CITATION` |
| 3 | `ANSWERED` has at least 1 citation; `CONFLICTING_EVIDENCE` at least 2, from at least 2 distinct sources or tool results | downgraded to `INVALID_OUTPUT` (never silently upgraded) |
| 4 | Every `policy_quotes[].quote` appears verbatim in the cited chunk text | `QUOTE_NOT_FOUND` |
| 5 | No statement contains verdict language (the Phase 3/4 word list, plus phrases such as "should be denied", "is fraudulent") | `VERDICT_LANGUAGE` |
| 6 | Every statement has at least 1 citation (uncited prose is not allowed in `summary`) | `UNRESOLVED_CITATION` |
| 7 | `INSUFFICIENT_EVIDENCE` and `OUT_OF_SCOPE` carry no evidence framed as a conclusion, and `OUT_OF_SCOPE` needs a `REQUEST_BLOCKED` reason | `INVALID_OUTPUT` |

What rule 2 and 4 do **not** prove: that a cited finding actually supports the sentence next to it.
That semantic check needs a judge and hand labels, so it belongs to Phase 7; until then it is a
named limit in `KNOWN_FAILURES.md`, not a claim.

### Request-scope gate

Runs before any model call. Blocks asks to decide fraud, denial, coverage, or medical necessity
(for example "is this fraudulent", "should we deny", "is this medically necessary", "approve or
reject") and returns `OUT_OF_SCOPE` / `REQUEST_BLOCKED` with a fixed explanation that offers the
allowed alternative ("here is the evidence for this claim"). It is conservative: an ambiguous ask
may be blocked, and that false-block rate is measured, not assumed. The post-generation rule 5 is
the second line, so the model cannot talk its way past the gate.

### Loop bounds

| Bound | Value (configurable, default) | When hit |
|---|---|---|
| Model turns | 8 | stop, summarise what was gathered, `STEP_LIMIT` |
| Tool calls | 12, and no identical call repeated | extra repeats return the earlier result id, not a new call |
| Output tokens per turn | 1,500 | provider cap |
| Cost per investigation | $0.15 (checked before each call) | stop, `BUDGET_LIMIT` |
| Wall time per investigation | 60 s | stop, `STEP_LIMIT` |
| Tool errors | error text goes to the model as data; 3 in a row stops the run | `TOOL_ERROR` |

Limit stops still run the validator on whatever answer exists; a run that hits a limit before
producing any answer ends as `INSUFFICIENT_EVIDENCE` with the limit named, not as a guess.

### Provider adapter

One small interface: `complete(messages, tools, schema) -> ModelTurn` where `ModelTurn` holds text,
tool calls, stop reason, and token usage in one normalised shape. Two adapters translate to each
provider's message and tool-call format. They use `httpx` (already a dependency, mockable with
`httpx.MockTransport`, same as `retrieval/embed.py`) instead of the vendor SDKs, so there are no
new dependencies and the cost guard wraps one place. The exact request formats, model ids, and
structured-output options are **checked against the providers' current documentation before use**,
not written from memory.

### Cost control

- Chat-model prices are not yet in `budget/prices.toml` (only the embedding model). Each model I use
  needs a price with a VERIFIED manifest source; Anthropic's pricing page is not in the manifest yet.
  `source-verifier` fetches both pricing pages first; I add entries to `prices.toml` only, never
  `caps.toml`.
- The default model for development is the cheapest adequate one per provider; the owner approves
  the two model ids after I show their verified prices (decision 2 below).
- Tests use the scripted fake provider. Live calls happen only in the smoke run.

### Tool results as model input

Tool results are large. The runtime sends the model the API's JSON, but trims `detail` pairs above
a size limit and says so in the message ("truncated; N more"). Claim ids and counts are never
truncated. The trimming rule is tested so that nothing cited can be trimmed away.

### Prompt

`prompts/agent_v1.md`, written in the structured form AGENTS.md requires: role, context, inputs,
constraints, output schema, two examples (one `ANSWERED`, one `INSUFFICIENT_EVIDENCE`), and failure
behaviour. It is versioned; any later change needs an eval comparison recorded in `DECISIONS.md`.
Phase 5 records v1 as the baseline only.

## Tests

All in-process; scripted fake provider returns canned turns.

- Loop: stops at each bound; dedupes repeated calls; never calls a tool outside the allow-list;
  rejects malformed arguments (the API's validator is the check); a tool error reaches the model as
  data.
- Validator: one test per rule, including a fabricated citation, an `ANSWERED` with zero citations,
  a `CONFLICTING_EVIDENCE` with one, a quote that is not in the chunk, and verdict language.
- Scope gate: a list of blocked asks and a list of allowed asks that look similar (false-block
  cases are listed in `KNOWN_FAILURES.md`, not edited away).
- Injection: policy chunks and tool strings containing "ignore previous instructions", fake
  citations, and requests for a verdict. The test asserts the validator outcome, not the model's
  behaviour, because the fake provider is scripted to obey the injected text.
- Provider adapters: request and response shapes with `MockTransport`; usage mapping into
  `CostGuard`; refusal when a model has no verified price or a cap would be exceeded.
- Truth isolation: the agent package may not import `tools/score.py`, `synth.store.load_dataset`,
  or contain truth tokens (the Phase 3/4 static test is extended to `agent/`).
- Records: a run record contains no secret, no request header, and no auth-failure body.

## Live smoke run (the only paid step)

10 flagged claims chosen by a fixed seed from the default dataset, plus 4 scripted adversarial asks
(2 out-of-scope, 1 prompt injection in a policy question, 1 question the corpus cannot answer),
run once on each provider (28 investigations). Reported per provider: validator pass rate, status
mix, turns, tool calls, tokens, latency, cost. This is a **smoke run, not an eval**: 14 cases per
provider cannot support quality claims, and the report will say so. It also is not a measurement
of end-to-end correctness against ground truth; that is Phase 7.

Estimated cost: at most 28 runs x the $0.15 per-investigation ceiling = **$4.20 as a hard upper
bound**, and a realistic few cents each; I will give the number from verified prices before running.
I propose a ceiling of **$3.00 for Phase 5 live spend** inside the $8 `p5` cap, leaving the rest for
retries and prompt iteration. The eval-run cap is $5, so the smoke run fits within it.

## Build order (after approval)

1. `source-verifier`: fetch OpenAI and Anthropic pricing pages and current model/tool-calling docs
   into the manifest; I add verified entries to `prices.toml`; owner approves model ids.
2. Agent types: `ModelTurn`, `ToolCall`, evidence registry, answer schema, enums (finalise
   `ANSWER_BOUNDARY.md`).
3. Validator and scope gate, with their tests first.
4. Tool runner over the in-process app (decision 3), allow-list taken from `GET /v1/tools`.
5. Loop with bounds and the scripted fake provider; run records.
6. Provider adapters and `CostGuard` wiring, with `MockTransport` tests.
7. `prompts/agent_v1.md` and the smoke-run harness (dry run prints the estimate and refuses to
   spend without `--confirm`, like `retrieval.dense`).
8. Run the smoke test after I state the verified-price estimate and you say go.
9. Update `ANSWER_BOUNDARY.md`, `docs/ARCHITECTURE.md`, `DECISIONS.md`, `EVALUATION.md`,
   `KNOWN_FAILURES.md`, `README.md`, `AGENTS.md`, `RESUME_METRICS.md` (measured numbers only), then
   `docs/PHASE5_REPORT.md`.

## Budget check against `budget/caps.toml`

Cap `p5` is $8.00; total spent is $0.0166 of $50. Planned live spend is at most $3.00 and is
authorised call by call by `CostGuard`; nothing is spent before step 8. The warn and stop fractions
apply (70% and 90% of the phase cap), and I will not edit `caps.toml`. As always, please check
Cursor's own usage yourself; I cannot see it.

## Exit criteria

- The loop, validator, scope gate, and both adapters are implemented and every rule above has a
  passing test; no network or spend in the test suite.
- Smoke run done with per-provider results recorded as measured, with the date, commit, and model
  ids; failures recorded in `KNOWN_FAILURES.md`.
- No agent output is shown as an answer unless the validator passed; verified by test.
- `pytest`, `ruff`, `ruff format --check`, `mypy`, and pre-commit green; docs and `DECISIONS.md`
  updated; phase report written; no Phase 6 work started.

## Risks

- **Citations that exist but do not support the sentence.** The validator proves existence and
  verbatim quotes, not meaning. Named limit until the Phase 7 judge.
- **Weak retrieval caps answer quality.** BM25 recall on paraphrases is 0.25 (KF-021); the agent
  will often return `INSUFFICIENT_EVIDENCE` for reworded questions until Phase 6. That is the
  correct failure, and the smoke run will show how often.
- **Verdict language by paraphrase.** A word list misses new phrasings. It is a floor, not a proof;
  Phase 7 safety cases will measure it.
- **Scope gate false blocks and misses.** Rules are conservative and will refuse some legitimate
  asks and could miss odd phrasings; both rates are measured in tests and later in Phase 7.
- **Provider API drift and model id retirement.** Formats and model names change; adapters are
  small and tested against recorded fixtures, and ids come from the verified docs.
- **Provider behaviour differs.** Tool-calling and structured-output support differ, so the two
  adapters may need different prompt wording; if so, the difference is recorded, not hidden.
- **Cost surprises from long tool outputs.** Mitigated by trimming, the per-investigation ceiling,
  and pre-call estimation (the guard's estimate is conservative).
- **Secrets.** Both keys are present in `.env` (checked only with `has_secret`); headers and
  auth-failure bodies are never logged or put in run records.
- **Run records may contain synthetic claim data.** They stay local in `data/runs/` (gitignored).

## Decisions I need from you

1. **Orchestration.**
   - A (recommended): a plain tool-calling loop with an explicit state and the bounds above. About
     a few hundred lines, no new dependency, every step testable and visible in the run record.
   - B: a graph framework (for example LangGraph). Gives checkpointing and graph visuals, but adds a
     large dependency and hides the loop behind its abstractions; fixed bounds are harder to prove.
2. **Providers in Phase 5.**
   - A (recommended): build both adapters and run the smoke test live on both (one cheap model each,
     about $3 ceiling). Proves the swap works and gives a first, small comparison.
   - B: live on OpenAI only; the Anthropic adapter is tested with mocks and goes live in Phase 7.
     Cheaper, but the swap claim is unproven until then.
   - C: Anthropic only live.
3. **Request-scope gate.**
   - A (recommended): deterministic rules before the model, plus the post-generation verdict check.
     Free, auditable, conservative; will over-block some asks.
   - B: add a cheap model call to classify the request. Handles paraphrases better but costs money,
     is itself manipulable, and needs its own eval; better as a Phase 7 experiment.
4. **`httpx2` (KF-022).**
   - A: add `httpx2` to the dev dependency group only (Starlette's recommended test client library),
     drop the warning filter, record the hash. It is Pydantic-stewarded and about 5 months old; it
     would also pull `httpcore2`, `truststore` and others into the test environment.
   - B (recommended): keep plain `httpx` and the filter. The only effect is a silenced test
     warning, runtime calls (including the new key-carrying provider calls) keep the long-established
     package, and I revisit when Starlette drops the fallback.
   - C: adopt `httpx2` everywhere, including runtime. Not recommended while its release history is
     this short.

## Teach me

The teach-me list for Phase 5 will accompany the report. Pending from earlier: the Phase 4 list in
`docs/PHASE4_REPORT.md`; use `/teach <concept>` for any of them.
