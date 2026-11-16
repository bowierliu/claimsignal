"""Shared helpers for the Ask tests: fake embedder, Ask-path search, Ask service, API wiring.

No network, no spend: the provider is `FakeProvider`, embeddings come from `FakeEmbedder`, and the
ledger is a temp file. Synthetic text and fake ids only.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI

from agent_fixtures import MODEL_KEY, PROMPT, FakeProvider, answer_json, text_turn, tool_turn
from api_fixtures import build_db, policy_index
from claims_copilot.agent.ask import AskService, AskToolRunner
from claims_copilot.agent.ask_search import AskPolicySearch
from claims_copilot.agent.loop import Limits
from claims_copilot.agent.session import SessionStore
from claims_copilot.agent.tools import in_process_client
from claims_copilot.agent.types import ModelTurn, ToolMessage
from claims_copilot.api.app import create_app
from claims_copilot.api.guard import Guard, GuardConfig
from claims_copilot.api.policy import SourceRef
from claims_copilot.api.workbench import AskBackend
from claims_copilot.budget import Caps, CostGuard, Ledger, ModelPrice
from claims_copilot.ingest.chunk import Chunk
from claims_copilot.retrieval.dense import MODEL_KEY as EMBED_KEY
from claims_copilot.retrieval.dense import DenseIndex
from claims_copilot.retrieval.embed import EmbeddingBatch
from tool_fixtures import icd_fixture

ASK_SOURCE = SourceRef(
    source_id="doc-a",
    title="Fixture manual",
    url="https://example.invalid/doc-a.pdf",
    retrieved_at="2026-10-16T00:00:00+00:00",
    sha256="a" * 64,
)
MOD_CHUNK = "doc-a:3-4:0000"
UNITS_CHUNK = "doc-a:5-6:0001"
OTHER_CHUNK = "doc-a:7-7:0002"
MOD_TEXT = "Modifier 59 marks a distinct procedural service on the same day."
UNITS_TEXT = "Units of service are counted per line for each fixture code."
OTHER_TEXT = "Place of service codes describe where a fixture service happened."
DOSSIER = ("claim_dossier", {"claim_id": "C0000001"})
UNIT_FINDING = "E1.r2.f1"  # check_unit_limits finding inside the C0000001 dossier


def ask_chunks(*extra: Chunk) -> list[Chunk]:
    return [
        Chunk(MOD_CHUNK, "doc-a", 3, 4, "Section 1", MOD_TEXT, "b" * 64),
        Chunk(UNITS_CHUNK, "doc-a", 5, 6, "Section 2", UNITS_TEXT, "c" * 64),
        Chunk(OTHER_CHUNK, "doc-a", 7, 7, "Section 3", OTHER_TEXT, "d" * 64),
        *extra,
    ]


def ask_sources() -> dict[str, SourceRef]:
    return {"doc-a": ASK_SOURCE}


def make_ask_guard(tmp_path: Path) -> CostGuard:
    """Temp-ledger guard that prices the fake chat model and the embedding model."""
    caps = Caps(
        total_usd=Decimal("50"),
        eval_run_usd=Decimal("5"),
        warn_fraction=Decimal("0.7"),
        stop_fraction=Decimal("0.9"),
        phases={"p5": Decimal("8")},
        approved_past_stop=frozenset(),
    )
    prices = {
        MODEL_KEY: ModelPrice(MODEL_KEY, Decimal("0.10"), Decimal("0.50"), "test"),
        EMBED_KEY: ModelPrice(EMBED_KEY, Decimal("0.02"), Decimal("0"), "test"),
    }
    return CostGuard(
        caps,
        prices,
        Ledger(tmp_path / "ledger.jsonl"),
        warn=lambda _m: None,
        clock=lambda: "2026-01-01T00:00:00+00:00",
    )


class FakeEmbedder:
    """Looks each text up in a fixed table (default vector otherwise) and records every batch."""

    model = "fake"

    def __init__(self, table: Mapping[str, Sequence[float]], default: Sequence[float]) -> None:
        self._table = dict(table)
        self._default = list(default)
        self.batches: list[list[str]] = []

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        self.batches.append(list(texts))
        vectors = [list(self._table.get(t, self._default)) for t in texts]
        # Large fake usage so the cost shows at the ledger's $0.000001 precision.
        return EmbeddingBatch(vectors, prompt_tokens=50_000 * len(texts))


def unit(*xs: float) -> list[float]:
    v = np.asarray(xs, dtype=np.float64)
    return [float(x) for x in v / np.linalg.norm(v)]


def dense_index(vectors: Mapping[str, Sequence[float]]) -> DenseIndex:
    ids = list(vectors)
    matrix = np.asarray([unit(*vectors[i]) for i in ids], dtype=np.float32)
    return DenseIndex(ids, ["0" * 64] * len(ids), matrix, "fake")


def lexical_search(*extra: Chunk) -> AskPolicySearch:
    """The Ask search as it runs without an embedding service: BM25, relevance not checked."""
    return AskPolicySearch(
        ask_chunks(*extra),
        ask_sources(),
        dense=None,
        embedder=None,
        reranker=None,
        guard=None,
        unavailable="test: no embedding service",
    )


def make_tools(tmp_path: Path, search: AskPolicySearch) -> AskToolRunner:
    app_dir = tmp_path / "tools-app"
    app_dir.mkdir(parents=True, exist_ok=True)
    app = create_app(
        build_db(app_dir / "payer.sqlite"),
        icd_loader=lambda: icd_fixture("E119"),
        policy_loader=lambda: None,
    )
    return AskToolRunner(in_process_client(app), search)


def make_service(
    tmp_path: Path,
    provider: FakeProvider,
    *,
    search: AskPolicySearch | None = None,
    guard: CostGuard | None = None,
    store: SessionStore | None = None,
    limits: Limits | None = None,
    record_dir: Path | None = None,
    session_ceiling: Decimal | None = None,
    server_ceiling: Decimal | None = None,
) -> AskService:
    kw: dict[str, Any] = {}
    if session_ceiling is not None:
        kw["session_ceiling"] = session_ceiling
    if server_ceiling is not None:
        kw["server_ceiling"] = server_ceiling
    return AskService(
        provider=provider,
        tools=make_tools(tmp_path, search or lexical_search()),
        guard=guard or make_ask_guard(tmp_path),
        prompt=PROMPT,
        store=store if store is not None else SessionStore(),
        limits=limits,
        record_dir=record_dir,
        **kw,
    )


def first_message(request: Mapping[str, Any]) -> str:
    return str(request["messages"][0].text)


def has_tool_output(request: Mapping[str, Any]) -> bool:
    return any(isinstance(m, ToolMessage) for m in request["messages"])


def tools_then_answer(
    provider_ref: list[FakeProvider],
    calls: Sequence[tuple[str, dict[str, Any]]],
    answer: str | Callable[[str], str],
) -> Callable[[int], ModelTurn]:
    """A script for a multi-turn session: each investigation first makes `calls` (if any), then
    answers. `answer` may depend on the investigation's first user message."""

    def script(n: int) -> ModelTurn:
        request = provider_ref[0].requests[n]
        if calls and not has_tool_output(request):
            return tool_turn(*calls)
        text = answer(first_message(request)) if callable(answer) else answer
        return text_turn(text)

    return script


