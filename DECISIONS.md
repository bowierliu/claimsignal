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
