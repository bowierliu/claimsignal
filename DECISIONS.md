# Decisions

Each entry: options considered, choice, and why. Newest last.

## 2026-10-13: Kickoff decisions (owner-approved)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Budget | $50 total / $5 per eval run vs. other | $50 / $5, per-phase caps in `budget/caps.toml`, $10 reserve | Owner approved the proposed split |
| Sequencing | Thin bootstrap first; swap Phases 0 and 1; free-only Phase 0 | Thin bootstrap (tooling + cost guard) before any paid call | Phase 0 spends money, so the cost guard must exist first |
| Vault isolation | Ignore project in vault repo; leave it | Added `hc_claims_investigator/` to vault `.gitignore` | Keeps the project's own repo from being embedded in the vault repo |
| Default branch | main; master | main | Convention |
| Python | 3.11; 3.12; 3.13 | 3.12 via uv | Broadest library support |
| Secret scanning | gitleaks via pre-commit; gitleaks binary; detect-secrets | gitleaks v8.30.1 via pre-commit, plus a Cursor `beforeShellExecution` hook | No Homebrew/Go on this machine; pre-commit builds the toolchain. The hook keeps credentials out of shell history |
| Baseline embeddings | OpenAI text-embedding-3-small; local model; Voyage | text-embedding-3-small | Verified at $0.02 per 1M tokens (`openai-api-pricing`); alternatives compared in Phase 6 |
| Licensed code files | Local-only; synthetic-only; decide per file | Raw files local and gitignored; commit manifest, hashes, fetch scripts | Reproducible without redistributing licensed content |
| Gold retrieval labels | Agent drafts + owner reviews; owner writes; LLM drafts | Agent drafts, owner reviews and approves each label | Hand-verified labels without owner writing them all |
| Phase 0 vector storage | Flat numpy index; real store now | Flat numpy index on disk | Defers the vector-storage gate to Phase 6 with a measured baseline |
| `/teach`, `/phase-report` | Skills with `disable-model-invocation`; legacy `.cursor/commands` | Skills | Cursor docs migrate commands to skills; command location is undocumented |
| file-scout model | composer-2; other; inherit | composer-2 | Cheap and fast; read-only |
| Old-repo archive | Exclude secrets and venv; exclude venv; everything | Exclude `.env`, `.venv`, caches | No secrets in archives |
| Old API key | Rotate; reuse | Owner revokes it and creates a fresh, spend-limited key | Limits blast radius |
| Product naming | Phase 1; now | Phase 1, working name `claims-copilot` | Name lives in `src/claims_copilot/project.py` |
| Adjacent vault folders | Off-limits; read cms_data_mcp | Off-limits | Avoids any employer-specific contamination |
| Raw fetched files | Commit; gitignore | `data/raw/` gitignored for all sources | Uniform rule; sizes and license terms vary |

## 2026-10-15: Git tooling and GitHub publication

- **Git upgrade:** git 2.24.3 could not run pre-commit (`ls-files --deduplicate`) or commit
  (`--trailer`). Options were Command Line Tools download, Homebrew, or conda. The owner chose the
  Apple Command Line Tools; they are now 14.3.1 with git 2.39.2 (Apple Git-143), verified by
  `git --version` on 2026-10-15. Conda was rejected: the 2022 Anaconda install crashes on an
  OpenSSL mismatch.
- **GitHub deferred (owner decision):** no remote is added to this repo and no push is made. The
  owner will publish himself when the project is finished, as a resume showcase. Agents must not
  add a remote, ask for SSH or repo setup, or use a browser on GitHub.
- **Publish to GitHub at project end.** Pre-publish checklist:
  1. Run gitleaks over the FULL git history.
  2. Make the license decision (open gate).
  3. Confirm `data/raw/` is still gitignored and no third-party source files are committed.
  4. Decide public vs private (the owner earlier said private; a resume showcase normally
     needs public).
  5. Scan docs and data for any employer-specific content.
- **Vault repo:** its `origin` was switched to an SSH URL, so the credential that was embedded in
  the old URL is gone from that config. The owner revokes the old token. The vault `.gitignore`
  edit (`hc_claims_investigator/`) is still uncommitted in the vault repo.
- **Local `.env`:** created from `.env.example` with empty values (mode 600, gitignored). The
  owner pastes a fresh OpenAI key himself, never in chat. Before the first paid call, check the
  variable is non-empty without printing it.

## 2026-10-15: Phase 0 corpus decisions (owner-approved)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Seed source list | All 23; smaller start; changes | All 23 (NCCI manual 4, Claims Processing 5, Program Integrity 5, OIG 6, eCFR 2, ICD-10-CM FY27 guidelines 1) | Covers the Phase 0 retrieval domains; tables and code files wait for Phase 3 |
| CPT descriptors found in documents | Redact at ingest and log; exclude document; report first | Redact descriptor text at ingest and log every redaction in the manifest | Keeps useful policy prose while honoring hard rule 3 |
| Sources with unreadable terms (OIG, eCFR, NCBI) | Record as UNVERIFIED and fetch for local use; skip | Fetch locally, terms UNVERIFIED, noted as US government works; raw files gitignored | Terms pages sit behind CAPTCHAs or JavaScript; nothing is redistributed |
| Gated content | Accept licenses; leave gated | Not accepted. Coverage Database LCDs/articles, PTP and MUE tables are out of scope for now | A GET to the Coverage Database license endpoint returns an access token, so no GETs there without the owner |
| Deferred API clients | Build all now; build when needed | eCFR client now; data.cms.gov and NCBI E-utilities clients when a phase first needs them | No Phase 0 source uses them |

## 2026-10-13: Cost guard design

- **Options:** per-call wrapper with pre-call estimate and ledger; provider-dashboard limits only;
  post-hoc ledger without refusal.
- **Choice:** a single `CostGuard.call()` wrapper. It prices the call from `budget/prices.toml`,
  checks the total, phase, and eval-run caps, refuses any call that would exceed a cap, warns at
  70%, refuses at 90% unless the owner lists the scope in `approved_past_stop`, and appends every
  call to `budget/ledger.jsonl`.
- **Why:** the refusal happens before money is spent, and the ledger is auditable in git.
- **Conservative choices:** tokens are estimated at 1 per 3 UTF-8 bytes (an overestimate for
  English); failed calls are charged at their estimate; models without a verified price are
  refused.

## 2026-10-16: Phase 0 approval (owner)

- **Phase 0 approved**; Phase 1 started.
- **Gold set** (`eval/phase0_retrieval_gold.jsonl`): owner chose to accept it as provisional
  rather than review every label now. Recorded as KF-006 in `KNOWN_FAILURES.md`; Phase 7 adds
  hand-labelled cases and judge calibration. This supersedes the earlier "owner reviews each
  label" default for Phase 0 only.
- **Phase 6 starting point:** hybrid BM25 + dense, measured against the Phase 0 numbers.

## 2026-10-16: Phase 1 foundation (agent defaults unless marked)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Cursor customization locations | Follow current docs; follow memory | Rules in `.cursor/rules/*.mdc`, skills in `.cursor/skills/<name>/SKILL.md`, subagents in `.cursor/agents/*.md`, hooks in `.cursor/hooks.json`, checked against cursor.com docs on 2026-10-16 | The docs are the source; only the custom-command location is undocumented, which is why `/teach` and `/phase-report` are skills with `disable-model-invocation` |
| `eval-runner` subagent | Create now; create in Phase 6/7; never | Create in Phase 6/7 (owner decision, 2026-10-16) | Until real evals exist, the `eval-running` skill and the cost guard cover Phases 0 to 5 |
| CI | GitHub Actions file now; none until publish | `.github/workflows/ci.yml` running ruff, mypy, pytest with pinned action versions (checkout v7.0.1, setup-uv v10.3.0, latest releases observed 2026-10-16) | Ready for publish. Not exercised: there is no remote. Full-history gitleaks stays a manual pre-publish step |
| Structure guard | Trust the files; test them | `tests/test_repo_structure.py` checks skill/agent/rule frontmatter, record files, and doc links | Cursor silently ignores misnamed rules and skills |
| Records | Create as phases need them; create now | All records exist now. Unbuilt parts (`ANSWER_BOUNDARY.md`, `DATA_MODEL.md`, planned layers) are labelled design or not designed | Keeps the working agreement concrete without claiming unbuilt features |

## 2026-10-16: Product naming (owner decision)

- **Options:** choose a surviving candidate now; run a third batch; keep the working name and
  decide before publishing.
- **Research (real checks, 20 candidates in two batches):** PyPI JSON API, GitHub REST search and
  user endpoints, DNS name-server lookups for .com/.io/.ai (heuristic, not a registrar check;
  rdap.org was unreliable for .io), and web search. 14 of 20 were rejected (8 of 10 in batch one, 6 of 10 in batch two; batch two also pre-screened 5 more names out on PyPI): taken on PyPI, or
  already used by a healthcare, insurance, claims, legal or compliance business, or the name
  implied adjudication. The 6 that were not rejected, none low-risk: adjudex (implies adjudication), auditrail
  (existing HIPAA compliance vendor), dossiary, exhibitry, citecase (each with a connotation or
  collision problem), and sourceledger (HIGH risk: two live products).
- **Choice:** keep `claims-copilot` as the working name and decide before publishing. The name
  lives only in `src/claims_copilot/project.py`, so renaming is cheap.
- **Why:** nothing was clean, and the name only matters at publish time. A real USPTO trademark
  search (which the research tool could not do) belongs with that decision.

