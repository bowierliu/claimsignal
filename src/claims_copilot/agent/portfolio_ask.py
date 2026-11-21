"""Connect the original workbench Ask loop to durable local portfolio accounting."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from contextvars import ContextVar
from decimal import Decimal
from pathlib import Path
from typing import Any

from claims_copilot.agent.ask import AskService, AskToolRunner
from claims_copilot.agent.ask_search import AskPolicySearch
from claims_copilot.agent.evidence import EvidenceRegistry, dumps
from claims_copilot.agent.loop import describe_messages
from claims_copilot.agent.prompt import load_prompt
from claims_copilot.agent.tools import in_process_client
from claims_copilot.agent.types import (
    Message,
    ModelTurn,
    ProviderError,
    ToolCall,
    ToolOutput,
    ToolSpec,
)
from claims_copilot.api.app import create_app
from claims_copilot.api.policy import CHUNKS_PATH, source_refs
from claims_copilot.budget import CostGuard, Ledger, ModelPrice, Usage, load_caps
from claims_copilot.obs.redact import scan
from claims_copilot.portfolio_guard import (
    INPUT_RATE,
    MODEL,
    OUTPUT_RATE,
    Guard,
    GuardError,
    Investigation,
)
from claims_copilot.project import BUDGET_DIR, PROMPTS_DIR
from claims_copilot.retrieval.evaluate import load_chunks

# A model or tool cannot operate outside the request that reserved its allowance.
ACTIVE: ContextVar[Investigation] = ContextVar("portfolio_investigation")


class PortfolioProvider:
    name = "openai"
    model_key = "openai/" + MODEL

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
        run = ACTIVE.get()
        # The evaluated system prompt already specifies the complete final answer schema.
        menu = {t.name: t.parameters for t in tools} if allow_tools else {}
        wire = {"tools": menu, "messages": describe_messages(list(messages))}
        protocol = (PROMPTS_DIR / "portfolio_ask_wire_v1.md").read_text()
        raw = run.model(system + "\n" + protocol, dumps(wire))
        # Carry verified token counts to the workbench's existing per-session cost view.
        # The durable SQLite ledger owns the actual reservations and lifetime limits.
        with closing(
            sqlite3.connect(f"{run.guard.path.resolve().as_uri()}?mode=ro", uri=True)
        ) as db:
            counts = db.execute(
                "SELECT input_tokens,output_tokens FROM calls WHERE run_id=? "
                "ORDER BY rowid DESC LIMIT 1",
                (run.run_id,),
            ).fetchone()
        if not counts or not all(type(n) is int for n in counts):
            raise GuardError("Verified token usage is unavailable.")
        usage = Usage(*counts)
        try:
            reply = json.loads(raw)
        except (ValueError, RecursionError):
            return ModelTurn(
                raw, (), "end", usage
            )  # Original final-answer validator will withhold.
        if not isinstance(reply, dict) or "tool" not in reply:
            return ModelTurn(raw, (), "end", usage)
        if (
            set(reply) != {"tool", "arguments"}
            or not isinstance(reply["tool"], str)
            or reply["tool"] not in menu
            or not isinstance(reply["arguments"], dict)
        ):
            raise ProviderError("The model returned an invalid tool selection.")
        call = ToolCall(f"call-{len(messages)}", reply["tool"], reply["arguments"])
        return ModelTurn("", (call,), "tool_calls", usage)


class PortfolioAskTools(AskToolRunner):
    def execute(self, call: ToolCall, registry: EvidenceRegistry) -> ToolOutput:
        return ACTIVE.get().tool(super().execute, call, registry)


class PortfolioAsk(AskService):
    def ask(self, token: str | None, question: str, claim_id: str | None) -> dict[str, Any]:
        if scan(question):
            raise GuardError(
                "Use a synthetic question without personal information or credentials."
            )
        with Guard.from_env().investigation("local-owner") as run:
            context = ACTIVE.set(run)
            try:
                return super().ask(token, question, claim_id)
            finally:
                ACTIVE.reset(context)


def build_portfolio_ask(payer: Path, scratch: Path) -> PortfolioAsk:
    chunks = load_chunks(CHUNKS_PATH) if CHUNKS_PATH.is_file() else []
    search = AskPolicySearch(
        chunks,
        source_refs(),
        dense=None,
        embedder=None,
        reranker=None,
        guard=None,
        unavailable="local lexical search" if chunks else "no local policy corpus",
    )
    tools = PortfolioAskTools(
        in_process_client(create_app(payer, policy_loader=lambda: None)), search
    )
    provider = PortfolioProvider()
    price = ModelPrice(
        provider.model_key,
        Decimal(INPUT_RATE) / 1000,
        Decimal(OUTPUT_RATE) / 1000,
        "docs/LIVE_BUDGET.md",
    )
    # Preserve original session/turn display and extra ceilings on top of the durable guard.
    # These temporary rows contain only usage metadata; the shared guard survives process exit.
    session_guard = CostGuard(
        load_caps(BUDGET_DIR / "caps.toml"),
        {provider.model_key: price},
        Ledger(scratch / "session.jsonl"),
    )
    return PortfolioAsk(
        provider=provider, tools=tools, guard=session_guard, prompt=load_prompt("agent_v2")
    )
