"""Reciprocal rank fusion (RRF) and paired comparison of retrieval variants.

Settings are fixed in docs/PHASE6_PLAN.md before any run and are not tuned on the gold questions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from claims_copilot.ingest.chunk import Chunk
from claims_copilot.retrieval.bm25 import Hit
from claims_copilot.retrieval.evaluate import GoldItem, is_hit

RRF_K = 60
CANDIDATE_DEPTH = 20
TOP_K = 10

Search = Callable[[str, int], list[Hit]]


def rrf(rankings: list[list[Hit]], k: int = RRF_K) -> list[Hit]:
    """Fuse ranked lists: score(d) = sum over lists of 1 / (k + rank). Ties break by chunk id."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [Hit(cid, s) for cid, s in ordered]


def hybrid(lexical: Search, dense: Search, depth: int = CANDIDATE_DEPTH) -> Search:
    """RRF of a lexical and a dense search, each taken to `depth` candidates."""

    def search(query: str, k: int) -> list[Hit]:
        return rrf([lexical(query, depth), dense(query, depth)])[:k]

    return search


def first_hit_rank(
    gold: list[GoldItem], chunks: list[Chunk], search: Search, k: int = TOP_K
) -> dict[str, int | None]:
    """Rank (1-based) of the first gold-matching chunk in the top k, per gold id; None = miss."""
    by_id = {c.chunk_id: c for c in chunks}
    out: dict[str, int | None] = {}
    for item in gold:
        hits = search(item.question, k)
        out[item.id] = next(
            (i for i, h in enumerate(hits, start=1) if is_hit(item, by_id[h.chunk_id])), None
        )
    return out


@dataclass(frozen=True)
class PairedDiff:
    """Questions found (within top 10) by one variant but not the other, and rank movement."""

    gained: tuple[str, ...]
    lost: tuple[str, ...]
    improved_rank: int
    worsened_rank: int


def compare(
    candidate: dict[str, int | None], baseline: dict[str, int | None], *, at: int = TOP_K
) -> PairedDiff:
    if candidate.keys() != baseline.keys():
        raise ValueError("variants were run on different questions")
    gained, lost = [], []
    better = worse = 0
    for qid in sorted(candidate):
        c, b = candidate[qid], baseline[qid]
        c_in = c is not None and c <= at
        b_in = b is not None and b <= at
        if c_in and not b_in:
            gained.append(qid)
        elif b_in and not c_in:
            lost.append(qid)
        elif c_in and b_in and c is not None and b is not None:
            better += c < b
            worse += c > b
    return PairedDiff(tuple(gained), tuple(lost), better, worse)