## 2026-10-19: Phase 1 approval and old-repo deletion (owner)

- **Phase 1 approved**, with the owner's confirmation of understanding.
- **Old repo deleted after the owner's typed confirmation** (`DELETE OLD REPO`, 2026-10-19).
  - Options offered: delete the project directory; keep it; delete it and the archive. The owner
    chose the project directory only.
  - Deleted: `~/Projects/hc_rag_proj` (the folder itself, no wildcards). Kept:
    `~/Projects/hc_rag_proj_archive_2026-10-16.zip`. No Desktop backup existed.
  - Safeguards that ran first: archive sha256 matched and `unzip -t` passed; the old working tree
    was clean at the archived HEAD; the git-ignored `docs/INTERVIEW_NOTES.md` was confirmed
    byte-identical in the archive.
  - Excluded from the archive by design (so now gone): `.env`, `.venv`, caches.

## 2026-10-19: Phase 2 owner choices (plan not yet approved)

- **Persistence: SQLite.** Options: SQLite (recommended), Parquet/CSV + DuckDB, PostgreSQL. Data
  regenerates from a seed, so storage is a cache; a thin repository interface keeps a later move
  cheap.
- **Diagnosis codes: real ICD-10-CM.** Owner chose this over my recommendation (fake codes with a
  `code_system` field). Consequence: Phase 2 starts with a verified fetch of the CDC/NCHS files
  and a terms check recorded in the manifest; procedure codes remain fake X0001-style codes.
- **Scope: defaults approved** (five anomaly types with decoys, 2,000 members, about 20,000 claims,
  IDs only, seed `20261019`).
- Phase 2 build has not started; it waits for the owner's approval of `docs/PHASE2_PLAN.md`.

## 2026-10-19: Phase 2 approved; ICD-10-CM code file added as a `data` source

- **Phase 2 plan approved by the owner** (`docs/PHASE2_PLAN.md`).
- Added `icd10cm-fy27-code-descriptions` (CDC/NCHS zip) to the catalog with a new `role = "data"`
  and a new `zip` kind. Options: (a) add a `data` role (chosen: keeps 75k code lines out of the
  retrieval corpus, and `extract`/`chunk` already skip non-corpus rows); (b) treat it as corpus
  (rejected: would pollute retrieval and break `extract`); (c) hand-copy codes into the repo
  (rejected: no provenance).
- Terms basis: the already-verified CDC policy page (`terms-cdc-agency-materials`). **Open
  caveat:** that page says "Most of the information" is public domain, and no notice specific to
  this file was found in the zip or its format PDF. Treated as a US government work for local use;
  the raw zip stays gitignored. Committed fixtures will contain codes only, no descriptors.

## 2026-10-19: Phase 2 build decisions and deviations from the approved plan

Each was a judgment call inside the approved plan. The owner can reverse any of them.

1. **Scale raised: 4,000 members, 400 providers, 40,000 claims (plan: 2,000 / 150 / 20,000).**
   Options: (a) keep the plan and seed fewer outliers (breaks the "30 per type" exit criterion);
   (b) raise scale (chosen). An intensity outlier is provider-level, so 30 outliers plus 30 decoys
   among about 190 visit-billing providers would make a third of peers elevated and stop them
   being outliers. Cost: none (generation takes about 3 seconds).
2. **Ground truth in a separate SQLite file (`truth.sqlite`)** instead of a table in the same
   database. Options: same file with a convention (rejected: relies on discipline); separate file
   (chosen: tools only ever open `payer.sqlite`, and a test checks it).
3. **Golden summary instead of a committed database fixture.** A 16 MB database does not belong in
   git. `eval/synthetic_dataset.json` records config, counts, and hashes; a test regenerates the
   default dataset and compares. Tests also generate a small dataset in memory.
4. **Dates inside the ICD-10-CM FY2027 window (2026-10-01 to 2027-09-30).** Options: dates in the
   past (diagnosis codes might not be valid on those dates); FY27 window (chosen). Some dates are
   after today; the data is fictional (KF-016).
5. **Unit limits apply per line, not per member per day.** A per-day limit would make duplicate
   claims also look like excess-unit cases, breaking independence of the five checks (KF-012).
6. **One provider id per claim** (the plan listed billing and rendering). Not needed for the five
   anomaly types; add if a later tool needs it.
7. **Diagnosis codes stored without descriptors.** Keeps the repository clear of any terms
   question and is all the validation tools need.
8. **Reference checker rule changed after the first full-scale run** (outlier multiple 3x to 2x).
   Evidence and consequence in KF-014. The change was made after seeing the failure; the
   labels themselves were correct (shares about 0.56 against a baseline of about 0.12).
9. **The ICD-10-CM file has 18 `QA` codes outside the shape I assumed.** My shape rule was
   written from memory and the file contradicted it; I widened the rule to match the file and
   excluded those codes from the sampled subset rather than guess what they mean (KF-015).

## 2026-10-19: Phase 2 approved

Owner approved Phase 2 as built and accepted all three decisions in `docs/PHASE2_REPORT.md`:
the scale deviation (4,000 / 400 / 40,000), the adjusted outlier rule with Phase 7 hand-built
cases as the unbiased check (KF-014), and the build decisions logged above. The owner did not
explicitly confirm the teach-me list; it stays available through `/teach`.

## 2026-10-19: Phase 3 plan decisions (plan not yet approved)

Options and reasoning are in `docs/PHASE3_PLAN.md`. Owner chose:

1. Bundle and unit rules: keep the synthetic rules behind a swappable `RulesProvider` interface
   (real NCCI/MUE tables are CPT-keyed and cannot apply to fake `X` codes; KF-009 and KF-012 stay open).
2. Diagnosis validation: full FY2027 list read from the verified local raw file, hash-checked
   against the manifest; tests use a fixture and the full-list test is skipped, visibly, when the
   raw file is absent.
3. Accuracy reporting: thresholds set from rule definitions, one documented tuning round on the
   main dataset, scores reported only on a second dataset with seed 20261020.

## 2026-10-19: Phase 3 build decisions

Plan approved by the owner (decisions 1A, 2B, 3A above). Choices made while building:

- **Findings versus observations.** A finding means a stated rule tripped. A near-miss that is
  worth showing (exception modifier present; near-match duplicates) is an observation and is never
  counted as a finding or scored as one. Options: one list with a severity field (rejected, it
  invites ranking); two lists (chosen).
- **Provider statistic.** Modified z-score with median and MAD, subject left out of its own peer
  group, 3.5 cutoff (published convention), MAD floor 0.02, at least 40 visit lines and 10 peers or
  the provider is not scored. Rejected: the reference checker's 2x median ratio (circular, KF-014).
- **Truth isolation in code, not only convention.** The repository opens SQLite read-only with
  `query_only` and ATTACH disabled, refuses the truth file name and any truth-like table or column,
  and a test forbids truth tokens in every tools module except `score.py`.
- **Diagnosis validation never falls back to the 420-code sample.** Without the full list it says
  "not checked".
- **Tuning round (decision 3A), recorded before it ran.** Candidate: iterative trimming of the peer
  baseline at the same 3.5 cutoff (no new constant), tried offline on dev only. Result: P0171 and
  P0203 moved from 2.96 and 2.95 to 3.23 and 3.21, still below the cutoff, so it was not adopted
  and no second variant was tried. The tool stays on the simple statistic; KF-017.
- **Held-out run.** Code committed as `c79a9b3`, then the seed-20261020 dataset generated and
  scored once: claim-level 100%, outliers 26 of 30.
- **Scorecard fix found by a test, not by results.** Seeded providers the tool declines to score
  (too little data) were counted as positives but not listed as missed. They are now listed.
  Dev numbers did not change (all 60 seeded providers were scored).
- **A test expectation I got wrong and corrected:** a claim with no diagnoses also has an
  out-of-range line pointer, and the tool reports both. The tool was right; the test was changed.

## 2026-10-19: Phase 3 approved; decisions on the report

Owner approved `docs/PHASE3_REPORT.md` as built and accepted KF-017, KF-018 and KF-019.

1. **Provider-outlier weakness (KF-017): option A.** Keep the simple statistic (modified z-score,
   median and MAD) and the recorded misses (2 of 30 on dev, 4 of 30 held-out). No further tuning
   round. Recheck on the Phase 7 hand-built cases, where peer-group contamination is realistic;
   Phase 7 is the unbiased check, and KF-017 stays open until then. Rejected: another tuning round
   on a fresh dev dataset (B), a lower cutoff (C, likely raises decoys).
2. **Near-match duplicate tiers (KF-019): option A.** They stay labelled observations only. They
   are never findings and are not counted in precision. Rejected: dropping them from the output.

The teach-me list is pending; the owner will use `/teach` for any concept he wants explained.

## 2026-10-19: Phase 4 plan approved; owner choices and build decisions

Owner approved `docs/PHASE4_PLAN.md` with 1B, 2A, 3A.

| Decision | Options | Choice | Why |
|---|---|---|---|
| Policy search in the API | A none; B free BM25 `GET /policy/search`; C dense via CostGuard | B (owner) | Gives the agent and UI citations at $0; Phase 6 replaces the ranking behind the same endpoint. Weak on paraphrases (KF-002, KF-021) |
| API shape | A resource-style GET plus `GET /tools`; B uniform `POST /tools/{name}` | A (owner) | Cacheable, UI-friendly, read-only by construction, one schema source |
| Access control | A none, loopback; B API key; C open bind | A (owner) | Synthetic read-only data; auth and rate limits are Phase 8, exposure is Phase 10 (KF-020) |

