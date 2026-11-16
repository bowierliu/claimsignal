"""Builds the Ask service for the server (`python -m claims_copilot.api --ask`).

Provider keys are read here, server-side, from the environment or `.env`; they never reach the
browser. The agent's tools run against a second, in-process copy of the read-only API (no network,
no guard: it is not reachable from outside), and its policy searches use the Ask-path search.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from claims_copilot.agent.ask import AskService, AskToolRunner
from claims_copilot.agent.ask_search import PHASE, AskPolicySearch
from claims_copilot.agent.prompt import load_prompt
from claims_copilot.agent.providers import AnthropicProvider, OpenAIProvider
from claims_copilot.agent.session import SessionStore
from claims_copilot.agent.tools import in_process_client
from claims_copilot.agent.types import Provider
from claims_copilot.api.policy import CHUNKS_PATH, source_refs
from claims_copilot.budget import CostGuard, default_guard
from claims_copilot.obs.audit import AuditLog
from claims_copilot.project import CACHE_DIR, INDEX_DIR, RUNS_DIR
from claims_copilot.retrieval.dense import MODEL, DenseIndex
from claims_copilot.retrieval.embed import OpenAIEmbedder
from claims_copilot.retrieval.evaluate import load_chunks
from claims_copilot.retrieval.pipeline import LLM_MODEL
from claims_copilot.retrieval.rerank import PROMPT_VERSION, Reranker
from claims_copilot.secrets import get_secret

OPENAI_MODEL = "gpt-6-luna"
ANTHROPIC_MODEL = "claude-haiku-5-5"
# Ask's prompt; Phase 7's sealed runs keep agent_v1 (prompt.DEFAULT_PROMPT).
ASK_PROMPT = "agent_v2"
ProviderName = Literal["anthropic", "openai"]


class AskUnavailableError(RuntimeError):
    """Ask cannot start. The message is a fixed reason, never a key or a response."""


def make_provider(name: ProviderName) -> Provider:
    if name == "anthropic":
        key = get_secret("ANTHROPIC_API_KEY")
        if not key:
            raise AskUnavailableError("ANTHROPIC_API_KEY is not set")
        return AnthropicProvider(key, ANTHROPIC_MODEL)
    key = get_secret("OPENAI_API_KEY")
    if not key:
        raise AskUnavailableError("OPENAI_API_KEY is not set")
    return OpenAIProvider(key, OPENAI_MODEL)


def build_search(guard: CostGuard, chunks_path: Path = CHUNKS_PATH) -> AskPolicySearch:
    """The adopted Ask-path search, or a lexical-only one that says why (never raises for keys)."""
    if not chunks_path.is_file():
        raise AskUnavailableError("the policy corpus has not been ingested")
    chunks = load_chunks(chunks_path)
    sources = source_refs()
    key = get_secret("OPENAI_API_KEY")
    dense = DenseIndex.load(INDEX_DIR / f"dense_{MODEL}.npz")
    reason = None
    if dense is None:
        reason = "dense index is not built"
    elif set(dense.ids) != {c.chunk_id for c in chunks}:
        reason = "dense index does not match the chunk file"
    if not key or reason:
        return AskPolicySearch(
            chunks,
            sources,
            dense=None,
            embedder=None,
            reranker=None,
            guard=None,
            unavailable=reason or "OPENAI_API_KEY is not set",
        )
    reranker = Reranker(
        lambda _q, _k: [],  # unused: the Ask search hands the reranker its own candidates
        chunks,
        OpenAIProvider(key, LLM_MODEL),
        guard,
        load_prompt(PROMPT_VERSION),
        CACHE_DIR / f"rerank_{PROMPT_VERSION}_{LLM_MODEL}.jsonl",
        phase=PHASE,
    )
    return AskPolicySearch(
        chunks,
        sources,
        dense=dense,
        embedder=OpenAIEmbedder(key, model=MODEL),
        reranker=reranker,
        guard=guard,
    )


def build_ask_service(
    payer_path: Path,
    *,
    provider: ProviderName = "anthropic",
    record_runs: bool = False,
    audit: AuditLog | None = None,
    record_dir: Path | None = None,
    label_prefix: str = "ask-",
    prompt_version: str = ASK_PROMPT,
) -> AskService:
    # Imported here: the API package must not import the agent at module load.
    from claims_copilot.api.app import create_app

    guard = default_guard()
    search = build_search(guard)
    tools = AskToolRunner(
        in_process_client(create_app(payer_path, policy_loader=lambda: None)), search
    )
    return AskService(
        provider=make_provider(provider),
        tools=tools,
        guard=guard,
        prompt=load_prompt(prompt_version),
        store=SessionStore(label_prefix=label_prefix),
        audit=audit,
        record_dir=record_dir or (RUNS_DIR / "ask" if record_runs else None),
    )
