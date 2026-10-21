# Final report

Status: Phases 0 to 11 complete. Phases 7 to 11 were built under the owner's standing instruction of
2026-10-20 (no per-phase approval gate). Nothing was pushed, deployed or published.

## 1. Executive summary

`claims-copilot` is a claims investigation assistant for a health plan, built only on synthetic data
and verified public sources. It helps a person assemble and assess evidence on a flagged claim. It
never decides fraud, denial, coverage or medical necessity.

It has three layers: retrieval over 23 verified public documents, deterministic tools over a
synthetic payer database, and a bounded model agent whose answers are checked by plain code
before anyone sees them. Around that sit a typed read-only API, an evaluation system, traces and an
audit log, a read-only workbench page, and container artifacts.

What is solid: the safety design (the validator, not the prompt, rejects forged citations and
verdict language), the provenance discipline (every source hashed and recorded), the deterministic
tools, and an evaluation that was pre-registered and run once on a held-out split.

What is not: two pre-registered targets were missed (unanswerable questions, judged faithfulness);
the judge was calibrated against labels drafted by another model, not by a person; the cases and
the generator share an author; the container was never built; the workbench was never opened in a
real browser; and no real claim data was ever used. These are listed below and in
`KNOWN_FAILURES.md`. Treat every number as evidence about this synthetic benchmark, not about a
production claims operation.

## 2. Architecture in one page

| Layer | What it does | Where |
|---|---|---|
| Sources | Fetch, hash and record public documents; redact CPT descriptors at ingest | `SOURCES/`, `src/claims_copilot/sources/`, `ingest/` |
| Retrieval | BM25 default; opt-in hybrid (BM25 + dense, RRF) with LLM rerank | `retrieval/` |
| Synthetic data | 4,000 members, 400 providers, 40,060 claims, five seeded anomaly types, answer key in a separate store | `synth/`, `DATA_MODEL.md` |
| Tools | Read-only, return findings with row ids, never a verdict | `tools/` |
| API | Typed FastAPI, committed OpenAPI contract, optional shared key, rate limit, audit | `api/`, `docs/openapi.json` |
| Agent | Scope gate, tool loop, evidence registry, answer validator, two provider adapters | `agent/`, `ANSWER_BOUNDARY.md` |
| Evals | Pre-registered cases, dev/test split by hash, judge, scorecards | `evals/`, `eval/`, `EVALUATION.md` |
| Observability | Payload-free JSONL traces, hash-chained audit log, scrubber | `obs/`, `docs/SECURITY.md` |
| Workbench | Static page at `/workbench`, strict CSP, text-only rendering | `api/web/` |
| Deployment | Dockerfile, entrypoint, compose, Fargate template (not built) | `Dockerfile`, `deploy/`, `docs/DEPLOYMENT.md` |

Fuller version: `docs/ARCHITECTURE.md`.

## 3. Metrics (all measured; method in `EVALUATION.md` and `RESUME_METRICS.md`)

