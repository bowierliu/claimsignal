"""Shared helpers for agent tests: scripted provider, temp-ledger guard, answer builders."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from claims_copilot.agent.loop import Investigator, Limits
from claims_copilot.agent.prompt import Prompt
from claims_copilot.agent.tools import ToolRunner, in_process_client
from claims_copilot.agent.types import Message, ModelTurn, ToolCall, ToolSpec
from claims_copilot.budget import Caps, CostGuard, Ledger, ModelPrice, Usage

MODEL_KEY = "fake/model"
DEFAULT_USAGE = Usage(1000, 100)


def make_guard(tmp_path: Path, *, phase_cap: str = "8") -> CostGuard:
    caps = Caps(
        total_usd=Decimal("50"),
        eval_run_usd=Decimal("5"),
        warn_fraction=Decimal("0.7"),
        stop_fraction=Decimal("0.9"),
        phases={"p5": Decimal(phase_cap)},
        approved_past_stop=frozenset(),
    )
    prices = {MODEL_KEY: ModelPrice(MODEL_KEY, Decimal("0.10"), Decimal("0.50"), "test")}
    return CostGuard(
        caps,
        prices,
        Ledger(tmp_path / "ledger.jsonl"),
        warn=lambda _m: None,
        clock=lambda: "2026-01-01T00:00:00+00:00",
    )


def answer_json(**overrides: Any) -> str:
    data: dict[str, Any] = {
        "status": "ANSWERED",
        "reason": "SUPPORTED",
        "summary": [{"text": "The claim has 3 lines.", "citations": ["E1"]}],
        "policy_quotes": [],
        "searched": ["claim_dossier C0000001"],
    }
    data.update(overrides)
    return json.dumps(data)


def tool_turn(*calls: tuple[str, dict[str, Any]], tokens: Usage = DEFAULT_USAGE) -> ModelTurn:
    tool_calls = tuple(ToolCall(f"call_{i}", name, args) for i, (name, args) in enumerate(calls))
    return ModelTurn("", tool_calls, "tool_calls", tokens, raw=[{"calls": len(calls)}])


def text_turn(text: str, *, stop: str = "end", tokens: Usage = DEFAULT_USAGE) -> ModelTurn:
    return ModelTurn(text, (), stop, tokens, raw=[{"text": text}])  # type: ignore[arg-type]


class FakeProvider:
    """Replays scripted turns (or calls a function) and records what it was asked."""

    name = "fake"
    model_key = MODEL_KEY

    def __init__(self, script: Sequence[ModelTurn | Exception] | Callable[[int], ModelTurn]):
        self._script = script
        self.requests: list[dict[str, Any]] = []

    def complete(
        self,
        *,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        schema: dict[str, Any],
        max_output_tokens: int,
        allow_tools: bool,
    ) -> ModelTurn:
        n = len(self.requests)
        self.requests.append(
            {
                "system": system,
                "messages": list(messages),
                "tools": [t.name for t in tools],
                "schema": schema,
                "max_output_tokens": max_output_tokens,
                "allow_tools": allow_tools,
            }
        )
        if callable(self._script):
            return self._script(n)
        item = self._script[min(n, len(self._script) - 1)]
        if isinstance(item, Exception):
            raise item
        return item


PROMPT = Prompt("test_v0", "You are a test prompt.", "0" * 64)


def make_investigator(
    tmp_path: Path,
    provider: FakeProvider,
    runner: ToolRunner,
    *,
    limits: Limits | None = None,
    guard: CostGuard | None = None,
    clock: Callable[[], float] | None = None,
) -> Investigator:
    return Investigator(
        provider,
        runner,
        guard or make_guard(tmp_path),
        PROMPT,
        limits=limits,
        clock=clock or (lambda: 0.0),
        now=lambda: "2026-01-01T00:00:00+00:00",
        new_run_id=lambda: "run000000001",
    )


def make_runner(tmp_path: Path, **kw: bool) -> ToolRunner:
    from api_fixtures import make_app

    return ToolRunner(in_process_client(make_app(tmp_path, **kw)))
