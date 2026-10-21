# Phase 10 report: deployment

Status: complete as artifacts under the owner's standing instruction of 2026-10-20. **Nothing was
built, pushed, or deployed.** Phase 11 starts after this report.

## 1. Executive summary

The repository now has a `Dockerfile`, a `.dockerignore`, an entrypoint, a local compose file, and an
AWS Fargate task template. The design decisions that matter for safety are in the files and tested:
the container runs as a non-root user with a read-only filesystem and no capabilities; it refuses to
start without an API key; the key arrives from the environment or Secrets Manager, never from a
file; the answer key (`truth.sqlite`) and the third-party-derived corpus are not in the image.

The honest status is "written, not built": this machine has no container runtime. I ran the same
server command locally with a generated key and confirmed the behaviour a container would show
(health open, 401 without a key, 200 with one, every request audited, audit chain valid). That does
not prove the image builds (KF-053).

## 2. Metrics and spend

| Item | Value |
|---|---|
| Files | `Dockerfile`, `.dockerignore`, `deploy/entrypoint.sh`, `deploy/compose.yaml`, `deploy/ecs-task-definition.json`, `docs/DEPLOYMENT.md` |
| Tests | 14 static checks in `tests/test_deploy_files.py`, including a real run of the entrypoint's no-key refusal (exit 78) |
| Spend | $0.00. Project total about $2.99 of $50 |

## 3. Failures and open risks

- KF-053: image never built; base images pinned by tag, not digest.
- KF-054: the audit volume is ephemeral on Fargate; a restart resets the chain.
- KF-055: no policy search in the container, by license.
- Bug found while running locally: `data/audit/` was not gitignored, so the first audit file would
  have been committed. Fixed and tested (`.gitignore`, `test_run_output_directories_are_gitignored`).
- Carried: KF-048, KF-049 (single shared key, per-process rate limit).

## 4. Decisions made on the owner's behalf

In `DECISIONS.md` ("Phase 10"): artifacts, not a live deployment; image contents; build-time
dataset; entrypoint that refuses to start without a key; Secrets Manager reference; read-only root;
say "not built" and test what can be tested.

## 5. Teach-me list

1. **Why the answer key is generated outside the data directory in the build.** What would it mean
   for the evaluation if the key shipped in the deployed image?
2. **Read-only root filesystem and dropped capabilities.** What does each stop a compromised process
   from doing?
3. **Where secrets can leak in a container workflow** (build args, image layers, task files, logs) and
   which of these the files here avoid.
