# Deployment

The public recruiter demo runs on [GitHub Pages](https://bowierliu.github.io/claimsignal/). Model-assisted investigations run in the [local launcher](../README.md).

On November 21, 2026, GitHub Actions built the offline API image from the Dockerfile and ran it on a temporary Linux runner. The health route succeeded. A synthetic claim dossier returned 401 without the local API key and returned the expected claim with the key. The running process had UID 10001, the synthetic payer database was present, and the ground-truth database was absent. Rerun **Actions → Verify the offline API container → Run workflow** to repeat these checks. The Compose and AWS Fargate templates have separate infrastructure requirements; no AWS service was provisioned. [Container verification run](https://github.com/bowierliu/claimsignal/actions/runs/44958597297)

## What ships

- `Dockerfile`: two stages on `python:3.12-slim`. The build stage installs locked dependencies with
  `uv sync --frozen --no-dev`, generates the synthetic dataset (deterministic, free, offline) into
  `/tmp`, and copies **only `payer.sqlite`** into the image. `truth.sqlite` (the answer key) is never
  copied. The runtime stage runs as uid 10001, has a health check on `/v1/health`, and starts
  `deploy/entrypoint.sh`.
- `deploy/entrypoint.sh`: refuses to start (exit 78) unless `CLAIMS_COPILOT_API_KEY` is set, never
  prints it, then runs the API on the container network with `--allow-remote` and lexical policy
  mode.
- `deploy/compose.yaml`: local run, published on `127.0.0.1` only, read-only root filesystem, all
  capabilities dropped, `no-new-privileges`, memory and process limits, the key required from the
  caller's environment.
- `deploy/ecs-task-definition.json`: an AWS Fargate task template. The key comes from Secrets
  Manager (`secrets.valueFrom`), not `environment`. Read-only root filesystem, non-root, capabilities
  dropped. Account, region, role, secret, and image values are placeholders to fill in.
- `.dockerignore`: keeps `.env`, `.git`, `data/`, tests, docs, and evaluation files out of the build
  context.

## What does not ship, on purpose

- **No policy search.** The corpus text, chunks, and indexes are derived from third-party documents
  with their own terms, so they stay local (`data/` is gitignored and dockerignored). The container
  reports policy search as off. A private deployment that is allowed to hold those files can mount
  `data/chunks` read-only at `/app/data/chunks`; check each source's terms in `SOURCES/manifest.jsonl`
  first.
- **No model provider keys, and no agent.** The API has no model call. The agent runs from the
  command line or the evaluation runner, with `CostGuard` and the local budget ledger.
- **No TLS, no WAF, no per-user login.** Terminate TLS and rate-limit at the load balancer; the
  in-process limit is per worker (KF-049).

## Run the offline API locally with Docker Compose

```bash
export CLAIMS_COPILOT_API_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
docker compose -f deploy/compose.yaml up --build
# then open http://127.0.0.1:8000/workbench and paste the key into the page
```

## Before this is more than a template

1. Verify the Compose configuration in the target environment and pin base images by digest.
2. Send the audit log somewhere the application cannot rewrite it (the task's `audit` volume is
   ephemeral; a restart loses it). Record the latest chain hash outside the host.
3. Put the service behind a load balancer with TLS and a rate limit; restrict inbound traffic.
4. Give the task role no permissions it does not need (it needs none for this service).
5. Scan the image for known vulnerabilities and the dependency lock for advisories.
6. Review `docs/SECURITY.md` section 6 before any real member data goes near it.
