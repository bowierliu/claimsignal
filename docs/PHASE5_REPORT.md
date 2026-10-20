# Phase 5 report: bounded agent workflow

Status: **awaiting owner approval.** Plan approved 2026-10-20; models `a_cheap` chosen by the owner.
Code is commit `133e3d4`; this report and the doc updates follow it.

## 1. Executive summary

Phase 5 added the third layer: a model that calls the Phase 4 API and policy search, then writes a
cited evidence summary, with plain code checking the result before anyone sees it.

- **Loop** (`src/claims_copilot/agent/loop.py`): a plain tool-calling loop with hard bounds: 8 turns,
  12 tool calls, 60 seconds, $0.15 and 100k prompt tokens per investigation, repeated identical
  calls answered from memory, 3 consecutive tool errors end the run. A limit ends the run with a
  typed status; it never raises and never guesses.
- **Tools**: called through the in-process API, only the operations listed by `GET /v1/tools`.
  Identifier arguments are validated before they become a URL path (a test caught `C0000001/dossier`
  being routed to a different endpoint).
- **Answer boundary** (`ANSWER_BOUNDARY.md`, now implemented): a deterministic scope gate before the
  model ("is this fraud?", "should we deny it?" cost nothing and call no model); after the model, an
  evidence registry that names every citable id, a schema check, status/reason agreement, citation
  counts, verbatim quotes, and a verdict-word scan. Failure means `INVALID_OUTPUT`, shown as
  invalid, with the record kept.
- **Two adapters** over `httpx`, no vendor SDK: OpenAI `gpt-6-luna` (Responses API) and Anthropic
  `claude-haiku-5-5` (Messages API), $0.10 / $0.50 per 1M tokens, prices VERIFIED in the manifest.
  Every model call goes through `CostGuard`; a test fails if anything else calls a provider.
- **Live smoke test**: 28 investigations per run (14 cases x 2 providers), run twice. The first run
  found a real defect of mine: flags had ids in the registry but were shown to the model without
  them, so Anthropic cited the raw `flag_id` and lost all 10 claim answers to the validator. I fixed
  it (flags now carry `E1.s1`); run 2 followed.

| Claim investigations shown after validation (10 per provider) | Run 1 | Run 2 (after fix) |
|---|---|---|
| OpenAI `gpt-6-luna` | 7 | 8 |
| Anthropic `claude-haiku-5-5` | 0 | 9 |

Both providers resisted the injection case without writing a verdict or a fake citation. Both
out-of-scope asks were blocked before any model call. This is a smoke test of 14 cases per provider,
one sample each. It shows the loop works. It does not show the answers are right, and it cannot rank
the two models.

## 2. Metrics and spend vs cap

| Item | Value |
|---|---|
| Tests | 426 passing (128 of them agent tests); no network, no spend |
| Quality gates | ruff, ruff format, mypy strict, gitleaks, pre-commit green; no `--no-verify` |
| Cost per investigation that reached a model (run 2) | OpenAI mean $0.0013; Anthropic mean $0.0022; 2 to 3 turns, 1 to 2 tool calls |
| Latency (run 2) | OpenAI median 6.8 s, max 21 s; Anthropic median 6.1 s, max 12 s |
| Limits hit | none (no turn, tool, time, or cost limit ended a run) |
| Phase 5 spend | **$0.0877 of the $8.00 `p5` cap**; total $0.1043 of $50. The $3.00 smoke ceiling was never close |

My estimate before running was about $0.0075 per investigation; measured values are 3 to 6 times
lower because the dossier answers need one tool call and two turns. Reminder: please check Cursor's
own usage yourself; agents cannot see it.

## 3. Failures and open risks

Details and evidence in `KNOWN_FAILURES.md`.

- **KF-023.** A PDF drop-cap is extracted as "N CCI", so a correct quote fails the verbatim check.
- **KF-024.** A flag and a check from one dossier count as one source, so a "flag says X, check found
  nothing" `CONFLICTING_EVIDENCE` answer is rejected. Whether that mismatch is a conflict at all is a
  Phase 7 labelling question.
- **KF-025.** A correct `INSUFFICIENT_EVIDENCE` answer was discarded because one `searched` item
  was over 200 characters.
- **KF-026.** The validator cannot tell a thin answer from a good one. OpenAI answered the
  unanswerable helicopter question as `ANSWERED` with honest quotes, where `INSUFFICIENT_EVIDENCE`
  was better; Anthropic refused the injection case outright, which is over-refusal.
- **KF-027.** Results vary between runs and between models; 14 cases cannot settle either.
- **KF-028 (fixed).** The flag-id defect above.
- **Not production-ready.** Prompt injection is tested with one case, not a suite (Phase 7 and 8).
  The scope gate is a pattern list: it will miss rephrasings and may block fair questions; its
  over-blocking rate is not yet measured.
- **Retrieval limits carry through.** BM25 only (KF-021); Phase 6 improves it.
- **Process note.** I rewrote one test that I had written wrongly (it matched a docstring). I did
  not change any corpus, gold set, or test to make a failing case pass; the three loosening changes
  below are waiting for you.

## 4. Decisions needed

1. **Quote matching (KF-023).**
   - A (recommended): compare quotes with all whitespace ignored, with a test that a changed word
     still fails. Fixes the split-letter artifact; it cannot make a wrong sentence pass.
   - B: keep strict and fix the drop-cap at ingest in Phase 6 (re-extraction changes chunk ids and
     hashes).
   - C: keep strict and accept the loss.
2. **Flags as a source (KF-024).**
   - A (recommended): a screen flag is its own source, because the screen and the checks are
     different mechanisms, so "flag versus check" can be reported as `CONFLICTING_EVIDENCE`.
   - B: keep one source per tool result; such answers stay invalid.
3. **`searched` list (KF-025).**
   - A (recommended): the runtime fills `searched` from its own tool log and ignores the model's.
   - B: raise the limit to 400 characters.
   - C: keep.
4. **Approve Phase 5 as built**, including KF-023 to KF-028, so I can propose the Phase 6 plan
   (retrieval upgrades). I will not start Phase 6 before you approve that plan. Any change for 1 to
   3 also changes validator behaviour, so I would rerun the smoke test once (about $0.04) to show
   the effect, and record it.

## 5. Teach me

1. **Why the runtime, not the model, names the citable ids.** If the model chose its own citation
   labels, "cited" would only mean "wrote something that looks like a citation". Handing out ids after
   the data is trimmed means a citation proves the model was shown that evidence. Run 1 is the
   example: the ids existed but were not shown, and every answer was correctly refused.
2. **Smoke test versus evaluation.** A smoke test asks "does it run end to end?" with a few cases;
   an evaluation asks "how often is it right?" with enough labelled cases to say. Our 14 cases
   per provider cannot support a claim about quality or about which model is better.
3. **Fail closed, and what it costs.** A strict validator turns doubtful answers into
   `INVALID_OUTPUT` instead of showing them. That is the safe default for this domain, but it also
   discards some correct answers (KF-023, KF-025). Each rule is a trade between false accepts and
   false rejects, and Phase 7 is where the trade gets measured.

Please confirm you understand these before I propose Phase 6.
