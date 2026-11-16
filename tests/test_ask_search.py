"""Ask-path policy search (spec item 7): relevance gate, keep floor, reference text, fallback,
ledgering, and nothing written to disk. Fake embedder and a tiny dense index only."""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ask_fixtures import (
    MOD_CHUNK,
    OTHER_CHUNK,
    UNITS_CHUNK,
    FakeEmbedder,
    ask_chunks,
    ask_sources,
    dense_index,
    make_ask_guard,
)
from claims_copilot.agent.ask_search import AskPolicySearch
from claims_copilot.budget import CostGuard
from claims_copilot.retrieval.dense import MODEL_KEY as EMBED_KEY
from claims_copilot.retrieval.embed import EmbeddingBatch, EmbeddingError

E1 = (1.0, 0.0, 0.0, 0.0)
E4 = (0.0, 0.0, 0.0, 1.0)
CHUNK_VECTORS = {
    MOD_CHUNK: E1,  # cosine 1.00 with an on-topic question
    UNITS_CHUNK: (0.45, 0.893, 0.0, 0.0),  # about 0.45: above the keep floor, below the gate
    OTHER_CHUNK: (0.30, 0.0, 0.954, 0.0),  # about 0.30: below the keep floor
}
ON_TOPIC = "What does the manual say about modifier 59?"
OFF_TOPIC = "Tell me about helicopter fixture transport."
NEAR_TOPIC = "Something only loosely related."  # best cosine about 0.45 (below the 0.51 gate)
QUERY = "modifier 59"
ODD_QUERY = "zzz qqq"
TABLE = {
    ON_TOPIC: E1,
    OFF_TOPIC: E4,
    NEAR_TOPIC: (0.45, 0.0, 0.0, 0.893),
    QUERY: E1,
    ODD_QUERY: E4,
}


def make_search(
    tmp_path: Path, *, unavailable: str | None = None, embedder: Any = None
) -> tuple[AskPolicySearch, FakeEmbedder, CostGuard]:
    fake = FakeEmbedder(TABLE, default=(0.0, 1.0, 0.0, 0.0))
    guard = make_ask_guard(tmp_path)
    search = AskPolicySearch(
        ask_chunks(),
        ask_sources(),
        dense=dense_index(CHUNK_VECTORS),
        embedder=embedder or fake,
        reranker=None,
        guard=guard,
        unavailable=unavailable,
    )
    return search, fake, guard


def hit_ids(payload: dict[str, Any]) -> list[str]:
    return [h["chunk_id"] for h in payload["hits"]]


def test_below_the_gate_every_hit_is_withheld(tmp_path: Path) -> None:
    search, _, _ = make_search(tmp_path)
    payload, stats = search.search(QUERY, 5, references=[OFF_TOPIC], eval_run_id="ask-r1")
    assert payload["hits"] == []
    rel = payload["relevance"]
    assert rel["checked"] is True
    assert rel["offered"] == 3 and rel["withheld"] == 3
    assert rel.get("note")
    assert stats.relevance_checked and stats.withheld == 3


def test_a_best_hit_above_the_keep_floor_but_below_the_gate_still_withholds_all(
    tmp_path: Path,
) -> None:
    search, _, _ = make_search(tmp_path)
    payload, _ = search.search(QUERY, 5, references=[NEAR_TOPIC], eval_run_id="ask-r1")
    assert payload["hits"] == []
    assert payload["relevance"]["withheld"] == 3 and payload["relevance"].get("note")


def test_above_the_gate_hits_below_the_keep_floor_are_dropped(tmp_path: Path) -> None:
    search, _, _ = make_search(tmp_path)
    payload, stats = search.search(QUERY, 5, references=[ON_TOPIC], eval_run_id="ask-r1")
    assert set(hit_ids(payload)) == {MOD_CHUNK, UNITS_CHUNK}
    assert OTHER_CHUNK not in hit_ids(payload)
    rel = payload["relevance"]
    assert rel["checked"] is True and rel["offered"] == 3 and rel["withheld"] == 1
    assert "note" not in rel
    assert stats.mode in ("hybrid", "hybrid_rerank")
    for hit in payload["hits"]:
        assert hit["untrusted"] is True
        assert hit["source"]["source_id"] == "doc-a" and hit["source"]["sha256"]