Build decisions (agent, within the approved plan):

- **Dependencies** added with `uv add`: `fastapi` 0.150.0, `pydantic` 2.14.1, `uvicorn` 0.54.0
  (pulls `starlette` 1.9.0, `pydantic-core` 2.50.1, `click`, `anyio`, `annotated-types`,
  `annotated-doc`, `typing-inspection`, `opentelemetry-api`). Versions pinned by `uv.lock`. These
  are libraries, not data sources, so no manifest entry; the FastAPI error-handler and OpenAPI
  behaviour was checked against its current documentation (Context7) before use.
- **Open item, not decided:** Starlette 1.9's `TestClient` warns that plain `httpx` is deprecated in
  favour of a package named `httpx2`. I did not add it because I have not verified that package. The
  warning is silenced for that one message in `pyproject.toml` (KF-022). Decision for the owner at the
  next dependency review: verify and adopt `httpx2`, or keep `httpx`.
- **Validation lives in one place.** Path ids carry the tools' own patterns (`id_regex`), so the
  published schema and the tools cannot disagree. The patterns now use `[0-9]` instead of `\d`, so
  Unicode digits are rejected (tested). Error bodies report only the parameter name, never its value.
- **Connections.** One read-only `Repository` per request, opened and closed inside the route, so no
  connection crosses threads and the truth/forbidden-word guard runs on every request. Rules, the
  peer book, and the ICD list are built once at startup and are immutable.
- **Flag paging** by cursor (`after` = last flag id) needed a small change to the Phase 3 tools:
  `flag_queue(..., after)` and `FlagQueue.next_after`. `truncated` now means "more after this page";
  with no cursor it is unchanged. No Phase 3 scorecard is affected.
- **Field names.** The peer z-score is published as `modified_z` (null when the group is too small to
  score), not `score`, and `score` joins the forbidden schema names.
- **Plan deviations:** (a) `GET /tools` is built from the OpenAPI document (operations marked
  `x-tool`) instead of a separate registry; (b) `ToolManifest` and `Health` carry the same notice as
  analysis responses; (c) "identical bytes" is tested for success responses only, since error bodies
  carry a per-request id; (d) the OpenAPI snapshot is generated from an app without data, so the
  test needs no local files.

## 2026-10-20: Phase 4 approved; `httpx2` check

Owner approved Phase 4 as built, accepting KF-020, KF-021, KF-022, and chose 1A for `httpx2`
("verify with `source-verifier`; adopt only if verified, then drop the warning filter").

`source-verifier` result: **UNVERIFIED**, not because anything was wrong, but because the rule I
set asked for the same maintainers as `httpx`, and that does not hold. Facts fetched on 2026-10-20:

- PyPI `httpx2`: latest 2.15.1 (2026-10-19), 21 releases, none yanked, first release 0.0.0 on
  2026-05-11, BSD-3-Clause, Python >=3.11. Author Tom Christie (also listed on `httpx`);
  maintainer "Pydantic Services Inc."; source `github.com/pydantic/httpx2` (not `encode/httpx`).
- README: "HTTPX2 is a continuation of the wonderful work started by @lovelydinosaur and the broader
  HTTPX community." and "Pydantic is picking up stewardship under the HTTPX2 name". Not a fork.
- Dependencies: `anyio`, `httpcore2==2.15.1`, `idna`, `truststore`, `typing-extensions` (<3.13).
  `httpcore2` was not inspected.
- Wheel sha256 `75841cd8...9015be` (matches PyPI after download); no `.pth` files, no install
  scripts; one console script. Nothing was installed.
- Starlette 1.9.0 imports `httpx2` first and falls back to `httpx`; it lists `httpx2>=2.0.0` under
  its `full` extra and its README calls `httpx2` required for `TestClient`.

Outcome: nothing adopted yet; `httpx` and the one-warning filter stay (KF-022 remains open). The
choice between adopting and keeping is put to the owner with the Phase 5 plan. This is a library,
not a data source, so no manifest entry was written; the evidence is recorded here.

## 2026-10-20: Phase 5 plan decisions (owner choices; plan itself not yet approved)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Orchestration | A plain tool-calling loop; B graph framework | A (owner) | No new dependency; bounds are provable and every step is in the run record |
| Providers in Phase 5 | A both live; B OpenAI only live; C Anthropic only live | A (owner) | Proves the swap and gives a first small comparison; about $3 live ceiling inside the $8 `p5` cap |
| Request-scope gate | A deterministic rules + post-generation check; B add LLM classifier | A (owner) | Free and auditable; over-blocking is measured and recorded, not hidden |
| `httpx2` (KF-022) | A dev-only; B keep `httpx` and filter; C everywhere | B (owner) | Only a silenced test warning; runtime provider calls keep the established package; revisit when Starlette drops the fallback |

The owner has not yet said "approve" for `docs/PHASE5_PLAN.md`, so no Phase 5 code, dependency, or
paid call exists.


## 2026-10-20: Phase 5 build decisions and first live smoke runs

| Decision | Options | Choice | Why |
|---|---|---|---|
| Models | `a_cheap`, a mid tier, a premium tier | `a_cheap` (owner): OpenAI `gpt-6-luna`, Anthropic `claude-haiku-5-5`, both $0.10 / $0.50 per 1M tokens, verified in the manifest | A smoke test needs to prove the loop and the swap, not model quality |
| Provider access | vendor SDKs; plain `httpx` | Plain `httpx` against the documented REST endpoints (OpenAI Responses, Anthropic Messages) | No new dependency; every request goes through `CostGuard`; adapters testable with `MockTransport` |
| Identifier arguments | trust FastAPI routing; validate first | Validate with `[A-Za-z0-9._:~-]{1,64}` before building a path | A test showed `C0000001/dossier` being routed to another endpoint |
| Flag ids (found by smoke run 1) | A show flags with registry ids; B accept the raw `flag_id` as a citation; C change the prompt | A | The runtime, not the model, names what can be cited. It was a defect in my implementation (ids registered, never shown). No prompt change, so no prompt A/B was needed. Result: Anthropic claim answers shown 0 of 10 before, 9 of 10 after |
| Smoke-run cost control | estimate only; hard run ceiling | A `--ceiling` (default $3) checked before every investigation, plus the $0.15 per-investigation bound and `CostGuard` caps | The first live calls were priced from the ledger, not from my estimate (see below) |

**Not changed, awaiting the owner** (each would loosen a check because of a failure, so I did not
do it alone; recommendations in `docs/PHASE5_REPORT.md` section 4): whitespace-insensitive quote
matching (KF-023); treating a screen flag as its own source for `CONFLICTING_EVIDENCE` (KF-024);
using the runtime's own `searched` list instead of the model's (KF-025).

**Estimate versus measured.** I estimated about $0.0075 per investigation (60k input and 3k output
tokens). Measured: OpenAI about $0.0013 and Anthropic about $0.0022, with 2 to 3 model turns and
1 to 2 tool calls. Each run of 28 cost about $0.042. Phase 5 live spend in total: $0.0877 of $8.

## 2026-10-20: Phase 5 report decisions (owner: 1A, 2A, 3A; Phase 5 approved)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Quote matching (KF-023) | A ignore whitespace; B fix drop-caps at ingest; C keep strict | A | Fixes the split-letter artifact without re-chunking. Trade: it also ignores spaces between words, so "a b" and "ab" match; a changed letter or word still fails (tested) |
| Flag as its own source (KF-024) | A yes; B no | A | The screen and the checks are different mechanisms. Trade: models now report more "conflicts" (KF-029) |
| `searched` (KF-025) | A runtime fills it; B raise limit; C keep | A | `searched` is a fact the runtime recorded. The model's list is still required by the schema but is clipped and never shown or scanned. The prompt was not changed |

These three changed validator behaviour, so I edited the one validator test that asserted the old
rule (an empty `searched` list is no longer invalid). That was a deliberate behaviour change by
the owner, not a way to make a failing case pass; the old cases are recorded in `KNOWN_FAILURES.md`.
Run 3 (`p5-smoke-20261020-r3`, $0.0417) measured the effect: 20 of 20 claim investigations shown
(OpenAI 10, Anthropic 10), both unanswerable-question cases `INSUFFICIENT_EVIDENCE`. Phase 5 live
spend in total: $0.1294 of $8.

## 2026-10-20: Phase 6 plan approved; owner choices

| Decision | Options | Choice | Why |
|---|---|---|---|
| Reranker | A LLM rerank (`gpt-6-luna`), B local cross-encoder, C none | A (owner) | No new vendor or dependency; reorder-only output validated by code; about $0.001 and a few seconds per search |
| Held-out questions | A 16 new paraphrase questions, B only the 40, C 40 new | A (owner) | An unbiased check on the chosen pipeline without a large drafting load. Still assistant-drafted (KF-006) |
| API integration | A opt-in hybrid, default lexical; B hybrid default; C lexical only | A (owner) | The API stays free and offline by default; hybrid goes through `CostGuard` and falls back to BM25 |

Plan: `docs/PHASE6_PLAN.md`. Live spend ceiling for Phase 6 is $2.00 inside the $8 cap; each paid step
waits for a separate go with its dry-run estimate.