| Area | Result | Sample | Caveat |
|---|---|---|---|
| Retrieval, hybrid + rerank | R@1 0.82, R@10 0.90 dev; 0.81 / 0.81 held-out. BM25: 0.33 / 0.80 dev, 0.25 / 0.44 held-out | 40 and 16 questions | Assistant-drafted gold sets (KF-006) |
| Tools, claim-level | 150 of 150 found, 0 decoys raised | 150 positives | Shares rule definitions with the generator (KF-018) |
| Tools, provider-level | 26 of 30, precision 100% | 30 positives | Four misses from peer contamination (KF-017) |
| Agent, seeded anomaly reported | 98.9% (Wilson 80% to 100%), 0 of 5 decoys | 15 seeded cases | Tiny n; assistant-written cases |
| Safety | 6 of 6 obfuscated decision asks blocked; injection followed 0 of 3, reached user 0 of 3; verdict language in a statement 0 | 17 safety cases | Dev split saw 2 of 6 injection runs followed (KF-039) |
| Unanswerable | 0.64 lexical (0.36 to 0.82), 0.60 hybrid. **Target 0.80 missed.** 0.87 counting a safe refusal | 13 cases | KF-035, KF-037, KF-042 |
| Judged faithfulness | 0.789 case mean (0.718 to 0.850). **Target 0.85 missed** | 42 cases, 1,509 statements | Judge calibrated against model-drafted labels (KF-041) |
| Judge calibration | Accepted by the registered rule: kappa 0.7535, false "supported" 2 (limit 2), minority class 28 | 169 statements | Agreement with another LLM, not a person. Conflict judge uncalibrated (8 < 10) |
| Validator rejections | 17 of 102 safety runs; 1 of 120 lexical end-to-end; 9 of 36 hybrid end-to-end | per run | Safe but unhelpful (KF-040, KF-044) |
| Hybrid vs lexical | No gain (gained 0, lost 1 of 19); about 2x cost and 3x latency. Default stays lexical | 19 paired cases | |
| API latency | Dossier p50 2.7 ms, p95 3.2 ms | 200 requests | One laptop, loopback, sequential |
| Tests | 686 passing; ruff, format, mypy strict, pre-commit clean | | |
| Secret scan | No leaks in 51 commits | | |

### Spend (ledger, `uv run python -m claims_copilot.budget`)

| Phase | Spent | Cap |
|---|---|---|
| 0 | $0.0166 | $3 |
| 5 | $0.1524 | $8 |
| 6 | $0.4693 | $8 |
| 7 | $2.3508 | $12 (live ceiling $4) |
| 8 to 11 | $0.00 | |
| **Total** | **$2.9890** | **$50** |

Cursor's own usage is not in this ledger and I cannot see it. Please check it.

## 4. Known failures that matter most

All 55 are in `KNOWN_FAILURES.md`. The ones an interviewer will go to first:

- **KF-041, labels are model-drafted.** The judge's calibration measures agreement with GPT Sol,
  which can share failure modes with the judge. Without the 19 "cannot tell" statements the minority
  class would be 9, under the registered 15. A person checking those 19, the 2 false-supported
  statements and the 8 conflict answers (about 20 minutes) would close most of this.
- **KF-042 and KF-043, two missed targets.** Reported, not tuned. Cases and thresholds were not
  edited after seeing results.
- **KF-035 and KF-037, the unanswerable test is weak and the scope gate over-blocks.** The gate
  refuses policy-reading questions that contain "covered", and misses one plain decision ask (KF-036).
- **KF-006, KF-011, KF-018, shared author.** Gold sets, cases and generator come from one author
  (the assistant), so results show consistency, not realism.
- **KF-039, injection resistance is stronger at the system level than at the model level.**
- **KF-048 to KF-050, security limits.** Tamper-evident not tamper-proof; one shared key; pattern
  scrubber is not a PHI scanner.
- **KF-051 to KF-055, product and deployment gaps.** The workbench does not show the agent's cited
  summary; never opened in a real browser; image never built; audit volume ephemeral on Fargate; no
  policy search in the container.

## 5. Decisions made on the owner's behalf

The owner's standing instruction (2026-10-20, 4:04 PM) was to approve every recommended decision.
All are in `DECISIONS.md` with options and reasons. The significant ones:

1. **Label provenance (amendment A4).** The label source for judge calibration changed from owner
   hand labels to labels drafted by GPT Sol. The owner's review field was left blank, so I recorded
   "form check only, content review not stated" and treated the labels as unreviewed. Rows carry
   `label_source` and `owner_review`; no row carries the owner's identity. Thresholds, cases and the
   sample did not change. Consequence: faithfulness numbers are weaker evidence (KF-041).
2. "Cannot tell" counts as not supported (the registered rule), with a sensitivity analysis shown.
3. Judge accepted, so the test split was judged (cost $0.23).
4. Default search stays lexical (hybrid gave no gain at twice the cost).
5. No `agent_v2` prompt: conflict reports are rare and uncalibrated, and a change needs an eval.
6. Missed targets reported, not tuned.
7. Phases 8 to 11 started without separate approvals.
8. Phase 8: JSONL spans and a hash-chained log rather than an OpenTelemetry collector; mandatory key
   for any non-loopback bind.
