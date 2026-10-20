"""Lexical (BM25) search over the verified public corpus, with every hit tied to its manifest row.

This is the free baseline (recall@10 0.80 overall, 0.25 on paraphrases; see EVALUATION.md). Dense
search is not offered here because each query would be a paid embedding call. A chunk whose source
is not a VERIFIED manifest row is never indexed, so every hit can name its source, URL and hash.
Retrieved text is untrusted; the API labels it and never interprets it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from claims_copilot.ingest.chunk import Chunk
from claims_copilot.project import CHUNKS_DIR, MANIFEST_PATH
from claims_copilot.retrieval.bm25 import BM25Index
from claims_copilot.retrieval.evaluate import load_chunks
from claims_copilot.sources.manifest import read_manifest

CHUNKS_PATH = CHUNKS_DIR / "chunks.jsonl"
RANKING_NAME = "BM25 (lexical baseline; replaced in a later phase)"


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    title: str
    url: str
    retrieved_at: str
    sha256: str


@dataclass(frozen=True)
class PolicyHit:
    chunk: Chunk
    source: SourceRef
    bm25: float


class PolicyIndex:
    def __init__(self, chunks: Iterable[Chunk], sources: Mapping[str, SourceRef]) -> None:
        self._chunks = [c for c in chunks if c.source_id in sources]
        self._by_id = {c.chunk_id: c for c in self._chunks}
        self._sources = dict(sources)
        self._index = BM25Index([c.chunk_id for c in self._chunks], [c.text for c in self._chunks])

    @property
    def size(self) -> int:
        return len(self._chunks)

    def search(self, query: str, k: int) -> list[PolicyHit]:
        hits = self._index.search(query, k)
        return [
            PolicyHit(
                self._by_id[h.chunk_id], self._sources[self._by_id[h.chunk_id].source_id], h.score
            )
            for h in hits
        ]


def source_refs(manifest_path: Path = MANIFEST_PATH) -> dict[str, SourceRef]:
    """Verified corpus sources from the manifest."""
    return {
        r["source_id"]: SourceRef(
            source_id=r["source_id"],
            title=r.get("title", ""),
            url=r.get("final_url") or r.get("url", ""),
            retrieved_at=r.get("retrieved_at", ""),
            sha256=r["sha256"],
        )
        for r in read_manifest(manifest_path)
        if r.get("role") == "corpus" and r.get("status") == "VERIFIED"
    }


def load_policy_index(
    chunks_path: Path = CHUNKS_PATH, manifest_path: Path = MANIFEST_PATH
) -> PolicyIndex | None:
    """The index over the local chunk file, or None when the corpus has not been ingested."""
    if not chunks_path.is_file():
        return None
    return PolicyIndex(load_chunks(chunks_path), source_refs(manifest_path))
