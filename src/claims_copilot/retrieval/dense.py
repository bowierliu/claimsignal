"""Dense retrieval baseline: OpenAI text-embedding-3-small + cosine similarity.

All paid calls go through CostGuard. The index is cached in data/index/ (gitignored) keyed by chunk
sha256, so a re-run only embeds new or changed chunks.

Run: `uv run python -m claims_copilot.retrieval.dense`            (cost estimate only, no spend)
     `uv run python -m claims_copilot.retrieval.dense --confirm`  (builds index, evaluates)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Protocol

import numpy as np
import numpy.typing as npt

from claims_copilot.budget import CostGuard, Usage, default_guard, estimate_tokens
from claims_copilot.ingest.chunk import Chunk
from claims_copilot.project import CHUNKS_DIR, INDEX_DIR, REPO_ROOT
from claims_copilot.retrieval.bm25 import BM25Index, Hit
from claims_copilot.retrieval.embed import EmbeddingBatch, OpenAIEmbedder
from claims_copilot.retrieval.evaluate import (
    evaluate,
    format_metrics,
    load_chunks,
    load_gold,
)
from claims_copilot.secrets import get_secret

MODEL = "text-embedding-3-small"
MODEL_KEY = f"openai/{MODEL}"
PHASE = "p0"
BATCH_SIZE = 96
EVAL_RUN_ID = "p0-baseline"

Vectors = npt.NDArray[np.float32]


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str]) -> EmbeddingBatch: ...


class GuardedEmbedder:
    """Embeds text in batches, pricing and ledgering every request through CostGuard."""

    def __init__(
        self,
        embedder: Embedder,
        guard: CostGuard,
        *,
        eval_run_id: str | None = None,
        phase: str = PHASE,
    ):
        self._embedder = embedder
        self._guard = guard
        self._eval_run_id = eval_run_id
        self._phase = phase

    def embed(self, texts: list[str], purpose: str) -> Vectors:
        out: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            estimate = Usage(sum(estimate_tokens(t) for t in batch), 0)
            result = self._guard.call(
                lambda b=batch: self._embedder.embed(b),  # type: ignore[misc]
                usage_of=lambda r: Usage(r.prompt_tokens, 0),
                phase=self._phase,
                model_key=MODEL_KEY,
                purpose=purpose,
                estimated_usage=estimate,
                eval_run_id=self._eval_run_id,
            )
            out.extend(result.vectors)
        return normalize_rows(np.asarray(out, dtype=np.float32))


def normalize_rows(m: Vectors) -> Vectors:
    if m.size == 0:
        return m
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return (m / np.where(norms == 0, 1, norms)).astype(np.float32)


class DenseIndex:
    def __init__(self, ids: list[str], hashes: list[str], vectors: Vectors, model: str) -> None:
        self.ids, self.hashes, self.vectors, self.model = ids, hashes, vectors, model

    @classmethod
    def load(cls, path: Path) -> DenseIndex | None:
        if not path.exists():
            return None
        with np.load(path, allow_pickle=False) as z:
            return cls(
                [str(x) for x in z["ids"]],
                [str(x) for x in z["hashes"]],
                z["vectors"].astype(np.float32),
                str(z["model"]),
            )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            path,
            ids=np.array(self.ids),
            hashes=np.array(self.hashes),
            vectors=self.vectors,
            model=np.array(self.model),
        )

    def search_vector(self, query: Vectors, k: int) -> list[Hit]:
        scores = self.vectors @ query
        top = np.argsort(-scores, kind="stable")[:k]
        return [Hit(self.ids[int(i)], float(scores[int(i)])) for i in top]


def pending_chunks(chunks: list[Chunk], existing: DenseIndex | None) -> list[Chunk]:
    have = dict(zip(existing.ids, existing.hashes, strict=True)) if existing else {}
    return [c for c in chunks if have.get(c.chunk_id) != c.sha256]


def build_index(
    chunks: list[Chunk], existing: DenseIndex | None, embedder: GuardedEmbedder
) -> DenseIndex:
    todo = pending_chunks(chunks, existing)
    new = embedder.embed([c.text for c in todo], purpose="p0 baseline: embed corpus chunks")
    keep = {c.chunk_id for c in chunks} - {c.chunk_id for c in todo}
    rows: dict[str, tuple[str, npt.NDArray[np.float32]]] = {}
    if existing:
        for i, cid in enumerate(existing.ids):
            if cid in keep:
                rows[cid] = (existing.hashes[i], existing.vectors[i])
    for c, vec in zip(todo, new, strict=True):
        rows[c.chunk_id] = (c.sha256, vec)
    ids = [c.chunk_id for c in chunks]
    vectors = np.stack([rows[i][1] for i in ids]).astype(np.float32)
    return DenseIndex(ids, [rows[i][0] for i in ids], vectors, MODEL)


class DenseSearcher:
    """search(question, k) with an on-disk query-embedding cache (queries cost money too)."""

    def __init__(
        self,
        index: DenseIndex,
        embedder: GuardedEmbedder,
        cache_path: Path,
        label: str = "p0 baseline",
    ) -> None:
        self._index, self._embedder, self._cache_path = index, embedder, cache_path
        self._label = label
        self._cache: dict[str, list[float]] = (
            json.loads(cache_path.read_text()) if cache_path.exists() else {}
        )

    def search(self, query: str, k: int) -> list[Hit]:
        key = hashlib.sha256(f"{self._index.model}\n{query}".encode()).hexdigest()
        if key not in self._cache:
            vec = self._embedder.embed([query], purpose=f"{self._label}: embed eval query")[0]
            self._cache[key] = [float(x) for x in vec]
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(self._cache))
        return self._index.search_vector(np.asarray(self._cache[key], dtype=np.float32), k)


def main(argv: list[str]) -> int:
    confirm = "--confirm" in argv
    chunks = load_chunks(CHUNKS_DIR / "chunks.jsonl")
    index_path = INDEX_DIR / "dense_text-embedding-3-small.npz"
    existing = DenseIndex.load(index_path)
    todo = pending_chunks(chunks, existing)
    guard = default_guard()
    estimate = guard.cost(MODEL_KEY, Usage(sum(estimate_tokens(c.text) for c in todo), 0))
    key_state = "set" if get_secret("OPENAI_API_KEY") else "MISSING"
    print(f"OPENAI_API_KEY: {key_state}")
    print(f"chunks to embed: {len(todo)} of {len(chunks)}; conservative cost estimate ${estimate}")
    print(f"spent so far (all phases): ${guard.ledger.spent()}")
    if not confirm:
        print("dry run only; re-run with --confirm to spend.")
        return 0
    api_key = get_secret("OPENAI_API_KEY")
    if api_key is None:
        print("refusing: OPENAI_API_KEY is empty. Set it in .env (never in chat).")
        return 2
    raw = OpenAIEmbedder(api_key, model=MODEL)
    try:
        index_embedder = GuardedEmbedder(raw, guard)
        index = build_index(chunks, existing, index_embedder)
        index.save(index_path)
        searcher = DenseSearcher(
            index,
            GuardedEmbedder(raw, guard, eval_run_id=EVAL_RUN_ID),
            INDEX_DIR / "query_embeddings.json",
        )
        gold = load_gold(REPO_ROOT / "eval/phase0_retrieval_gold.jsonl")
        bm25 = BM25Index([c.chunk_id for c in chunks], [c.text for c in chunks])
        print(format_metrics("BM25 baseline", evaluate(gold, chunks, bm25.search)))
        print(
            format_metrics(
                "Dense baseline (text-embedding-3-small)", evaluate(gold, chunks, searcher.search)
            )
        )
    finally:
        raw.close()
    print(f"spent so far (all phases): ${guard.ledger.spent()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