9. Phase 9: static page, read-only, no "investigate" button.
10. Phase 10: artifacts only, no live deployment, no policy corpus or answer key in the image.
11. Retrieval-only unanswerable layer not run (KF-047).

## 6. Pre-publish checklist (`ROADMAP.md`)

| Item | Status |
|---|---|
| gitleaks over full history | Done: no leaks in 51 commits |
| `data/raw/` and third-party sources not committed | Done: no sqlite, PDF, csv or zip tracked; `data/` ignored |
| Employer-specific content scan | Done for what I can check: no named health-plan companies, no absolute home paths in tracked files. I do not know the employer's name or internal terms, so the owner should read the repository once for anything I cannot recognise |
| Licence decision | **Open (owner)** |
| Product name: real trademark search | **Open (owner)** |
| Public vs private | **Open (owner)** |
| GitHub | Deferred by owner; the owner publishes |
| Build the container and open the workbench in a real browser | Not done (KF-052, KF-053) |

## 7. Interview preparation

**Why did you build it this way: three layers?**
Exact questions (does this claim exceed a unit limit?) should have exact answers from tested code;
policy questions need retrieval with a source; only the writing of a summary needs a model. Each
layer fails differently and is tested differently.

**How do you stop it deciding fraud?**
Three independent lines: a scope gate before any model call (6 of 6 obfuscated asks blocked), tool
outputs that carry findings and no verdict field, and a validator that rejects answers with verdict
language. The prompt is the weakest of the three, and the evaluation says so (KF-039).

**How do you know a citation is not made up?**
Every citation must resolve to something the run actually retrieved, and quotes must appear verbatim
in that text. Result: 0 fabricated citations in shown answers on the test split. Note this proves the
citation exists, not that the passage supports the claim; the judge covers support, with the caveat
in KF-041.

**Your faithfulness number missed its target. What now?**
Report it, do not edit the target or the cases. 0.789 against 0.85. Of the unsupported share, 6.0% is
"cannot tell" from the display cut-off, 9.0% "partly", 0.4% "not supported". The cut-off is a
measurement artefact worth fixing; the "partly" share is where the judge is stricter than the labels.

**Why is the judge result weak evidence?**
It was calibrated on labels written by another LLM. Kappa 0.75 means they agree, not that either is
right. Fix: a person labels the 19 + 2 + 8 items and `evals.calibrate` is re-run.

**What is pre-registration and did you keep to it?**
Thresholds, cases and the split were fixed and committed before any provider call; the test split
was run once per configuration. Amendments A1 to A4 are logged in `DECISIONS.md`; A4 (label source)
was made before the test split was run, and its consequence is stated there.

**Hybrid retrieval and reranking: why not the default?**
On the Phase 6 retrieval set the reranker lifted R@1 from 0.33 to 0.82. At the agent level it gained
0 of 19 paired cases, cost about 2x, tripled latency, and 25% of its end-to-end runs were rejected.
Retrieval metrics did not predict end-to-end value.

**What is the biggest risk if this touched real claims?**
Real members' data. Controls exist (payload-free traces, scrubber, audit chain, key, read-only
container) but they are one shared key, a pattern scrubber and a tamper-evident log, which a real
deployment would need to replace with identity, per-claim authorization, a PHI scanner and an
external audit sink. No real data was used or should be.

**What would you do with another week?**
Human labels for calibration; a second, independently written case set; fix the scope-gate
over-block; build and run the container; real-browser and accessibility pass; show the agent's cited
summary in the workbench behind a cost cap.

## 8. Teach-me list

1. **Why a missed target is reported, not patched** (pre-registration).
2. **Why agreement between two LLMs is weaker than agreement with a person.**
3. **Why "the validator, not the prompt" is the safety boundary.**

Please confirm you understand these before choosing what comes next.
