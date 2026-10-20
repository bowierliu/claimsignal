"""The bounded tool-calling loop.

One investigation: scope gate, then at most `max_turns` model turns, each of which may call the
allow-listed tools; then one structured answer that plain code validates. Every model call goes
through `CostGuard`. Limits never raise: they end the run with a typed, honest status.
"""

from __future__ import annotations

import functools
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from claims_copilot.agent.answer import FinalAnswer, Reason, Status, answer_schema
from claims_copilot.agent.evidence import EvidenceRegistry, dumps
from claims_copilot.agent.prompt import Prompt
from claims_copilot.agent.scope import BLOCK_MESSAGE, check_request
from claims_copilot.agent.tools import ToolRunner
from claims_copilot.agent.types import (
    AssistantMessage,
    Message,
    ModelTurn,
    Provider,
    ProviderError,
    ToolCall,
    ToolMessage,
    ToolOutput,
    UserMessage,
)
from claims_copilot.agent.validator import invalid, validate_text
from claims_copilot.budget import (
    ApprovalRequiredError,
    BudgetExceededError,
    CostGuard,
    Usage,
    estimate_tokens,
)

PHASE = "p5"
NO_TOOL_CALLS = "no tool call completed before the run ended"
SEARCHED_ITEM_CHARS = 200
SEARCHED_MAX = 10


@dataclass(frozen=True)
class Limits:
    max_turns: int = 8
    max_tool_calls: int = 12
    max_output_tokens: int = 4000
    max_usd: Decimal = Decimal("0.15")
    max_seconds: float = 60.0
    max_prompt_tokens: int = 100_000  # estimate; keeps Haiku below its 100K price step
    max_consecutive_tool_errors: int = 3


@dataclass
class RunRecord:
    run_id: str
    started_at: str
    provider: str
    model_key: str
    prompt_version: str
    prompt_sha256: str
    question: str
    claim_id: str | None
    answer: FinalAnswer
    limit: str | None = None
    turns: list[dict[str, Any]] = field(default_factory=list)
    tool_log: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal(0)
    elapsed_s: float = 0.0
    model_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "provider": self.provider,
            "model_key": self.model_key,
            "prompt_version": self.prompt_version,
            "prompt_sha256": self.prompt_sha256,
            "question": self.question,
            "claim_id": self.claim_id,
            "answer": self.answer.to_dict(),
            "limit": self.limit,
            "turns": self.turns,
            "tool_log": self.tool_log,
            "messages": self.messages,
            "evidence_ids": self.evidence_ids,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": str(self.cost_usd),
            "elapsed_s": round(self.elapsed_s, 3),
            "model_calls": self.model_calls,
        }


def _usage_of(turn: ModelTurn) -> Usage:
    return turn.usage


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _describe_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if isinstance(m, UserMessage):
            out.append({"role": "user", "text": m.text})
        elif isinstance(m, AssistantMessage):
            out.append(
                {
                    "role": "assistant",
                    "text": m.turn.text,
                    "stop": m.turn.stop,
                    "tool_calls": [
                        {"id": c.call_id, "name": c.name, "arguments": c.arguments}
                        for c in m.turn.tool_calls
                    ],
                }
            )
        else:
            out.append(
                {
                    "role": "tool",
                    "outputs": [
                        {
                            "id": o.call_id,
                            "name": o.name,
                            "is_error": o.is_error,
                            "content": o.content,
                        }
                        for o in m.outputs
                    ],
                }
            )
    return out


def _message_text(m: Message) -> str:
    if isinstance(m, UserMessage):
        return m.text
    if isinstance(m, AssistantMessage):
        return m.turn.text + "".join(dumps(c.arguments) + c.name for c in m.turn.tool_calls)
    return "".join(o.content for o in m.outputs)