def test_the_reference_is_the_investigators_text_not_the_models_query(tmp_path: Path) -> None:
    search, fake, _ = make_search(tmp_path)
    # An on-topic model query cannot widen an off-topic question...
    payload, _ = search.search(QUERY, 5, references=[OFF_TOPIC], eval_run_id="ask-r1")
    assert payload["hits"] == []
    # ...and an odd model query does not hide passages close to the investigator's question.
    payload, _ = search.search(ODD_QUERY, 5, references=[ON_TOPIC], eval_run_id="ask-r1")
    assert MOD_CHUNK in hit_ids(payload)
    embedded = [t for batch in fake.batches for t in batch]
    assert OFF_TOPIC in embedded and ON_TOPIC in embedded


def test_with_a_previous_question_either_investigator_text_can_qualify(tmp_path: Path) -> None:
    search, _, _ = make_search(tmp_path)
    payload, _ = search.search(QUERY, 5, references=[OFF_TOPIC, ON_TOPIC], eval_run_id="r")
    assert MOD_CHUNK in hit_ids(payload)


def test_unavailable_falls_back_to_lexical_and_says_relevance_was_not_checked(
    tmp_path: Path,
) -> None:
    search, fake, guard = make_search(tmp_path, unavailable="test: embeddings off")
    payload, stats = search.search(QUERY, 5, references=[OFF_TOPIC], eval_run_id="ask-r1")
    assert payload["mode"] == "lexical" and stats.mode == "lexical"
    assert payload["relevance"]["checked"] is False and not stats.relevance_checked
    assert MOD_CHUNK in hit_ids(payload)  # not filtered: shown, and labelled unchecked
    reason = str(payload["fallback_reason"]).lower()
    assert "not checked" in reason and "relevance" in reason
    assert fake.batches == [] and guard.ledger.entries() == []
    assert search.unavailable == "test: embeddings off"


def test_without_a_dense_index_the_search_is_lexical_and_unchecked() -> None:
    search = AskPolicySearch(
        ask_chunks(), ask_sources(), dense=None, embedder=None, reranker=None, guard=None
    )
    assert search.unavailable
    payload, stats = search.search(QUERY, 5, references=[ON_TOPIC], eval_run_id=None)
    assert stats.mode == "lexical" and payload["relevance"]["checked"] is False
    assert "not checked" in str(payload["fallback_reason"]).lower()


class BrokenEmbedder:
    model = "fake"

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        raise EmbeddingError("service down")


def test_an_embedding_failure_falls_back_to_lexical_unchecked(tmp_path: Path) -> None:
    search, _, _ = make_search(tmp_path, embedder=BrokenEmbedder())
    payload, stats = search.search(QUERY, 5, references=[ON_TOPIC], eval_run_id="ask-r1")
    assert stats.mode == "lexical" and payload["relevance"]["checked"] is False
    assert "not checked" in str(payload["fallback_reason"]).lower()


def test_embedding_spend_is_ledgered_under_the_given_eval_run_id(tmp_path: Path) -> None:
    search, _, guard = make_search(tmp_path)
    search.search(QUERY, 5, references=[ON_TOPIC], eval_run_id="ask-run-label")
    entries = guard.ledger.entries()
    assert entries, "embedding calls must be ledgered"
    assert {e.eval_run_id for e in entries} == {"ask-run-label"}
    assert {e.model_key for e in entries} == {EMBED_KEY}
    assert guard.ledger.spent(eval_run_id="ask-run-label") > 0


def test_nothing_derived_from_the_question_is_written_to_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    search, _, guard = make_search(tmp_path)
    writes: list[str] = []
    real_path_open = Path.open
    real_open = builtins.open

    def path_open(self: Path, mode: str = "r", *a: Any, **kw: Any) -> Any:
        if any(c in mode for c in "wax+"):
            writes.append(str(self))
        return real_path_open(self, mode, *a, **kw)

    def any_open(file: Any, mode: str = "r", *a: Any, **kw: Any) -> Any:
        if any(c in mode for c in "wax+"):
            writes.append(str(file))
        return real_open(file, mode, *a, **kw)

    def no_save(*_a: Any, **_kw: Any) -> None:
        raise AssertionError("numpy save called during a search")

    monkeypatch.setattr(Path, "open", path_open)
    monkeypatch.setattr(builtins, "open", any_open)
    monkeypatch.setattr(np, "save", no_save)
    monkeypatch.setattr(np, "savez", no_save)
    before = {p for p in tmp_path.rglob("*")}
    search.search(QUERY, 5, references=[ON_TOPIC], eval_run_id="ask-r1")
    search.search(ODD_QUERY, 5, references=[OFF_TOPIC], eval_run_id="ask-r1")
    assert set(writes) <= {str(guard.ledger.path)}
    assert {p for p in tmp_path.rglob("*")} - before <= {guard.ledger.path}
    for path in tmp_path.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert ON_TOPIC not in text and OFF_TOPIC not in text
