"""The Phase 6 winning pipeline as one object: BM25 + dense (RRF), then LLM rerank (V3).

Used by the API when the server starts with `--policy-mode hybrid`. Every paid call (query
embedding, rerank) goes through CostGuard. Anything that cannot run raises
`PipelineUnavailableError` with a short fixed reason, so the caller can fall back to lexical
search and say so.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from claims_copilot.agent.prompt import load_prompt
from claims_copilot.agent.providers import OpenAIProvider
from claims_copilot.agent.types import ProviderError
from claims_copilot.budget import BudgetError, CostGuard, default_guard
from claims_copilot.ingest.chunk import Chunk
from claims_copilot.project import CACHE_DIR, INDEX_DIR
from claims_copilot.retrieval.bm25 import BM25Index, Hit
from claims_copilot.retrieval.dense import MODEL, DenseIndex, DenseSearcher, GuardedEmbedder
from claims_copilot.retrieval.embed import EmbeddingError, OpenAIEmbedder
from claims_copilot.retrieval.fusion import hybrid
from claims_copilot.retrieval.rerank import PROMPT_VERSION, Reranker
from claims_copilot.secrets import get_secret

PHASE = "p6"
LLM_MODEL = "gpt-6-luna"
Mode = Literal["hybrid", "hybrid_rerank"]


class PipelineUnavailableError(RuntimeError):
    """The hybrid pipeline could not answer. The message is a fixed reason, never a response."""


@dataclass(frozen=True)
class PipelineResult:
    hits: list[Hit]
    mode: Mode


class HybridPipeline:
    def __init__(self, reranker: Reranker) -> None:
        self._reranker = reranker

    def search(self, query: str, k: int) -> PipelineResult:
        try:
            hits, reranked = self._reranker.search_with_status(query, k)
        except BudgetError:
            raise PipelineUnavailableError("spend cap reached") from None
        except (EmbeddingError, ProviderError, httpx.HTTPError):
            raise PipelineUnavailableError("model service unavailable") from None
        except KeyError:
            raise PipelineUnavailableError("index out of date") from None
        return PipelineResult(hits, "hybrid_rerank" if reranked else "hybrid")


def load_pipeline(chunks: list[Chunk], *, guard: CostGuard | None = None) -> HybridPipeline:
    """Build the pipeline from local indexes, or raise PipelineUnavailableError with the reason."""
    key = get_secret("OPENAI_API_KEY")
    if not key:
        raise PipelineUnavailableError("OPENAI_API_KEY is not set")
    index = DenseIndex.load(INDEX_DIR / f"dense_{MODEL}.npz")
    if index is None:
        raise PipelineUnavailableError("dense index is not built")
    if set(index.ids) != {c.chunk_id for c in chunks}:
        raise PipelineUnavailableError("dense index does not match the chunk file")
    guard = guard or default_guard()
    bm25 = BM25Index([c.chunk_id for c in chunks], [c.text for c in chunks])
    dense = DenseSearcher(
        index,
        GuardedEmbedder(OpenAIEmbedder(key, model=MODEL), guard, phase=PHASE),
        Path(INDEX_DIR / "query_embeddings.json"),
        label="p6 api",
    )
    lock = threading.Lock()  # DenseSearcher keeps an on-disk query cache; serialise it

    def dense_search(query: str, k: int) -> list[Hit]:
        with lock:
            return dense.search(query, k)

    reranker = Reranker(
        hybrid(bm25.search, dense_search),
        chunks,
        OpenAIProvider(key, LLM_MODEL),
        guard,
        load_prompt(PROMPT_VERSION),
        CACHE_DIR / f"rerank_{PROMPT_VERSION}_{LLM_MODEL}.jsonl",
    )
    return HybridPipeline(reranker)
