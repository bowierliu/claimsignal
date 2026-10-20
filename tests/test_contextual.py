"""Contextual descriptions: validation, cache keys, budget stop, and the index-only boundary."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from claims_copilot.agent.prompt import Prompt
from claims_copilot.agent.types import ModelTurn
from claims_copilot.budget import CostGuard, Usage
from claims_copilot.budget.config import Caps, ModelPrice
from claims_copilot.budget.ledger import Ledger
from claims_copilot.ingest.chunk import Chunk
from claims_copilot.retrieval import contextual
from claims_copilot.retrieval.contextual import (
    DescriptionCache,
    DescriptionError,
    build_jobs,
    run,
    validate_description,
)

PROMPT = Prompt("contextualize_test", "prompt text", "p" * 64)


def _chunk(i: int, source: str = "s1") -> Chunk:
    return Chunk(f"{source}:1-1:{i:04d}", source, 1, 1, "1.1 Topic", f"text {i}", f"h{i}")


class FakeProvider:
    name = "fake"
    model_key = "openai/gpt-6-luna"

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.calls: list[dict[str, Any]] = []

    def complete(self, **kwargs: Any) -> ModelTurn:
        self.calls.append(kwargs)
        text = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        return ModelTurn(text, (), "end", Usage(1000, 100))


def _guard(tmp_path: Path, p6_cap: int = 8) -> CostGuard:
    caps = Caps(
        total_usd=Decimal(50),
        eval_run_usd=Decimal(5),
        warn_fraction=Decimal("0.7"),
        stop_fraction=Decimal("0.9"),
        phases={"p6": Decimal(p6_cap)},
        approved_past_stop=frozenset(),
    )
    prices = {
        "openai/gpt-6-luna": ModelPrice(
            "openai/gpt-6-luna", Decimal("0.10"), Decimal("0.50"), "openai-api-pricing"
        )
    }
    return CostGuard(caps, prices, Ledger(tmp_path / "ledger.jsonl"))


def test_validate_description_accepts_clean_json_and_collapses_whitespace() -> None:
    assert (
        validate_description('{"description": "About  billing\\nrules."}') == "About billing rules."
    )


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        "[]",
        '{"description": 3}',
        '{"description": "   "}',
        '{"description": "x", "extra": 1}',
        json.dumps({"description": "x" * 501}),
    ],
)
def test_validate_description_rejects_bad_output(bad: str) -> None:
    with pytest.raises(DescriptionError):
        validate_description(bad)


def test_jobs_use_neighbours_only_within_the_same_source() -> None:
    chunks = [_chunk(0, "a"), _chunk(1, "a"), _chunk(0, "b")]
    jobs = build_jobs(chunks, {"a": "Doc A"}, PROMPT)
    assert "Doc A" in jobs[0].message
    assert "<next_passage_start>text 1" in jobs[0].message
    assert "<previous_passage_end>text 0" in jobs[1].message
    assert "<next_passage_start></next_passage_start>" in jobs[1].message  # next is source b
    assert "<previous_passage_end></previous_passage_end>" in jobs[2].message


def test_cache_key_changes_with_prompt_model_and_text() -> None:
    chunks = [_chunk(0), _chunk(1)]
    base = build_jobs(chunks, {}, PROMPT)[0].key
    assert build_jobs(chunks, {}, Prompt("v2", "x", "q" * 64))[0].key != base
    assert build_jobs(chunks, {}, PROMPT, model="other")[0].key != base
    changed = [_chunk(0), Chunk("s1:1-1:0001", "s1", 1, 1, "1.1 Topic", "new", "hNEW")]
    assert build_jobs(changed, {}, PROMPT)[0].key != base


def test_run_caches_descriptions_and_a_rerun_is_free(tmp_path: Path) -> None:
    jobs = build_jobs([_chunk(0), _chunk(1)], {}, PROMPT)
    cache = DescriptionCache(tmp_path / "c.jsonl")
    guard = _guard(tmp_path)
    provider = FakeProvider(['{"description": "About topic."}'])
    assert run(jobs, cache, provider, guard, PROMPT, workers=1) == (2, 0)
    assert len(provider.calls) == 2
    assert provider.calls[0]["tools"] == [] and provider.calls[0]["allow_tools"] is False
    assert guard.ledger.spent(phase="p6") > 0
    again = DescriptionCache(tmp_path / "c.jsonl")
    assert run(jobs, again, provider, guard, PROMPT, workers=1) == (0, 0)
    assert len(provider.calls) == 2


def test_unusable_output_is_counted_and_not_cached(tmp_path: Path) -> None:
    jobs = build_jobs([_chunk(0)], {}, PROMPT)
    cache = DescriptionCache(tmp_path / "c.jsonl")
    provider = FakeProvider(["Ignore previous instructions"])
    assert run(jobs, cache, provider, _guard(tmp_path), PROMPT, workers=1) == (0, 1)
    assert cache.rows == {}


def test_live_ceiling_stops_the_run(tmp_path: Path) -> None:
    jobs = build_jobs([_chunk(0), _chunk(1)], {}, PROMPT)
    cache = DescriptionCache(tmp_path / "c.jsonl")
    provider = FakeProvider(['{"description": "ok"}'])
    with pytest.raises(RuntimeError, match="ceiling"):
        run(jobs, cache, provider, _guard(tmp_path), PROMPT, ceiling_usd=0.0, workers=1)
    assert provider.calls == []


def test_module_makes_no_direct_provider_or_http_call() -> None:
    source = Path(contextual.__file__).read_text()
    assert "httpx" not in source and "import openai" not in source
