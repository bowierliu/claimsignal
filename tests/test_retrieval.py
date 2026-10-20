from __future__ import annotations

import json
from pathlib import Path

import pytest

from claims_copilot.ingest.chunk import Chunk
from claims_copilot.project import CHUNKS_DIR, REPO_ROOT
from claims_copilot.retrieval.bm25 import BM25Index, Hit, tokenize
from claims_copilot.retrieval.evaluate import (
    KS,
    GoldItem,
    evaluate,
    format_metrics,
    load_chunks,
    load_gold,
    unmatched_gold,
)


def chunk(cid: str, source: str, text: str) -> Chunk:
    return Chunk(cid, source, 1, 1, "", text, "0" * 64)


CHUNKS = [
    chunk("a:1-1:0", "a", "Modifier 59 indicates a distinct procedural service."),
    chunk("a:2-2:1", "a", "Medically unlikely edits cap units of service per day."),
    chunk("b:1-1:0", "b", "The provider must refund overpayments within sixty days."),
]


def test_tokenize_drops_stopwords_and_lowercases() -> None:
    assert tokenize("What is the Modifier 59?") == ["modifier", "59"]


def test_bm25_ranks_matching_chunk_first() -> None:
    index = BM25Index([c.chunk_id for c in CHUNKS], [c.text for c in CHUNKS])
    hits = index.search("overpayments refund", k=3)
    assert hits[0].chunk_id == "b:1-1:0"
    assert len(hits) == 1  # only chunks sharing a term are returned


def test_bm25_unknown_terms_return_nothing() -> None:
    index = BM25Index([c.chunk_id for c in CHUNKS], [c.text for c in CHUNKS])
    assert index.search("zzzzqqq") == []


def test_bm25_rejects_mismatched_inputs() -> None:
    with pytest.raises(ValueError):
        BM25Index(["a"], ["x", "y"])


def test_bm25_rare_term_outranks_common_term() -> None:
    texts = ["billing billing billing", "billing", "billing unbundling"]
    index = BM25Index(["x", "y", "z"], texts)
    assert index.search("unbundling billing", k=3)[0].chunk_id == "z"


def gold(item_id: str, kind: str, q: str, source: str, evidence: str) -> GoldItem:
    return GoldItem(item_id, kind, q, source, evidence)


def test_evaluate_computes_recall_and_mrr() -> None:
    items = [
        gold("g1", "direct", "q1", "a", "distinct procedural service"),
        gold("g2", "paraphrase", "q2", "b", "refund overpayments within sixty days"),
    ]

    def search(q: str, k: int) -> list[Hit]:
        if q == "q1":  # correct chunk at rank 2
            return [Hit("a:2-2:1", 1.0), Hit("a:1-1:0", 0.9)]
        return [Hit("a:1-1:0", 1.0)]  # miss: wrong chunk and wrong source

    assert unmatched_gold(items, CHUNKS) == []
    assert unmatched_gold([gold("g3", "direct", "q", "b", "text not in corpus")], CHUNKS) == ["g3"]
    metrics = evaluate(items, CHUNKS, search)
    assert metrics["direct"].recall_at == {1: 0.0, 5: 1.0, 10: 1.0}
    assert metrics["direct"].mrr_at_10 == 0.5
    assert metrics["paraphrase"].recall_at == {k: 0.0 for k in KS}
    assert metrics["all"].n == 2
    assert "R@5=0.50" in format_metrics("t", metrics)


def test_evaluate_requires_matching_source() -> None:
    items = [gold("g1", "direct", "q", "b", "distinct procedural service")]  # quote is in source a
    metrics = evaluate(items, CHUNKS, lambda q, k: [Hit("a:1-1:0", 1.0)])
    assert metrics["all"].recall_at[10] == 0.0


def test_load_gold_rejects_duplicate_ids(tmp_path: Path) -> None:
    row = {"id": "g1", "kind": "direct", "question": "q", "source_id": "a", "evidence": "e"}
    path = tmp_path / "gold.jsonl"
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_gold(path)


def test_committed_gold_set_is_well_formed() -> None:
    items = load_gold(REPO_ROOT / "eval/phase0_retrieval_gold.jsonl")
    assert len(items) == 40
    assert {i.kind for i in items} == {"direct", "paraphrase"}
    assert all(i.evidence and i.question for i in items)


@pytest.mark.skipif(not (CHUNKS_DIR / "chunks.jsonl").exists(), reason="corpus not ingested")
def test_every_gold_quote_exists_in_the_chunked_corpus() -> None:
    chunks = load_chunks(CHUNKS_DIR / "chunks.jsonl")
    items = load_gold(REPO_ROOT / "eval/phase0_retrieval_gold.jsonl")
    assert unmatched_gold(items, chunks) == []


def test_phase6_gold_set_is_well_formed() -> None:
    items = load_gold(REPO_ROOT / "eval/phase6_retrieval_gold.jsonl")
    dev_ids = {i.id for i in load_gold(REPO_ROOT / "eval/phase0_retrieval_gold.jsonl")}
    assert len(items) == 16
    assert {i.kind for i in items} == {"paraphrase"}
    assert not dev_ids & {i.id for i in items}


@pytest.mark.skipif(not (CHUNKS_DIR / "chunks.jsonl").exists(), reason="corpus not ingested")
def test_every_phase6_gold_quote_exists_in_the_chunked_corpus() -> None:
    chunks = load_chunks(CHUNKS_DIR / "chunks.jsonl")
    items = load_gold(REPO_ROOT / "eval/phase6_retrieval_gold.jsonl")
    assert unmatched_gold(items, chunks) == []


def test_rrf_rewards_agreement_and_breaks_ties_by_id() -> None:
    from claims_copilot.retrieval.bm25 import Hit
    from claims_copilot.retrieval.fusion import rrf

    a = [Hit("x", 3.0), Hit("y", 2.0), Hit("z", 1.0)]
    b = [Hit("y", 0.9), Hit("w", 0.8), Hit("x", 0.7)]
    fused = [h.chunk_id for h in rrf([a, b])]
    assert fused[:2] == ["y", "x"]  # in both lists; y ranks 2 and 1, x ranks 1 and 3
    assert set(fused) == {"x", "y", "z", "w"}
    assert [h.chunk_id for h in rrf([[Hit("b", 1.0)], [Hit("a", 1.0)]])] == ["a", "b"]


def test_compare_counts_gained_lost_and_rank_moves() -> None:
    from claims_copilot.retrieval.fusion import compare

    base = {"q1": None, "q2": 3, "q3": 5, "q4": 2, "q5": None}
    cand = {"q1": 4, "q2": None, "q3": 1, "q4": 6, "q5": None}
    diff = compare(cand, base)
    assert diff.gained == ("q1",)
    assert diff.lost == ("q2",)
    assert (diff.improved_rank, diff.worsened_rank) == (1, 1)
    with pytest.raises(ValueError, match="different questions"):
        compare({"a": 1}, {"b": 1})