class Investigator:
    def __init__(
        self,
        provider: Provider,
        tools: ToolRunner,
        guard: CostGuard,
        prompt: Prompt,
        *,
        limits: Limits | None = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], str] = _utc_now,
        new_run_id: Callable[[], str] = _new_run_id,
        phase: str = PHASE,
    ) -> None:
        self._phase = phase
        self._provider = provider
        self._tools = tools
        self._guard = guard
        self._prompt = prompt
        self._limits = limits or Limits()
        self._clock = clock
        self._now = now
        self._new_run_id = new_run_id
        self._schema = answer_schema()

    def run(
        self, question: str, *, claim_id: str | None = None, eval_run_id: str | None = None
    ) -> RunRecord:
        t0 = self._clock()
        record = RunRecord(
            run_id=self._new_run_id(),
            started_at=self._now(),
            provider=self._provider.name,
            model_key=self._provider.model_key,
            prompt_version=self._prompt.version,
            prompt_sha256=self._prompt.sha256,
            question=question,
            claim_id=claim_id,
            answer=FinalAnswer(Status.INVALID_OUTPUT, Reason.SCHEMA_VIOLATION),
        )
        try:
            self._run(record, question, claim_id, eval_run_id, t0)
        finally:
            record.elapsed_s = self._clock() - t0
        return record

    # ------------------------------------------------------------------ internals

    def _run(
        self,
        record: RunRecord,
        question: str,
        claim_id: str | None,
        eval_run_id: str | None,
        t0: float,
    ) -> None:
        limits = self._limits
        gate = check_request(question)
        if gate.blocked:
            record.answer = FinalAnswer(
                Status.OUT_OF_SCOPE, Reason.REQUEST_BLOCKED, issues=(BLOCK_MESSAGE,)
            )
            record.limit = "scope_gate"
            return

        registry = EvidenceRegistry()
        specs = self._tools.specs()
        messages: list[Message] = [UserMessage(_first_message(question, claim_id))]
        seen_calls: dict[str, str] = {}
        searched: list[str] = []
        tool_calls_made = 0
        consecutive_errors = 0

        def finish_limit(reason: Reason, label: str) -> None:
            record.limit = label
            record.answer = FinalAnswer(
                Status.INSUFFICIENT_EVIDENCE,
                reason,
                searched=tuple(searched[:SEARCHED_MAX]) or (NO_TOOL_CALLS,),
            )

        for turn_no in range(1, limits.max_turns + 1):
            if self._clock() - t0 > limits.max_seconds:
                finish_limit(Reason.STEP_LIMIT, "time")
                break
            allow_tools = turn_no < limits.max_turns and tool_calls_made < limits.max_tool_calls

            estimate = Usage(
                estimate_tokens(
                    self._prompt.text
                    + "".join(_message_text(m) for m in messages)
                    + dumps(self._schema)
                )
                + sum(estimate_tokens(dumps(s.parameters) + s.description) for s in specs),
                limits.max_output_tokens,
            )
            if estimate.input_tokens > limits.max_prompt_tokens:
                finish_limit(Reason.BUDGET_LIMIT, "prompt_size")
                break
            if record.cost_usd + self._guard.cost(record.model_key, estimate) > limits.max_usd:
                finish_limit(Reason.BUDGET_LIMIT, "investigation_cost")
                break

            try:
                turn = self._guard.call(
                    functools.partial(
                        self._provider.complete,
                        system=self._prompt.text,
                        messages=list(messages),
                        tools=specs,
                        schema=self._schema,
                        max_output_tokens=limits.max_output_tokens,
                        allow_tools=allow_tools,
                    ),
                    usage_of=_usage_of,
                    phase=self._phase,
                    model_key=record.model_key,
                    purpose=f"{self._phase} agent turn {turn_no}",
                    estimated_usage=estimate,
                    eval_run_id=eval_run_id,
                )
            except (BudgetExceededError, ApprovalRequiredError):
                finish_limit(Reason.BUDGET_LIMIT, "guard_refused")
                break
            except ProviderError as exc:
                record.limit = "provider_error"
                record.answer = invalid(Reason.PROVIDER_ERROR, str(exc)[:200])
                break

            self._account(record, turn, turn_no)
            messages.append(AssistantMessage(turn))

            if not turn.tool_calls:
                record.answer = self._final(turn, registry, searched)
                break
            if not allow_tools:
                record.answer = invalid(
                    Reason.SCHEMA_VIOLATION, "the model called a tool when tools were disabled"
                )
                break

            outputs: list[ToolOutput] = []
            for call in turn.tool_calls:
                output = self._call_tool(
                    call, registry, seen_calls, record, searched, tool_calls_made, limits
                )
                if output[1]:
                    tool_calls_made += 1
                outputs.append(output[0])
            messages.append(ToolMessage(tuple(outputs)))
            consecutive_errors = consecutive_errors + 1 if all(o.is_error for o in outputs) else 0
            if consecutive_errors >= limits.max_consecutive_tool_errors:
                finish_limit(Reason.TOOL_ERROR, "tool_errors")
                break
        else:
            finish_limit(Reason.STEP_LIMIT, "turns")

        record.messages = _describe_messages(messages)
        record.evidence_ids = registry.ids()

    def _call_tool(
        self,
        call: ToolCall,
        registry: EvidenceRegistry,
        seen: dict[str, str],
        record: RunRecord,
        searched: list[str],
        calls_made: int,
        limits: Limits,
    ) -> tuple[ToolOutput, bool]:
        """Run or refuse one call. Returns the output and whether it used up a tool call."""
        key = call.name + dumps(call.arguments)
        entry: dict[str, Any] = {"name": call.name, "arguments": call.arguments}
        if key in seen:
            entry.update(evidence_id=seen[key], repeated=True, is_error=False)
            record.tool_log.append(entry)
            note = json.dumps({"note": "identical call already made", "evidence_id": seen[key]})
            return ToolOutput(call.call_id, call.name, note, False), False
        if calls_made >= limits.max_tool_calls:
            entry.update(evidence_id=None, repeated=False, is_error=True, refused="tool_limit")
            record.tool_log.append(entry)
            message = json.dumps({"error": "tool call limit reached; give your answer now"})
            return ToolOutput(call.call_id, call.name, message, True), False

        output = self._tools.execute(call, registry)
        evidence_id = None if output.is_error else registry.latest_id
        if evidence_id:
            seen[key] = evidence_id
        entry.update(evidence_id=evidence_id, repeated=False, is_error=output.is_error)
        record.tool_log.append(entry)
        searched.append(f"{call.name} {dumps(call.arguments)}"[:SEARCHED_ITEM_CHARS])
        return output, True

    def _account(self, record: RunRecord, turn: ModelTurn, turn_no: int) -> None:
        cost = self._guard.cost(record.model_key, turn.usage)
        record.model_calls += 1
        record.input_tokens += turn.usage.input_tokens
        record.output_tokens += turn.usage.output_tokens
        record.cost_usd += cost
        record.turns.append(
            {
                "turn": turn_no,
                "input_tokens": turn.usage.input_tokens,
                "output_tokens": turn.usage.output_tokens,
                "stop": turn.stop,
                "tool_calls": [c.name for c in turn.tool_calls],
                "cost_usd": str(cost),
            }
        )

    @staticmethod
    def _final(turn: ModelTurn, registry: EvidenceRegistry, searched: list[str]) -> FinalAnswer:
        if turn.stop == "length":
            return invalid(Reason.SCHEMA_VIOLATION, "the provider stopped at the output limit")
        if turn.stop == "refusal":
            return invalid(Reason.SCHEMA_VIOLATION, "the provider refused to answer")
        answer = validate_text(turn.text, registry)
        if not answer.shown_as_answer:
            return answer
        # What was searched is a fact the runtime recorded, not something the model reports.
        return replace(answer, searched=tuple(searched[:SEARCHED_MAX]) or (NO_TOOL_CALLS,))


def _first_message(question: str, claim_id: str | None) -> str:
    cleaned = question.replace("</investigator_question>", "")
    lines = [f"<investigator_question>\n{cleaned}\n</investigator_question>"]
    if claim_id:
        lines.append(f"Claim in scope: {claim_id}")
    return "\n".join(lines)