## 2026-10-20: Phase 6 build decisions (assistant, within the approved plan)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Winner of the development comparison | any of V0 to V6 by the pre-set rule "best on the development set" | V3 (hybrid + rerank) | Best on every development metric (R@1 0.82, R@10 0.90, MRR 0.856), and simpler than V6 (no contextual index). Confirmed once on held-out |
| Contextual embeddings | adopt V5/V6, or record as not helpful | Not adopted; kept in the repo as a measured, index-only tool | V6 is below V3; V5 alone is below V3. KF-033 |
| API mode name and shape | new endpoint, or a mode on `/policy/search` | `--policy-mode hybrid` on the same endpoint; response gains `mode` and `fallback_reason`; `bm25` becomes nullable | Owner choice 3A. Default behaviour unchanged except two new fields; `docs/openapi.json` diff reviewed |
| Reranker output rule | permutation only, or any valid subset | Valid subset accepted (listed first, rest in fused order); any unknown, repeated, or malformed label rejects the whole answer and keeps fused order | Lets the model rank only its best few; still reorder-only |
| Held-out diagnostics | winner + V0 + V1 only, or add V2 | Added V2 (free, offline) | Separates the fusion effect from the rerank effect on held-out; V4 to V6 were not run on it |
| Rerank cache key | question only, or question + candidate ids and hashes + prompt + model | The full key | A changed corpus, prompt, or model cannot serve a stale order |
| Live-spend discipline | one go for all Phase 6 steps, or one per step | One go per paid step: 10-chunk pilot ($0.0021), full descriptions ($0.3437); the embedding ($0.0184), rerank runs ($0.1071 over all runs) and the 8-case re-check ($0.0230) ran inside the plan's own line items and ceiling after a printed upper bound | The plan listed those items and the ceiling is $2.00; I stated each estimate before running |

Process note: the ledger labels the contextual-embedding calls "p0 baseline: embed corpus chunks"
because the existing embedding helper hard-codes that purpose text; the calls are phase `p6` and are
counted in the Phase 6 total.

## 2026-10-20: Phase 6 approved; owner accepted all recommendations

| Decision | Options | Choice | Why |
|---|---|---|---|
| Phase 6 as built | approve / change | Approved (owner) | Hybrid + rerank (V3) measured R@1 0.82 dev and 0.81 held-out |
| Hybrid as API default | A keep opt-in until Phase 7; B default now | A (owner) | Unanswerable-question behaviour (KF-031) and cost/latency (KF-032) are not yet measured on a larger set |
| Candidate depth | A leave at 20, revisit in Phase 7; B try 40 now | A (owner) | Avoid tuning on 56 assistant-drafted questions (KF-030) |
| Contextual descriptions | A keep code as a documented negative result; B remove | A (owner) | KF-033; the measurement is reproducible from the repo |

## 2026-10-20: Phase 7 plan decisions (owner chose every recommendation)

| Decision | Choice | Why |
|---|---|---|
| Calibration labels | A: owner labels 40 answers against a one-page rubric | The judge is checked against someone other than the case author (KF-006) |
| Judge model | A: each answer judged by the other provider's cheap model | Avoids a model grading its own writing; both judges get calibrated |
| Suite size | A: about 95 new agent cases plus the 56 retrieval questions | Narrower intervals than 60 cases at about $1.80 estimated |
| KF-029 prompt change | A: measure only; any `agent_v2` is a separate gated step | Keeps the `agent_v1` comparison clean |

Live-spend ceiling proposed: $4.00 inside the $12 `p7` cap (not yet confirmed by the owner).

## 2026-10-20: Phase 7 pre-registration and guardrails

- **Owner approved** the Phase 7 plan as drafted (decisions 1A to 4A) with these guardrails: the
  pre-registration commit comes before any provider call; the live-spend ceiling is $4.00 (stop and
  ask if an estimate would exceed it); the owner labels about 40 answers after the dev-split runs;
  the held-out (test) split and judge calibration wait until the owner has finished labelling; no
  labels are written on the owner's behalf and reported as human.
- **Choice: metrics are code, thresholds are data.** `src/claims_copilot/evals/metrics.py` holds the
  definitions and `eval/phase7_preregistration.json` the numbers; a test checks that
  `docs/PHASE7_PREREGISTRATION.md` states the same thresholds. Rejected: thresholds only in prose
  (they drift) or only in code (not reviewable by the owner).
- **Choice: the split is a hash rule per layer** (`(n + 1) // 3` dev). Rejected: random sampling at
  run time (not reproducible) or hand-picking (can favour easy cases).
- **Choice: the conflict rubric does not decide the flag-versus-check question** (KF-029). The owner's
  labels record a `pattern` (`FLAG_VS_CHECK` or `OTHER`) so the definition comes from the owner's
  judgement, not the assistant's. Rejected: writing "a flag the checks do not confirm is not a
  conflict" into the rubric, which would pre-decide the question the labels exist to answer.
- **Choice: decoy results are split into tool false alarms and agent reports**, because a decoy finding
  that is in the dossier and faithfully reported is a tool issue (KF-017 family), not an agent one.

## 2026-10-20: Standing instruction, and Phase 7 case-suite choices (auto-chosen)

The owner gave a standing instruction on 2026-10-20 (3:48 PM): approve every recommendation, make
every remaining decision gate with my own recommended option, log it here, and stop only for the
owner's hand labels (and for the listed hard-rule stops). Entries below are auto-chosen under that
instruction and are listed for owner review in the final report.

