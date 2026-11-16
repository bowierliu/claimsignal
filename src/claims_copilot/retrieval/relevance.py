"""Minimum-relevance rule for policy hits shown to the agent on the Ask path.

A hit is kept only if its chunk is close enough to the investigator's own question: the cosine of
the two `text-embedding-3-small` vectors (both unit length) must reach a fixed threshold. The
reference is the investigator's text, never the query the model chose to type, so a model cannot
widen what counts as on topic. Withheld hits never reach the agent, so they can never be cited;
when every hit is withheld the agent sees an empty search, which is the "nothing relevant" signal
that feeds `INSUFFICIENT_EVIDENCE`. Plain arithmetic, no model call.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from claims_copilot.retrieval.bm25 import Hit

Vector = npt.NDArray[np.float32]


@dataclass(frozen=True)
class Filtered:
    kept: list[Hit]
    withheld: int
    best_cosine: float | None  # highest cosine among the hits offered; None when none offered


def cosine(a: Vector, b: Vector) -> float:
    """Dot product of two unit vectors, written element-wise (no BLAS call)."""
    return float(np.sum(a * b, dtype=np.float64))


def filter_hits(
    hits: Sequence[Hit],
    vector_of: dict[str, Vector],
    references: Sequence[Vector],
    threshold: float,
    *,
    keep_threshold: float | None = None,
) -> Filtered:
    """Withhold every hit unless the best one reaches `threshold`; then keep each hit that
    reaches `keep_threshold` (default: `threshold` itself, a plain per-hit cut).

    `references` are embeddings of investigator-written text only (the question, and on a
    follow-up the previous question too). A hit whose chunk has no vector is withheld.
    """
    floor = threshold if keep_threshold is None else min(keep_threshold, threshold)
    scored: list[tuple[Hit, float]] = []
    for h in hits:
        vec = vector_of.get(h.chunk_id)
        if vec is not None and references:
            scored.append((h, max(cosine(vec, r) for r in references)))
    best = max((s for _, s in scored), default=None)
    if best is None or best < threshold:
        return Filtered([], len(hits), best)
    kept = [h for h, s in scored if s >= floor]
    return Filtered(kept, len(hits) - len(kept), best)
