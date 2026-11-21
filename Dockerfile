# syntax=docker/dockerfile:1
#
# The API and workbench on synthetic data. No credentials, no third-party source files, and no
# ground-truth labels go into the image. The manual GitHub Actions container check builds and runs it;
# see docs/DEPLOYMENT.md for its scope.

FROM python:3.12-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir uv==0.11.25
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY prompts ./prompts
COPY SOURCES ./SOURCES
RUN uv sync --frozen --no-dev
# Generate the synthetic dataset (deterministic, free, offline) outside the final data directory,
# then keep only payer.sqlite: truth.sqlite holds the answer key and never ships.
RUN .venv/bin/python -m claims_copilot.synth --out /tmp/synth \
    && mkdir -p data/synth \
    && cp /tmp/synth/payer.sqlite data/synth/payer.sqlite \
    && rm -rf /tmp/synth

FROM python:3.12-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app /app
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
# Only these two directories are writable at run time; everything else can be mounted read-only.
RUN chmod 0555 /usr/local/bin/entrypoint.sh \
    && mkdir -p data/audit data/traces \
    && chown -R app:app data/audit data/traces
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/v1/health', timeout=3).status == 200 else 1)"]
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