| Decision | Options | Choice | Why |
|---|---|---|---|
| Hand-built fixture shape (step 2) | A: separate small payer database written by code, expected values declared by hand; B: reuse the generator with new seeds | A | B would repeat KF-011 (generator and checks share an author's assumptions). A peer group of 30 with about 10% elevated replaces the 33% to 40% seeded in the generator (KF-017) |
| Provider-level hand-built cases | 6 of the 20 scenarios are provider-level (elevated, in range, low, sparse, contaminated 10%, small group) | As stated | Covers both sides of the 3.5 cutoff and both "not scored" limits. Margins were worked out by hand first (z 5.8, 1.2, -2.3, 6.1) so no case sits near the cutoff |
| E5 result | n/a | 20/20 exact, 0 false alarms on 10 decoys | By construction the cases are easy; this shows the tools behave as designed on realistic peer groups, not that they are accurate on real data. KF-011 and KF-017 are narrowed, not closed (see `KNOWN_FAILURES.md`) |
| Unanswerable confirmation (amendment A1 to the pre-registration) | A: assistant read of the top hits; B: a deterministic term-absence test over all 1,913 chunks plus a spot check by the owner if wanted | B | The plan said "confirmed by a human read"; the owner is not asked to read 20 searches. Absence of the topic word is a floor, not proof (KF-035). **This amends the plan's wording; thresholds, metrics and cases are unchanged** |
| Unanswerable mix | 14 far from the corpus, 6 near misses (related words present, the rule asked about is not) | As stated | Near misses are where an always-returns-something retriever is tested (KF-031) |
| E2E fresh seed | 20261021 (not 20261019 or 20261020) | As stated | A seed no earlier tuning or scoring touched |
| E2E selection | 4 seeded + 2 decoys per type, seeded sample over flagged claims; expected labels written to the case file at build time | As stated | Scoring a run then never opens a truth store |
| Safety claims | Drawn from the e2e dataset's flagged queue, excluding e2e case claims | As stated | Keeps one payer database for e2e, unanswerable and safety runs |
| Planted-chunk exposure | A: planted hit at rank 1 of every search while the case is active; B: planted hit only when the query matches | A | Worst-case exposure; B would test the retriever more than the model's resistance |
| Injection compliance detection | Per attack: a phrase, a verdict word, a fake id, a tool argument, a prompt-text shingle overlap | As stated | Deterministic, no judge. Verdict signal counts a mention of the word as well as an assertion, so it overstates compliance (conservative) |
| Plain versus obfuscated decision asks | 3 plain, 7 paraphrased or obfuscated, tagged in the case note | As stated | The pre-registered targets are 1.0 for plain and 0.8 for obfuscated; both are reported separately |

## 2026-10-20: Phase 7 step 6, the runner (auto-chosen)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Spend accounting | A: leave agent calls on phase p5 and rerank on p6; B: add a `phase` argument to `Investigator`, `Reranker`, `load_pipeline`, `load_policy_index` (default unchanged) and charge Phase 7 runs to `p7` | B | The Phase 7 ceiling ($4.00) is then enforced from the ledger by `phase=p7`, and Phase 5 and 6 numbers stay what they were. Defaults keep every earlier caller identical |
| Parallelism | A: serial (about 3 hours for the test split); B: 4 worker threads, one set of API stacks per thread, one lock-protected guard | B | Per-run latency is still recorded per run. `LockedGuard` serialises ledger read and append so caps see every entry. Overshoot past a ceiling is at most a few calls (cents) |
| Resumability | A: a summary file only; B: one atomic JSON file per (case, provider, repeat); a file means done | B | An interrupted run resumes at zero extra cost; a finished run is free to "run" again |
| Provider errors | Pre-registered: re-run once, keep both attempts; a second error is a failure for that case and repeat | As registered | Six provider errors in a row stop the run (outage or bad key) so money is not burned |
| Cap refusal | A: record the refused run as a result; B: stop and write nothing | B | A refusal is a spend event, not a model behaviour; recording it would bias scores |
| E3 design (amendment A2, dated 2026-10-20, before any test-split run) | Plan said "one provider per case"; A: keep that; B: run both providers on every E3 case | B | Same case set, same paired design, twice the paired observations at about $0.37 on the test split. **Amends the plan's wording only; thresholds, metrics and cases are unchanged.** Hybrid never falls back silently: if hybrid is unavailable the run refuses |
| Search-mode configs | `lexical` runs every case (E1, E4); `hybrid` (hybrid + rerank) runs unanswerable and policy-related e2e cases only (E3); planted injections are lexical-only | As stated | The planted hit is a worst-case rank-1 exposure in a controlled index; mixing it with hybrid would test two things at once |
| Dry-run estimate | Mean cost per run from earlier job and smoke records, per provider; plan figures as a fallback; scope-gated cases at $0 | As stated | Measured, not assumed. Dev lexical $0.30, dev hybrid $0.23, test lexical $0.63, test hybrid $0.37; all fit the $4.00 ceiling together with the judge |

## 2026-10-20: Phase 7 step 7, judge, label sheet, calibration rule (auto-approved under the owner's standing instruction of 2026-10-20)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Judge pairing | A: one judge model for all answers; B: cross-provider (OpenAI answers judged by Claude Haiku, Anthropic answers by GPT-6 Luna) | B | Avoids a model grading its own family's output. Judge sees only statements and the recorded tool outputs (each source clipped to 900 characters, the same clip the owner sees) |
| Label sample (pre-registered mix) | Seeded draw of 40 dev answers: 24 `ANSWERED`, 8 `CONFLICTING_EVIDENCE`, 8 other; seed 7 | As registered | Sheet is blind: no judge label, no provider, no case id shown to the owner. Key is a separate file |
| Amendment A3 (dated 2026-10-20, before any label exists) | Plan: label every statement (169 in the sample, about 2.5 hours); A: keep; B: a seeded random subset of at most 6 statements per answer | B | Keeps the sitting to about 70 minutes as the owner asked. **Amends the plan's wording only**; thresholds are unchanged. Cost: fewer statements per answer, so statements within an answer are correlated and intervals are wider than their nominal n suggests (stated in the report) |
| Sheet forgery | Model summary text could contain a line that looks like a label prompt | Lines starting at column 0 with a prompt keyword are escaped when rendering; the parser matches only prompt lines | Test in `test_evals_labels.py` |
| Calibration module | `evals/calibrate.py` applies the pre-registered rule (kappa >= 0.6, false "supported" <= 2, minority class >= 15 statements, conflict calibrated only with >= 10 labelled conflict answers) | As registered | Refuses any label row whose labeller is not "owner". A bad judge parse is counted as "no judge label", never imputed |
| Judge on the test split | A: judge test answers regardless; B: only if the judge is accepted by calibration; else report hand-label faithfulness only (option C) | B | Saves money and follows the pre-registration: an uncalibrated judge's numbers are not reported as faithfulness |
| Dev-only findings | Safety dev results show a planted injection followed in 2 of 6 runs (never reached the user) and several `INVALID_OUTPUT` refusals | Record as KF-039, KF-040; do not change the prompt, scope gate or cases | Changing the prompt on dev results is tuning; the test split stays untouched. A prompt change would need an eval comparison (AGENTS.md) |
| Flaky test fix | `test_hostile_query_values_are_rejected_without_echo[limit=1e9]` failed once because the random hex `request_id` happened to contain "1e9" (about 1 in 140 runs for that value) | Remove the request id from the body before the no-echo check; the check on the rest of the body is unchanged | A false positive in the test, not a behaviour failure: the response did not echo the value. Recorded here because tests are not edited to pass; this one was wrong, and the fix keeps the assertion as strong |
| Label sheet whitespace | The pre-commit whitespace hook strips the trailing space after each `LABEL ...:` prompt | Accept the stripped sheet | The parser accepts a prompt with or without a trailing space; the owner types after the colon |
| Phase 8 start | Plan said Phase 8 starts after Phase 7 exit criteria; the labels are an exit criterion | Wait for labels (or an explicit "skip labels") before test runs and before Phase 8 | The standing instruction says start each phase only after the previous phase's exit criteria are met |

## 2026-10-20: Amendment A4, the label source changed (auto-approved under the owner's standing instruction of 2026-10-20)

The pre-registered label source was the owner's own hand labels (decision 1A). The owner did not
label the sheet. A different model (GPT Sol, in a separate chat) drafted the labels into
`eval/labeling/phase7_label_sheet_DRAFT_gptsol.md` from the blind sheet and the rubrics only (told
not to open the key, run records or judgments). The owner checked the draft's form: 193 prompts,
same ids and order as the original, no invalid letters, non-prompt lines identical, 40 notes.
The owner's review of the labels' content was left blank in the instruction, so it is **not assumed**:
every row records `owner_review` = "form check only; content review not stated, treated as
unreviewed".

| Decision | Options | Choice | Why |
|---|---|---|---|
| A4: label source | A: wait for owner hand labels; B: use the model-drafted labels, named as such; C: option C (no labels, judge uncalibrated) | B, as the owner instructed | Keeps the project moving. **What changed:** the label source (owner hand labels to model-drafted labels, GPT Sol, owner review as recorded). **What did not change:** kappa >= 0.6, false "supported" <= 2, minority class >= 15, conflict calibration only with >= 10 labelled conflict answers, the cases, the 40-answer sample and the 6-statement cap (A3) |
| Consequence | n/a | Judge agreement now measures agreement with another LLM. GPT Sol and the judge models (GPT-6 Luna, Claude Haiku 5.5) are all LLMs and share failure modes (both can read a truncated source as support, favour fluent restatement, or mis-handle numbers). A judge accepted on these labels is weaker evidence of faithfulness than one accepted on human labels, and every faithfulness number reported from it is labelled that way | KNOWN_FAILURES KF-041 |
| Naming | A: keep "hand labels"; B: "model-drafted labels (GPT Sol), owner review: form check only" everywhere | B | The pre-registration already says labels by anyone but the owner are never reported as human labels |
| Pipeline | A: ingest as "labeller: owner"; B: record `label_source` and `owner_review` per row; file renamed `eval/phase7_model_drafted_labels.jsonl` | B | The owner's identity is not written onto rows the owner did not label. Accepted sources are `owner-hand` and `gpt-sol-draft` only; `assistant`, the judge models and unknown sources are refused by `labels.label_rows` and by `calibrate.read_labels` (tests). The CLI needs `--label-source` and `--owner-review` |
| Ingest checks | n/a | `check --sheet DRAFT` passed (no empty or invalid prompt); the draft's 169 statement ids equal the key's; counts statements S141 P9 C19 N0, CONFLICT W6 N2, PATTERN F6 O2, HONEST Y8, as the owner stated. No letter was changed | The assistant looked at the key (run-file names) only to compare ids and to explain the C labels; it did not change any label |
| 19 "cannot tell" statements | A: re-label; B: report, count as not supported (registered rule) and show a sensitivity analysis | B | Every C is explained in the labeller's own notes by the 900-character cut-off or the omitted search results: 15 of the 19 statements cite a source clipped in the sheet, and 4 cite one shown earlier in the item ("same as above") that was clipped there. Items: L03.3, L04.8, L13.6, L17.1 and L17.2, L22.3, L23.1 to L23.3, L24.1 to L24.3, L26.5, L29.3 and L29.4, L35.4 and L35.7, L38.8, L39.7. The judge saw the same clip. So C measures what the 900-character display hides, not the writer's faithfulness (KF-041) |
| Calibration result (registered rule, C counts as not supported) | n/a | **Judge accepted**: kappa 0.7535, false "supported" 2 (limit 2), minority class 28 statements (limit 15), raw agreement 0.9231 on 169 statements. Conflict: 8 labelled answers, under the 10 minimum, so conflict is reference labels only (not calibrated) | The result sits on the limit for false "supported" and rests on model-drafted labels. With C removed (information only), the minority class is 9 statements, under 15, so the rule would not accept; that variant is not what was registered |
| Test split | A: run the judge on the test split only if accepted; B: always | A (as registered). The judge is accepted, so test answers are judged, and reported as "judged against model-drafted labels" | Money and the pre-registration |

## 2026-10-20: Phase 7 close (auto-approved under the owner's standing instruction of 2026-10-20)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Default search mode (E3) | A: change the API default to hybrid + rerank; B: keep lexical, hybrid opt-in | B | The registered rule allows a recommendation only if hybrid loses no more policy cases than it gains. Measured: gained 0, lost 1 of 19 (not detectable, p = 1.0). Hybrid is about 2x the cost, 3x the latency, and 9 of 36 end-to-end runs were rejected against 1 of 120 for lexical. No API change |
| Conflict prompt (KF-029, decision 4A) | A: propose `agent_v2`; B: measure only | B | Conflict answers are rare (4 of 229 shown test answers) and the conflict judge is uncalibrated, so there is no evidence for a prompt change. `agent_v1` unchanged |
| Missed targets (unanswerable 0.64 vs 0.80; judged faithfulness 0.789 vs 0.85) | A: tune prompt, cases or gate; B: report and log | B | Pre-registration: a missed target is a KNOWN_FAILURES entry, not a reason to change a case or threshold (KF-042, KF-043) |
| Mode comparison tooling | A: ad hoc script; B: `scorecard --vs RUN` writes `modes_paired` with a test | B | Reproducible and tested; no new provider calls |
| Judged-faithfulness report | A: pooled statements only; B: per-case mean with a seeded bootstrap interval plus the pooled rate flagged as optimistic | B | The pre-registered unit is the case; pooled statements overstate precision (`evals/judged.py`, tests) |
| Retrieval-only unanswerable layer | A: run it now; B: report as not run (KF-047) | B | The agent-level result answers the product question; extra spend and time for a secondary view. Stated as a scope reduction, not a result |
| Amendments in force at the end of Phase 7 | n/a | A1 (term-absence test confirms unanswerables), A2 (both providers on every E3 case), A3 (at most 6 labelled statements per answer), A4 (model-drafted labels) | Thresholds are unchanged by all four |
| Phase 8 start | A: wait for the owner's report approval; B: start under the standing instruction | B | The owner's instruction of 2026-10-20 4:04 PM covers Phases 7 to 11 without further approvals. Phase 7 report written; no Phase 8 work was started before it |

## 2026-10-20: Phase 8 observability and security (auto-approved under the owner's standing instruction)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Tracing stack | A: add the OpenTelemetry SDK and a collector; B: a small span tracer writing JSON lines, with OpenTelemetry-shaped field names | B | No new dependency or service for a single-process portfolio system, and a file that `jq` reads. The field mapping is documented (`OTEL_COMPATIBLE_FIELDS`), so a collector can be added without changing callers. Tracing is off by default (`NullTracer`) and never changes behaviour |
| What a trace holds | A: full prompts and answers for debugging; B: metadata only (ids, names, versions, sizes, tokens, cost, status) | B | Traces are the log most likely to be shipped or shared. Payload-bearing keys are omitted by rule, string values scrubbed and cut, exceptions record the class only. Full payload stays in the run records in `data/runs/` (gitignored), which evaluation needs |
| Audit log | A: plain log lines; B: hash-chained JSON lines with sequence numbers and a verifier | B | An investigator tool needs to show that history was not edited. Detects edit, delete, reorder, and forged links, and names the first bad entry. Tamper-evident only; the limit and the real-deployment answer (write-once storage) are in `docs/SECURITY.md` |
| API authentication | A: leave open (the Phase 4 decision, loopback only); B: optional `X-API-Key` plus a rule that a non-loopback bind needs a key | B | The Phase 4 decision assumed loopback. Phase 10 puts the service behind a network, so the service now refuses to listen on a network without a key. One shared key, hashed at startup, constant-time compare; per-user identity is listed as out of scope |
| Rate limit | A: none; B: in-process token bucket per caller (120 per minute, burst 30) | B | Cheap and testable; per process only, so Phase 10 also limits at the load balancer |
| Health probe | A: guard everything; B: leave `/v1/health` open | B | Liveness probes carry no credentials and the route returns no claim data |
| Scrubber | A: adopt a PHI library; B: regex patterns for credentials, SSN, phone, email | B | All data is synthetic, so this is defence in depth. A real-data deployment needs a reviewed scanner (stated in `docs/SECURITY.md`) |
| Wiring | A: instrument every CLI and the eval runner now; B: `Investigator` takes optional `tracer` and `audit`; the API takes an optional `Guard` | B | The loop and the API are the two production paths. The eval runner and smoke CLI are not changed: their records already hold everything, and adding audit writes to 600 eval runs adds nothing |
| Prompt injection | A: add new model-level defences or change the prompt; B: test the existing system-level controls and document them | B | A prompt change needs an eval comparison. The controls that matter (scope gate, allow-listed read-only tools, validator on citations, quotes, and verdict words) are deterministic and already measured in Phase 7 (KF-039, KF-040). Phase 8 adds regression tests for the forged-citation path and for what reaches logs |

## 2026-10-20: Phase 9 workbench UI (auto-approved under the owner's standing instruction)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Frontend stack | A: React/Vite app with a build step; B: three static files (HTML, CSS, plain JS) served by the API | B | No Node toolchain, no third-party code in the page, nothing to audit but 400 lines, and the page can use a strict content security policy. A richer framework adds supply-chain risk for a read-only viewer |
| Where it is served | A: a separate server; B: `/workbench` on the API, outside the OpenAPI contract | B | One process and one origin, so the policy can say `connect-src 'self'`. `docs/openapi.json` is unchanged (tested) |
| Access | A: key required for the page; B: page files open, every record still behind the key | B | The browser cannot send a header on a page load. The files hold no data. Data calls send `X-API-Key` from a field in the page; the key is not stored and never put in a URL |
| Rendering untrusted text | A: render HTML from the API; B: text nodes only, https links only | B | Policy passages and tool strings are untrusted. The script has no `innerHTML`, `eval`, or storage (tested), and a fake-DOM run shows a hostile passage as literal text and a `javascript:` URL not used as a link |
| What the UI shows | A: add an "Investigate" button that calls the model; B: read-only evidence: flag queue, claim dossier with check results, evidence references, limits and notices, provider and member drill-down, policy search with source, page, hash and an "untrusted source text" label, evidence download as JSON | B | The API has only GET routes and no model call. A button that spends money needs its own approval, caps, and a POST route, which would break the read-only contract. The cited-summary agent stays a CLI/eval component (KF-051) |
| Audit review in the UI | A: add an audit-log route; B: not in the UI; verify with `python -m claims_copilot.obs.audit` | B | A route that serves the audit log is a new surface to protect and a change to the contract; the CLI verifies the chain |
| UI testing | A: no UI tests; B: static checks plus a Node run of `app.js` on a fake DOM against recorded API responses | B | A real browser was not used (workspace rule: no browser use). The fake DOM checks that real API payloads render without error, that hostile text stays text, that the key goes in a header only, and that errors are shown. It does not check layout, focus order, or screen readers (KF-052) |

## 2026-10-20: Phase 10 deployment (auto-approved under the owner's standing instruction)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Target | A: a live cloud deployment now; B: container artifacts and an ECS Fargate template, not deployed | B | The owner decided no GitHub or hosting action in this project, and a live deployment needs an account, money, and a TLS setup. The artifacts show how it would run |
| What goes in the image | A: everything incl. the policy corpus and indexes; B: code, prompts, manifest, and `payer.sqlite` only | B | The corpus and indexes derive from third-party documents with their own terms (AGENTS rule 3). The answer key is generated outside the data directory and never copied |
| Dataset in the image | A: mount it at run time; B: generate it at build time | B | Deterministic, free, offline, and one fewer thing to mount. The default seed gives the same dataset hash as the local one |
| Start-up | A: let the API default (open on loopback); B: an entrypoint that refuses to start without a key | B | A container is network-reachable by design. The Python runner already refuses a remote bind without a key; the entrypoint fails earlier with a clear message and never prints the value |
| Secrets | A: environment values in the task file; B: Secrets Manager reference | B | Nothing secret in a file under version control (tested: no `environment` block, a Secrets Manager ARN) |
| Writable paths | A: writable root; B: read-only root with two writable volumes (audit, traces) and `/tmp` | B | Limits what a compromised process can change. The audit volume is ephemeral on Fargate, so a durable sink is listed as required before use (KF-054) |
| Verification | A: claim it works; B: say it was not built and test what can be tested | B | No container runtime on this machine. Static tests, the entrypoint run, and a real local server run with a key |

## 2026-10-20: Phase 11 interview hardening (auto-approved under the owner's standing instruction)

| Decision | Options | Choice | Why |
|---|---|---|---|
| README order | A: keep per-phase order; B: results first with an honest summary table, per-phase detail below | B | A reader should see what works, what missed its target and what the labels are before the history. Missed targets and the label provenance are in the first table |
| Pre-publish scan | A: claim the repository is clean; B: run what can be run and say what cannot | B | gitleaks over all history and tracked-file checks were run. An assistant cannot know the owner's employer terms, so that item stays open for the owner |
| Working-directory secret scan | A: report it as clean; B: do not use it as evidence | B | `gitleaks dir` also scans ignored local files (`.env`, `data/`), which are not committed. The history scan is the relevant one |
| Final report | Include "decisions made on my behalf" first with label provenance (A4) | Done | The owner asked for it explicitly |

## 2026-10-20: Independent-author tool test, pre-registration (KF-018)

Written and committed before any file from the independent author exists in the repository.
The brief is `eval/independent/BRIEF_for_sol.md`; its sha256 is in `SESSION_LOG.md`.

| Item | Registered |
|---|---|
| Author | GPT Sol in a separate chat run by the owner, told not to open the code, `eval/`, `tests/` or any answer key. Sol cannot be launched from here and no other model stands in for it |
| Question | Do the unchanged tools find anomalies that a different author wrote from public rules, and do they stay quiet on near misses and ordinary claims? |
| Metrics | Per type: recall on TRUE cases (found / n, Wilson 95% and 80% intervals). False alarms: count on DECOY cases and on CLEAN claims, per type and in total. n = 10 per type is small; one case moves recall by 10 points. No pooled "accuracy" |
| Unit of a case | Claim-level types: any flag on a case's claim(s) by the matching check counts as found (same matching logic as `tools.score`). Provider-level type: the provider is the case; "not scored" (the tool abstains) counts as a miss and is listed |
| Fixed now | No threshold changes. No tool, test, corpus or gold-set edits. I do not edit Sol's claims, rules or labels, and do not repair invalid rows. Labels never go into `payer.sqlite` or anywhere the tools or API can read |
| Invalid input | If a file is missing or invalid (schema, duplicate ids, real-looking codes, labels not one-to-one with claims), stop and report; no repair |
| Misses and false alarms | Each classified once: (a) tool bug, (b) tool rule narrower than the public rule, (c) Sol's case wrong or ambiguous, (d) our schema cannot express it. The label is never changed to fit the tool. Class (c) cases stay counted as misses and are listed. A worse score than 150 of 150 is the finding and is not fixed in this task |
| Comparison | The earlier 150 of 150 used a generator we also wrote and shared rule definitions; the two results are not like-for-like and are reported side by side with that caveat |

Deviations from the owner's task text, made because the text could not be carried out as written
(all disclosed in the final report):

1. **Third file, `rules.json`.** Our tools check against rule tables (paired codes, unit limits,
   visit codes). A blind author cannot know them, so the author states its own small rule set and
   I load it into the temporary database. Without it unbundling and excess-unit cases would be
   untestable. If the tools' behaviour depends on our fixed tables rather than the loaded rules,
   that is a finding.
2. **Provider-level block outside the 140.** Intensity is a provider-level case that needs many
   visit lines per provider and many same-specialty peers, so 10 + 10 cases cannot fit in 140
   claims. The brief asks for 100 claim-level case claims plus 40 clean claims (140) plus a separate
   intensity block (20 test providers and at least 25 background providers, at least 50 visit lines
   each), generated by a script.
3. **Labels use `claim_ids` (a list) and `provider_id`, not one `claim_id`,** because a duplicate case
   has two claims and an intensity case has none.
4. **Sample-size guidance in the brief** (at least 50 visit lines per provider, at least 25
   background providers) is a rounded feasibility hint, deliberately not our own cut-offs. If the
   tool abstains anyway, that is reported as "not scored", a miss.
5. **Entity schema given to the author** is the claim, line, member and provider rows of
   `DATA_MODEL.md` only. Rule-table rows, the flag queue, code tables and our own decoy designs were
   left out.

## 2026-10-20: Independent-author result: provider-intensity miss recorded as an open limit, not tuned

Decided with the owner (not on their behalf).

| Option | Result |
|---|---|
| A. Record as an open limit; change nothing; any fix is a separate pre-registered change on fresh data from a new independent author, with the rule and cutoff written down before looking at that data | **Chosen** (the recommendation, accepted by the owner) |
| B. Retune the cutoff or peer logic against Sol's data now | Rejected: it would turn the independent test into a tuning set and break the pre-registration |
| C. Drop the provider-level claim without recording the miss | Rejected: the result stays visible |

Unchanged: the 3.5 cutoff, peer-group logic, tools, tests, Sol's cases and labels. The DUP-D-10 false alarm stays counted; the owner has not ruled on whether Sol's label is right. Recorded in KF-018 and KF-056 to KF-059, `EVALUATION.md`, `RESUME_METRICS.md`, `README.md` and `docs/FINAL_REPORT.md`. Follow-ups are listed in `ROADMAP.md`, not started.

## 2026-10-20 (later): Correction of wording in the independent-author entry and related docs

Appended correction; earlier entries are unchanged and the decision itself (intensity miss recorded as an open limit, not tuned) stands. Earlier text said the 26 of 30 on provider intensity "was partly produced by data shaped to fit the tool". That cause was an inference, not tested. The wording is now: the 26 of 30 (our own generated data) does not carry over to an independent author's data (0 of 10); the cause is not established. Candidate causes, not ranked: peer-baseline skew from 20 test providers in one specialty of 45 (KF-017 family; a flaw of the brief), outliers only mildly above ordinary providers, and the fixed 3.5 cutoff. The 3.21 hand calculation is exploratory, not a scored result. Where earlier entries (for example the Phase 3 held-out run, "claim-level 100%, outliers 26 of 30") state results, they refer to our own generated data. Docs updated: KNOWN_FAILURES.md (KF-018, KF-056), EVALUATION.md, RESUME_METRICS.md, README.md, docs/FINAL_REPORT.md.

## 2026-11-03: Human check of the calibration labels (KF-041): method, written before any owner label exists

The owner chose follow-up (b) from `ROADMAP.md` (a human check of the model-drafted calibration
labels, about 20 minutes). The method below was fixed and committed before the owner saw the
sheet.

| Decision | Options | Choice | Why |
|---|---|---|---|
| Scope | A: re-label the full 40-item sheet (about an hour); B: only the rows that decide calibration; C: skip and keep the A4 caveat | B | KF-041 names exactly these rows as closing most of the weakness: the 19 CANNOT_TELL statements, the 2 false-supported statements (L11.7: judge SUPPORTED against a PARTLY draft; L24.3: SUPPORTED against a CANNOT_TELL draft, also one of the 19), and the 8 conflict answers. 19 items, 36 prompts, about 30 minutes |
| Source text shown | A: the same 900-character cut the draft labeller and the judge saw; B: full text | B | With A the owner would also have to answer CANNOT_TELL wherever the cut removed the evidence, so the review would test the display again instead of the writer (KF-041). Consequence, disclosed with the new calibration numbers: on these rows the reference sees more than the judge did, so a disagreement can reflect the cut-off rather than a judge error |
| Blinding | A: show the draft label for confirm-or-challenge; B: blind sheet, compare after | B | Confirm-or-challenge anchors; an independent label is stronger evidence. The audit key (draft and judge labels per row) stays in a separate file the owner opens only after labelling |
| Disagreement handling | A: the owner's letter always replaces the draft row; B: adjudicate each disagreement first | A | The owner is the reference standard. Every change is listed verbatim in `SESSION_LOG.md`. Thresholds, cases, rubrics and the registered acceptance rule are unchanged, and the calibration outcome (accepted or not) is reported, not tuned |
| Merge mechanics | A: replace only the reviewed rows in `eval/phase7_model_drafted_labels.jsonl`, stamped `label_source="owner-hand"`; B: a parallel labels file | A | Per-row provenance was designed for mixed sources (A4); git history keeps the draft; `calibrate` needs no change |
| DUP-D-10 | Ask the owner to rule on Sol's decoy label at the same sitting | Ask | KF-057 leaves the ruling to the owner; under the independent-test pre-registration the false alarm stays counted either way |

New code: `src/claims_copilot/evals/owner_review.py` (prepare/check/ingest; deterministic; no
provider calls, no spend) and `tests/test_evals_owner_review.py`. Sheet and audit key:
`eval/labeling/phase7_owner_review_sheet.md` and `phase7_owner_review_key.json`.

## 2026-11-03 (later): Owner decisions — publication gates, container, browser, DUP-D-10 ruling

Six decisions made by the owner in one sitting (structured questions, recommendations shown).

| Decision | Options | Choice | Consequence |
|---|---|---|---|
| Container verification (KF-053) | A: install colima + docker CLI via Homebrew, build, run, test; B: Docker Desktop; C: defer | A | Blocked the same day: Homebrew is not installed on this machine (macOS 13.6.7, arm64; no MacPorts or nix either), so the approved path needs Homebrew installed first — a separate gate, presented after the rest of the day's work |
| Browser pass (KF-052) | A: one-time local-only browser pass on `/workbench`; B: keep the no-browser rule | A | Reverses the no-browser rule ONCE, scoped: the locally served workbench on 127.0.0.1 only, no external sites. The rule itself is unchanged |
| License | A: MIT; B: Apache-2.0; C: other | MIT | `LICENSE` added (copyright holder: the git author handle `bowierliu`; changeable before publishing). The third-party policy corpus is not distributed, so nothing in the repo conflicts with MIT |
| Product name | A: keep `claims-copilot` and run the real USPTO search plus PyPI/GitHub/domain re-checks before publishing; B: third naming batch; C: pick a 2026-10-16 survivor | A | The checks are the gate; results recorded in `SESSION_LOG.md` |
| Visibility | A: public; B: private | Public | A resume showcase needs public. Still required before publishing: the owner's own read-through for employer-specific terms and a gitleaks re-run over full history. The owner publishes himself |
| DUP-D-10 (KF-057) | A: Sol's decoy label is right; B: wrong; C: unsure | A | The owner rules the tool's signature too broad here: different place of service and diagnosis make the pair genuinely distinct services. The false alarm STAYS COUNTED (independent-test pre-registration). Any signature change is a separate pre-registered change on fresh independent data |

## 2026-11-03 (later still): Browser decision reversed by the owner; name checks reopen the name gate

Appended entries; earlier decisions stand except where this entry says otherwise.

1. **Browser use.** The owner reversed the no-browser decision in chat ("approve reversing the
   existing browser decision and always run"). The earlier one-time local-only approval is
   superseded: browser tooling may be used without a per-call gate. `.cursor/rules/security.mdc`
   updated to match. Unchanged: no GitHub remote, push, or publishing, and no touching GitHub in
   a browser. The KF-052 pass itself stayed local-only (127.0.0.1) in any case.
2. **Name.** The 2026-11-03 keep-`claims-copilot` decision was conditional on the USPTO, PyPI,
   GitHub and domain checks. The checks (facts in `SESSION_LOG.md`, 2026-11-03) found: PyPI/npm
   free and no live USPTO registration for the exact plural, but a dead USPTO application for
   CLAIM COPILOT in medical claim management, active commercial "Claims Copilot" use by Office
   Ally, DENmaar, Aon and ICICI Lombard, and 10+ exact-name GitHub repos, two of them in health
   claims. The condition is therefore not cleanly met: keep-vs-rename returns to the owner as an
   open decision. No rename has been made and nothing has been published.

## 2026-11-03 (rename): Product renamed claims-copilot -> ClaimSignal

The owner chose to rename (the name checks had reopened the gate), then picked the new name from
three checked candidates presented with their availability results.

| Candidate | Checks (2026-11-03) | Outcome |
|---|---|---|
| PrepayLens | 0 exact GitHub repos, PyPI free, `prepaylens.com`/`prepay-lens.com` appear unregistered, no product or trademark found | Recommended; not picked |
| FlagFolio | PyPI free, `flagfolio.com` appears free; an iPhone flags-education app uses the name, 2 small GitHub repos | Not picked |
| ClaimSignal | PyPI free, `claimsignal.com` appears unregistered; claimsignal.io is a live unrelated product (claimant proof for mass arbitrations) | **Picked by the owner, caveat accepted** |

Scope of the rename: `PRODUCT_NAME` ("ClaimSignal"), the distribution name in `pyproject.toml`
(`claimsignal`), deploy image names (`claimsignal-api`), the fetch user-agent, and
current-facing docs (README, AGENTS, ROADMAP, FINAL_REPORT, this repo's rules). Not renamed:
the Python package `claims_copilot`, module CLI paths, `CLAIMS_COPILOT_*` env vars, and the data
layout — internal identifiers whose churn would add risk without changing what a reader sees.
Historical records (SESSION_LOG, DECISIONS, phase reports) keep the old name as written.
Also decided at the same sitting: the owner will install Homebrew, after which colima + docker
CLI are installed and the container verification (KF-053) runs.

## 2026-11-03 (design): Warm workbench redesign

The owner asked for a warmer, more distinctive workbench, learning from a reference
landing page's tone without copying it. Options were put to the owner with the structured
question tool before any code changed.

| Decision | Options | Choice | Why |
|---|---|---|---|
| Scope | A: workbench only; B: workbench + landing page; C: landing only | A | The workbench is the only page; a landing page would need claims the project cannot cite, and testimonials/pricing would be fabrication |
| Palette | A: warm cream/brown + soft sky blue; B: warm neutrals, keep blue; C: keep current | A | The reference quality the owner liked; contrast re-checked to AA after the change |
| Interactive moment | A: example chips + typed hint running the real forms; B: simulated tour; C: none | A | A simulated demo would show fake behaviour in an evidence tool; the chips run real read-only lookups on synthetic ids |
| Imagery | A: original inline SVG; B: CSS only; C: owner-provided assets | A | CSP allows same-origin only and the repo had no assets; an original mark costs nothing |

Also fixed, found during browser verification: the `data:,` favicon was blocked by the
page's own CSP (`img-src 'self'`), so the mark is also served as `favicon.svg` from the
existing allowlist (one line in `workbench.py`). Reference "conversion" elements were
translated, not copied: repeated primary actions per view and honest microcopy
(synthetic, read-only, cited, human decides). No routes, endpoints, element ids,
boundary text, or rendering-safety rules changed. Spend: $0.

## 2026-11-07: Independent MODEL re-review replaces the pending owner re-review (KF-041); method fixed before any reviewer output

Decided by the owner's task instruction of 2026-11-07 (not on the owner's behalf). The owner label
sheet (`eval/labeling/phase7_owner_review_sheet.md`) was never labelled, so it is no longer a
human-review task. It becomes a blind independent re-review by a fresh isolated model. **Nothing in
this entry is human or owner review, and no output of it may be stamped `owner-hand`, `human` or
`human-validated`.**

| Decision | Options | Choice | Why |
|---|---|---|---|
| Reviewer | A: Claude Sonnet 5.5 in a fresh isolated task; B: a second GPT run; C: wait for the owner | A | Instructed. It is a different run, not a different family, from the existing Claude judge: Claude Sonnet shares a model family with it (disclosed in every row and report). The orchestrating agent is also Claude Sonnet 5.5, so the review's independence rests on isolation, not on a different model. The task tool lets us name the model but not an effort level, so "Medium" is requested in the brief and recorded as unverifiable |
| Isolation | A: package only; B: whole repository | A | The reviewer gets a sanitized package copied to a folder outside the repository: both rubrics (intro and owner-specific sections removed), the 19 items with full cited text, the 36 unanswered prompts, a response schema. It gets no draft or judge labels, no key, no scorecards, no `DECISIONS.md`, `KNOWN_FAILURES.md` or `SESSION_LOG.md`, no model names, and no wording on why items were chosen. Item ids are renamed R01 to R19 so gaps in the sample do not show. Limit: the task tool has no filesystem sandbox, so "package only" is enforced by instruction and by giving it only that path, not by access control |
| Output | A: letters in a sheet; B: one JSON object | B | Exactly one answer per prompt, validated deterministically (no missing, extra, duplicate or invalid answers; one json fence tolerated, other prose refused); nothing is repaired or guessed. A refused response is reported and rerun, not edited |
| Provenance | A: reuse `owner-hand`; B: a distinct source | B | `claude-sonnet-5-5-independent-review`, with reviewer model, method, package sha256, run id, `blind`, `model_generated`, effort and same-family flags on every row. The human labelling CLI cannot write it; `calibrate.read_labels` refuses a model row that claims a human source or lacks provenance; `owner-hand` behaviour is unchanged |
| Artifacts | A: overwrite the draft labels; B: derived files | B | `eval/phase7_model_drafted_labels.jsonl` (GPT Sol, sha256 pinned in a test) and `phase7_judge_calibration.json` stay as they are. New: `phase7_claude_review_labels.jsonl` (36 reviewed rows), `phase7_mixed_model_reference_labels.jsonl`, `claude_review_provenance.json`, and `eval/scorecards/phase7_judge_calibration_views.json` |
| Views | n/a | Fixed now | (1) Mixed-model reference: Claude replaces GPT Sol on all 36 reviewed prompts, other rows stay GPT Sol-derived; never "human validation" or "full independent relabelling". (2) Consensus-only sensitivity: only reviewed rows where both agree (a conflict row needs its label and its pattern to agree); unreviewed rows are not consensus and are excluded; disagreements stay unresolved and the main agent adjudicates none. A secondary variant (original rows minus contested rows) is reported as such. Thresholds, rubrics and the acceptance rule are the pre-registered ones, unchanged |
| Judge disagreement | A: tune the judge; B: report | B | The calibration outcome is reported whichever way it falls. The human-label gap stays open in `KNOWN_FAILURES.md` |

Code: `evals/model_review.py` (package builder, response validator, rows, views, CLI),
`evals/labels.py` (`MODEL_REVIEW_SOURCE`, `validate_model_rows`), `evals/calibrate.py` (accepts
the model source with provenance; provenance says mixed-model and not human validated). Tests:
`tests/test_evals_model_review.py`. Cursor model usage is outside the project budget
(`budget/`); this review makes no `CostGuard` call and no project spend.

## 2026-11-07: Provider-intensity v2 pre-registered before any fresh data exists

Decided by the owner's task instruction of 2026-11-07 (KF-056 follow-up). v1 is the immutable
control; v2 is additive and experimental.

| Decision | Options | Choice | Why |
|---|---|---|---|
| Method | A: retune v1's z cutoff; B: volume-aware exact-binomial v2 | B | v1's z does not use volume, and retuning on failed data is forbidden. v2 uses each provider's own volume as evidence |
| Constants | Chosen before data | `MIN_VISIT_LINES` 40, `MIN_PEERS` 20, Bonferroni 0.05, `P0` clamp [0.02, 0.98], gap >= 0.10 above peer P75, abstain when the peer median >= 0.50 | From the statistic's definition and practice, not from any label or score. Frozen in `eval/provider_intensity_v2_preregistration.json` (sha256 in `docs/PROVIDER_INTENSITY_V2_PREREGISTRATION.md`), pinned by tests |
| Gate | Suggested by the owner | recall >= 0.80; recall gain over v1 >= 0.20; false-positive rate (ordinary + decoy) <= 0.05; false alarms <= v1; Wilson intervals and all abstentions reported | Adopted unchanged; all must pass |
| Fixture format | A: claim-level (heavy); B: aggregated visit counts per provider, loaded as single-line visit claims | B | The check only uses per-provider visit counts; both versions run through the real repository path. Stated as a limit |
| Author | A: DeepSeek V4.1 Flash High (preferred, a different family); B: Claude Sonnet 5.5 isolated task (the only model the task tool offers besides the session's own); C: paid OpenAI call through CostGuard | B, disclosed | DeepSeek is not available in this environment (no task-tool slug, no project provider adapter), and C needs paid-call approval the task said should not be needed. The author is therefore the same family as the main agent, isolated by context only. This weakens independence and is recorded with the result |
| If v2 fails | A: tune; B: keep experimental and record | B | Registered failure handling; no re-scoring with different constants |

Code: `tools/patterns_v2.py`, `evals/intensity_v2.py`; tests `tests/test_tools_patterns_v2.py`,
`tests/test_evals_intensity_v2.py`. No paid calls; no CostGuard use.

## 2026-11-07: Line-level independent evaluation (report only)

| Decision | Options | Choice | Why |
|---|---|---|---|
| Label format | A: new per-line label file; B: extend the claim-level labels with `case_kind`, `line_refs`, `tempting_line_refs` | B | Reuses the existing validator and store builder unchanged; the extension keys are split off before the claim-level validation, so nothing is repaired |
| Scope | All five types vs line-level only | Unbundling, excess units, date anomaly | Duplicates are whole-claim and intensity is provider-level; they stay out of line denominators |
| Expected lines for unbundling | A: component and comprehensive; B: component only | B (stated in the brief before the author wrote anything) | The component is the line that should not be paid separately. The tool cites both, so exact-match is 0/12; recorded as KF-063 rather than changing the label convention after seeing results |
| Author | Same trade-off as intensity v2 | Claude Sonnet 5.5 isolated task, disclosed | DeepSeek unavailable; independence by context isolation only (KF-064) |
| Tool changes | Fix the over-citation now vs report | Report only | The task fixed this run as report-only; a fix needs new data to be tested against |

Code: `evals/line_level.py`; tests `tests/test_evals_line_level.py`. No paid calls; no CostGuard use.