def scripted(
    calls: Sequence[tuple[str, dict[str, Any]]], answer: str | Callable[[str], str]
) -> FakeProvider:
    ref: list[FakeProvider] = []
    provider = FakeProvider(tools_then_answer(ref, calls, answer))
    ref.append(provider)
    return provider


Plan = tuple[Sequence[tuple[str, dict[str, Any]]], str]


def question_of(first: str) -> str:
    return first.split("<investigator_question>\n", 1)[1].split("\n</investigator_question>", 1)[0]


def planned(plans: Mapping[str, Plan]) -> FakeProvider:
    """Each investigation looks up its plan (tool calls, then the final answer text) by the
    investigator's question, so one provider can script a whole session."""
    ref: list[FakeProvider] = []

    def script(n: int) -> ModelTurn:
        request = ref[0].requests[n]
        calls, answer = plans[question_of(first_message(request))]
        if calls and not has_tool_output(request):
            return tool_turn(*calls)
        return text_turn(answer)

    provider = FakeProvider(script)
    ref.append(provider)
    return provider


def answered(text: str, citations: Sequence[str], **kw: Any) -> str:
    return answer_json(summary=[{"text": text, "citations": list(citations)}], **kw)


def insufficient(**kw: Any) -> str:
    return answer_json(
        status="INSUFFICIENT_EVIDENCE",
        reason="NO_RELEVANT_SOURCE",
        summary=[],
        policy_quotes=[],
        **kw,
    )


TEST_KEY = "test-ask-key-not-real"  # dummy value, never a real credential


def make_api(
    tmp_path: Path,
    ask: AskBackend | None,
    *,
    key: str | None = TEST_KEY,
) -> FastAPI:
    app_dir = tmp_path / "api-app"
    app_dir.mkdir(parents=True, exist_ok=True)
    guard = Guard(GuardConfig.from_keys(key)) if key else None
    return create_app(
        build_db(app_dir / "payer.sqlite"),
        icd_loader=lambda: icd_fixture("E119"),
        policy_loader=policy_index,
        guard=guard,
        ask=ask,
    )


class FakeBusyError(Exception):
    pass


class FakeBackend:
    """An AskBackend that records calls and returns a fixed view."""

    busy_error: type[Exception] = FakeBusyError

    def __init__(self, *, busy: bool = False) -> None:
        self.asks: list[tuple[str | None, str, str | None]] = []
        self.resets: list[str | None] = []
        self._busy = busy
        self._tokens = itertools.count(1)

    def status(self) -> dict[str, Any]:
        return {"enabled": True, "policy_search": True, "policy_search_note": None}

    def reset(self, token: str | None) -> bool:
        self.resets.append(token)
        return True

    def ask(self, token: str | None, question: str, claim_id: str | None) -> dict[str, Any]:
        if self._busy:
            raise self.busy_error("busy")
        self.asks.append((token, question, claim_id))
        return {"status": "OUT_OF_SCOPE", "session": {"token": f"t{next(self._tokens)}"}}


def ledger_text(guard: CostGuard) -> str:
    path = guard.ledger.path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def view_text(view: Mapping[str, Any]) -> str:
    return json.dumps(view, ensure_ascii=False)
