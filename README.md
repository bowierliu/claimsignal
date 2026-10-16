# claims-copilot

A claims investigation and payment integrity copilot for a health plan, built only on synthetic
data and verified public sources. It helps a human investigator assemble and assess evidence for
flagged claims. It never decides fraud, denial, coverage, or medical necessity; the human decides.

## Status

Phase 0 (source corpus and baseline retrieval) is in progress. No results yet: this section will
report measured retrieval and evaluation numbers as phases complete. See `ROADMAP.md` once Phase 1
lands.

## Design (planned)

1. Retrieval over verified public policy and coding sources (CMS, CDC/NCHS, HHS-OIG, eCFR).
2. Deterministic, tested tools for exact lookups and calculations.
3. A bounded LLM agent that orchestrates both and writes a cited evidence summary, validated
   deterministically after generation.

## Development

```bash
uv sync
uv run pytest
uv run ruff check && uv run ruff format --check
uv run mypy
uv run pre-commit run --all-files
uv run python -m claims_copilot.budget   # API spend vs caps
```

Copy `.env.example` to `.env` and fill in keys locally. Never commit `.env`.
