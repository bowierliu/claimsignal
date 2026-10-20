"""Policy search over the verified public corpus, with every hit tied to its manifest row.

Default is lexical BM25: free and offline (recall@10 0.80 overall, 0.25 on paraphrases). The server
can opt in to the Phase 6 pipeline (BM25 + dense, then an LLM rerank) with
`--policy-mode hybrid`; that makes paid calls through CostGuard and falls back to lexical, saying
so in the response, when it cannot run. A chunk whose source is not a VERIFIED manifest row is
never served, so every hit can name its source, URL and hash. Retrieved text is untrusted; the API
labels it and never interprets it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from claims_copilot.ingest.chunk import Chunk
from claims_copilot.project import CHUNKS_DIR, MANIFEST_PATH
from claims_copilot.retrieval.bm25 import BM25Index, Hit
from claims_copilot.retrieval.evaluate import load_chunks
from claims_copilot.retrieval.pipeline import (
    PipelineResult,
    PipelineUnavailableError,
    load_pipeline,
)
from claims_copilot.sources.manifest import read_manifest

CHUNKS_PATH = CHUNKS_DIR / "chunks.jsonl"
RANKING_NAMES = {
    "lexical": "BM25 (lexical)",
    "hybrid": "BM25 + dense embeddings, fused by reciprocal rank (rerank not applied)",
    "hybrid_rerank": "BM25 + dense embeddings, fused, then reordered by an LLM reranker",
}
PolicyMode = Literal["lexical", "hybrid", "hybrid_rerank"]


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    title: str
    url: str
    retrieved_at: str
    sha256: str


class HybridSearch(Protocol):
    def search(self, query: str, k: int) -> PipelineResult: ...


@dataclass(frozen=True)
class PolicyHit:
    chunk: Chunk
    source: SourceRef
    bm25: float | None  # lexical score; None when the hit came from the hybrid pipeline


@dataclass(frozen=True)
class PolicyResult:
    hits: list[PolicyHit]
    mode: PolicyMode
    fallback_reason: str | None


class PolicyIndex:
    def __init__(
        self,
        chunks: Iterable[Chunk],
        sources: Mapping[str, SourceRef],
        *,
        hybrid: HybridSearch | None = None,
        hybrid_unavailable: str | None = None,
    ) -> None:
        self._chunks = [c for c in chunks if c.source_id in sources]
        self._by_id = {c.chunk_id: c for c in self._chunks}
        self._sources = dict(sources)
        self._index = BM25Index([c.chunk_id for c in self._chunks], [c.text for c in self._chunks])
        self._hybrid = hybrid
        self._hybrid_unavailable = hybrid_unavailable

    @property
    def size(self) -> int:
        return len(self._chunks)

    @property
    def hybrid_enabled(self) -> bool:
        return self._hybrid is not None

    def _hits(self, hits: list[Hit], *, lexical: bool) -> list[PolicyHit]:
        out = []
        for h in hits:
            chunk = self._by_id.get(h.chunk_id)  # drops any chunk that is not a verified source
            if chunk is not None:
                out.append(
                    PolicyHit(chunk, self._sources[chunk.source_id], h.score if lexical else None)
                )
        return out

    def search(self, query: str, k: int) -> PolicyResult:
        reason = self._hybrid_unavailable
        if self._hybrid is not None:
            try:
                result = self._hybrid.search(query, k)
            except PipelineUnavailableError as exc:
                reason = f"hybrid search unavailable ({exc}); lexical results shown"
            else:
                return PolicyResult(self._hits(result.hits, lexical=False), result.mode, None)
        lexical = self._hits(self._index.search(query, k), lexical=True)
        return PolicyResult(lexical, "lexical", reason)


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
    chunks_path: Path = CHUNKS_PATH,
    manifest_path: Path = MANIFEST_PATH,
    *,
    mode: Literal["lexical", "hybrid"] = "lexical",
) -> PolicyIndex | None:
    """The index over the local chunk file, or None when the corpus has not been ingested.

    With mode "hybrid" it also tries to load the Phase 6 pipeline. If that cannot be built, the
    index serves lexical results and every response says why.
    """
    if not chunks_path.is_file():
        return None
    chunks = load_chunks(chunks_path)
    sources = source_refs(manifest_path)
    if mode == "lexical":
        return PolicyIndex(chunks, sources)
    try:
        return PolicyIndex(chunks, sources, hybrid=load_pipeline(chunks))
    except PipelineUnavailableError as exc:
        return PolicyIndex(
            chunks,
            sources,
            hybrid_unavailable=f"hybrid search unavailable ({exc}); lexical results shown",
        )
