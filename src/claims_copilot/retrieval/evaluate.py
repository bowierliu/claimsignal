"""Retrieval evaluation against the gold set.

A gold item names the source document and a verbatim evidence quote. A retrieved chunk is a hit
only if it comes from that source AND its text contains the quote (whitespace/quote-normalised).
Defining gold by quote rather than chunk id keeps the metric valid when chunking changes.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from claims_copilot.ingest.chunk import Chunk
from claims_copilot.retrieval.bm25 import Hit
from claims_copilot.sources.verify import normalize

KS = (1, 5, 10)


@dataclass(frozen=True)
class GoldItem:
    id: str
    kind: str
    question: str
    source_id: str
    evidence: str


@dataclass(frozen=True)
class Metrics:
    n: int
    recall_at: dict[int, float]
    mrr_at_10: float


def load_gold(path: Path) -> list[GoldItem]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            items.append(GoldItem(d["id"], d["kind"], d["question"], d["source_id"], d["evidence"]))
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate gold ids")
    return items


def load_chunks(path: Path) -> list[Chunk]:
    return [
        Chunk(**json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def unmatched_gold(gold: list[GoldItem], chunks: list[Chunk]) -> list[str]:
    """Gold ids whose evidence quote is in no chunk of the named source (data-quality check)."""
    unmatched = []
    for item in gold:
        needle = normalize(item.evidence)
        if not any(c.source_id == item.source_id and needle in normalize(c.text) for c in chunks):
            unmatched.append(item.id)
    return unmatched


def is_hit(item: GoldItem, chunk: Chunk) -> bool:
    return chunk.source_id == item.source_id and normalize(item.evidence) in normalize(chunk.text)


def evaluate(
    gold: list[GoldItem],
    chunks: list[Chunk],
    search: Callable[[str, int], list[Hit]],
) -> dict[str, Metrics]:
    by_id = {c.chunk_id: c for c in chunks}
    ranks: dict[str, list[int | None]] = {}
    for item in gold:
        hits = search(item.question, max(KS))
        rank = next(
            (i for i, h in enumerate(hits, start=1) if is_hit(item, by_id[h.chunk_id])), None
        )
        for group in ("all", item.kind):
            ranks.setdefault(group, []).append(rank)
    return {group: _metrics(rs) for group, rs in ranks.items()}


def _metrics(ranks: list[int | None]) -> Metrics:
    n = len(ranks)
    recall = {k: sum(1 for r in ranks if r is not None and r <= k) / n for k in KS}
    mrr = sum(1 / r for r in ranks if r is not None and r <= 10) / n
    return Metrics(n=n, recall_at=recall, mrr_at_10=mrr)


def format_metrics(name: str, metrics: dict[str, Metrics]) -> str:
    lines = [f"== {name}"]
    for group in sorted(metrics, key=lambda g: (g != "all", g)):
        m = metrics[group]
        recalls = "  ".join(f"R@{k}={m.recall_at[k]:.2f}" for k in KS)
        lines.append(f"{group:<11} n={m.n:<3} {recalls}  MRR@10={m.mrr_at_10:.3f}")
    return "\n".join(lines)
