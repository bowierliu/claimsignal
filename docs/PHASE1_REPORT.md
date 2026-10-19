# Phase 1 report: project foundation

Status: **approved by the owner on 2026-10-19**. The old-repo deletion gate is complete (below).

## 1. Executive summary

Phase 1 turned the Phase 0 code into a project that an agent or a person can work in safely.

- **Working agreement.** `AGENTS.md` now holds the product definition, the 8 hard rules, cost
  discipline, commands, a repository map, conventions, the phase workflow, the prompt policy, and
  the definition of done.
- **Cursor setup**, checked against the current Cursor docs on 2026-10-16:
  - 5 scoped rules in `.cursor/rules/*.mdc` (python style, testing, provenance, security, cost).
  - 6 skills in `.cursor/skills/` (source-verification, eval-running, decision-logging,
    cost-guard, and the explicit-only `/phase-report` and `/teach`).
  - 2 subagents in `.cursor/agents/`: `file-scout` (read-only, `composer-2`) and
    `source-verifier`.
  - Custom slash commands are not documented by Cursor for projects, so `/teach` and
    `/phase-report` are skills with `disable-model-invocation`, as the docs recommend.
- **Records**: README (results first), `docs/ARCHITECTURE.md`, `EVALUATION.md`,
  `KNOWN_FAILURES.md` (10 entries), `ANSWER_BOUNDARY.md`, `DATA_MODEL.md`, `RESUME_METRICS.md`.
  Parts that are not built yet are labelled design or not designed.
- **CI**: `.github/workflows/ci.yml` (ruff, mypy, pytest). It has never run because there is no
  GitHub remote.
- **A guard test** (`tests/test_repo_structure.py`) checks skill, agent, and rule frontmatter and
  that every local doc link resolves, because Cursor silently ignores misnamed files.
- **A correction.** The Phase 0 report said about 1 in 5 questions were missed by both retrieval
  methods. Measured on the cached index it is 4 of 40 (10%); the corrected text is in
  `docs/PHASE0_REPORT.md`.
- **Naming.** 20 candidates were researched with real PyPI, GitHub, DNS, and web checks. 14 were
  rejected and none of the other 6 was clean (one was high-risk), so you chose to keep `claims-copilot` and
  decide before publishing. Evidence is in `DECISIONS.md`.

## 2. Metrics and spend

| Item | Value | How measured |
|---|---|---|
| Tests | 125 passing | `uv run pytest` |
| Quality gates | ruff, ruff format, mypy (strict), all pre-commit hooks incl. gitleaks green | `uv run pre-commit run --all-files` |
| Spend, all of Phase 0 and 1 | $0.0166 of the $50 total cap | `uv run python -m claims_copilot.budget` |
| Phase 1 spend | $0.00 of the $1 cap | same; Phase 1 made no paid calls |

The name research and these docs used no paid APIs through the cost guard. Reminder: check
Cursor's own usage yourself; agents cannot see it, and subagents (the research runs above) count
against it.

## 3. Failures and open risks

- CI is unexercised until publish. Pinned action versions were the latest releases observed
  on 2026-10-16.
- `file-scout` uses `composer-2` as you chose; Cursor may substitute another model on plans that
  do not include it. I have not run it against the repository yet.
- The brief asked for a Cursor `/teach` command; because commands are undocumented it is a
  skill. If it does not appear as `/teach` in your Cursor, tell me.
- The old repo's git history contained real CPT codes (one of its commits replaced them with
  placeholders). The archive is the only remaining copy and stays outside this repository; never
  copy anything from it into this repo without checking it first.
- Carried from Phase 0: provisional gold set, CPT redaction is heuristic, three terms pages
  unreadable (see `KNOWN_FAILURES.md`).
- The vault repo's `.gitignore` edit that excludes this project is still uncommitted in the vault
  repo (yours to commit).

## 4. Decisions

1. **Old-repo deletion gate: complete (2026-10-19).** After the owner typed `DELETE OLD REPO`, I
   first verified that the archive `~/Projects/hc_rag_proj_archive_2026-10-16.zip` matched sha256
   `bd53c73cb26d...f36263` and passed `unzip -t`, and that the old repo's working tree was clean at
   the same HEAD (`7a1a8e6`). I also confirmed the one git-ignored file of value,
   `docs/INTERVIEW_NOTES.md`, is byte-identical inside the archive. Then I deleted only the folder
   `~/Projects/hc_rag_proj`. It is gone; the archive remains. Lost on purpose: `.env` (old key,
   which the owner revokes), `.venv`, caches. There was no Desktop backup.
2. **Phase 1 approved by the owner (2026-10-19).**

Decided in this phase: product name deferred to pre-publish; `eval-runner` subagent deferred to
Phase 6/7.

## 5. Teach me

Run `/teach <concept>` on any of these:

1. **Hybrid retrieval and reciprocal rank fusion**: why combining BM25 and dense should beat
   either (Phase 6; see the overlap numbers in `EVALUATION.md`).
2. **The cost guard**: pre-call estimation, refusing over a cap, and the ledger
   (`src/claims_copilot/budget/`).
3. **Provenance manifest**: why a citation must resolve to a fetched, hashed source
   (`SOURCES/manifest.jsonl`).

The owner confirmed understanding on 2026-10-19.
