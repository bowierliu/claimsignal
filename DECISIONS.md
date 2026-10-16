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
