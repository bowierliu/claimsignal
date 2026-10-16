---
name: cost-guard
description: How to make a paid API call or add a paid model through the CostGuard (estimate, refuse over cap, ledger). Use before writing any code that calls an LLM, embedding, or other paid endpoint.
---

# Cost guard

All spend is controlled by `claims_copilot.budget.CostGuard` (`src/claims_copilot/budget/`).

## Making a paid call

```python
guard.call(
    lambda: client.embed(batch),
    usage_of=lambda result: Usage(result.prompt_tokens, 0),
    phase="p0",  # key from budget/caps.toml
    model_key="openai/text-embedding-3-small",  # must exist in budget/prices.toml
    purpose="what this call is for",
    estimated_usage=Usage(estimated_input_tokens, estimated_output_tokens),
    eval_run_id=None,  # set for evals so the per-run cap applies
)
```

Behaviour: prices the estimate, checks total, phase, and eval-run caps, refuses before spending if
a cap would be exceeded, warns at 70%, refuses at 90% unless the owner listed the scope in
`approved_past_stop`, and appends every call to `budget/ledger.jsonl`. Failed calls are charged at
their estimate. Estimates must be conservative (tokens are roughly 1 per 3 UTF-8 bytes here).

## Rules

- Never call a provider SDK or paid HTTP endpoint outside the guard.
- Never edit `budget/caps.toml`; only the owner raises caps.
- Add a price to `budget/prices.toml` only with a VERIFIED manifest `source_id` (fetch the vendor
  pricing page first). Unpriced models are refused.
- Build a dry-run path (estimate only) and require `--confirm` to spend.
- Check key presence with `has_secret("NAME")` only; never print a key.
- Check spend: `uv run python -m claims_copilot.budget`. Tests use a temp ledger and fake clients.
