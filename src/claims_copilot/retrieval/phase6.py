"""Phase 6 variant runner. The offline stage (V0, V1, V2) makes no network or paid call.

V1 uses only query embeddings already cached by Phase 0; a missing one is an error, never a paid
call. Run: `uv run python -m claims_copilot.retrieval.phase6`
"""

from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np

from claims_copilot.agent.prompt import load_prompt
from claims_copilot.agent.providers import OpenAIProvider
from claims_copilot.budget import Usage, default_guard, estimate_tokens
from claims_copilot.ingest.chunk import Chunk
from claims_copilot.project import CACHE_DIR, CHUNKS_DIR, INDEX_DIR, REPO_ROOT
from claims_copilot.retrieval.bm25 import BM25Index, Hit
from claims_copilot.retrieval.contextual import MODEL as CTX_MODEL
from claims_copilot.retrieval.contextual import PROMPT_VERSION, DescriptionCache, build_jobs
from claims_copilot.retrieval.dense import (
    MODEL,
    MODEL_KEY,
    DenseIndex,
    DenseSearcher,
    GuardedEmbedder,
    build_index,
    pending_chunks,
)
from claims_copilot.retrieval.embed import OpenAIEmbedder
from claims_copilot.retrieval.evaluate import (
    GoldItem,
    evaluate,
    format_metrics,
    load_chunks,
    load_gold,
)
from claims_copilot.retrieval.fusion import Search, compare, first_hit_rank, hybrid
from claims_copilot.retrieval.rerank import PROMPT_VERSION as RERANK_PROMPT
from claims_copilot.retrieval.rerank import Reranker
from claims_copilot.secrets import get_secret
from claims_copilot.sources.catalog import load_catalog


class CacheOnlyDense:
    """Dense search over cached query embeddings. Raises KeyError instead of embedding."""

    def __init__(self, index: DenseIndex, cache_path: Path) -> None:
        self._index = index
        self._cache: dict[str, list[float]] = json.loads(cache_path.read_text())

    def search(self, query: str, k: int) -> list[Hit]:
        key = hashlib.sha256(f"{self._index.model}\n{query}".encode()).hexdigest()
        if key not in self._cache:
            raise KeyError(f"query embedding not cached: {query[:50]!r}")
        return self._index.search_vector(np.asarray(self._cache[key], dtype=np.float32), k)


MODEL_KEY_LLM = f"openai/{CTX_MODEL}"
CTX_INDEX_PATH = INDEX_DIR / f"dense_contextual_v1_{MODEL}.npz"


def contextual_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Chunks whose text is `description + chunk`, for building the V4 to V6 indexes only.

    Ids match the originals, so a hit maps back to the original chunk (and original text) for the
    quote check and for anything shown to the agent.
    """
    titles = {e.source_id: e.title for e in load_catalog(REPO_ROOT / "SOURCES/catalog.toml")}
    prompt = load_prompt(PROMPT_VERSION)
    cache = DescriptionCache(CACHE_DIR / f"contextual_{PROMPT_VERSION}_{CTX_MODEL}.jsonl")
    out = []
    for job in build_jobs(chunks, titles, prompt):
        description = cache.rows.get(job.key)
        text = f"{description}\n\n{job.chunk.text}" if description else job.chunk.text
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        out.append(replace(job.chunk, text=text, sha256=sha))
    return out


def build_contextual_index(chunks: list[Chunk], *, confirm: bool) -> int:
    ctx = contextual_chunks(chunks)
    existing = DenseIndex.load(CTX_INDEX_PATH)
    todo = pending_chunks(ctx, existing)
    guard = default_guard()
    estimate = guard.cost(MODEL_KEY, Usage(sum(estimate_tokens(c.text) for c in todo), 0))
    print(f"contextual chunks to embed: {len(todo)} of {len(ctx)}; upper-bound cost ${estimate}")
    if not confirm or not todo:
        print("nothing spent." if not todo else "dry run only; re-run with --confirm to spend.")
        return 0
    key = get_secret("OPENAI_API_KEY")
    if not key:
        print("refusing: OPENAI_API_KEY is empty. Set it in .env (never in chat).")
        return 2
    raw = OpenAIEmbedder(key, model=MODEL)
    try:
        embedder = GuardedEmbedder(raw, guard, phase="p6")
        build_index(ctx, existing, embedder).save(CTX_INDEX_PATH)
    finally:
        raw.close()
    print(f"saved {CTX_INDEX_PATH.name}; p6 spent: ${guard.ledger.spent(phase='p6')}")
    return 0


GOLD_FILES = {
    "dev": "eval/phase0_retrieval_gold.jsonl",
    "heldout": "eval/phase6_retrieval_gold.jsonl",
}
# Pre-registered (docs/PHASE6_PLAN.md): the held-out set is run once, for the winner chosen on the
# development set (V3, best on every development metric) and for V0 and V1 as references.
WINNER = "V3 Hybrid + rerank"
HELDOUT_VARIANTS = frozenset({"V0 BM25", "V1 Dense", "V2 Hybrid RRF", WINNER})
QUERY_CACHE = INDEX_DIR / "query_embeddings.json"
RERANK_CACHE = CACHE_DIR / f"rerank_{RERANK_PROMPT}_{CTX_MODEL}.jsonl"


def _arg(argv: list[str], name: str, default: str) -> str:
    return argv[argv.index(name) + 1] if name in argv else default


def embed_queries(gold: list[GoldItem], *, confirm: bool) -> int:
    """Embed gold questions missing from the query cache (paid, tiny, ledgered under p6)."""
    index = DenseIndex.load(INDEX_DIR / f"dense_{MODEL}.npz")
    if index is None:
        return 2
    cache = json.loads(QUERY_CACHE.read_text())
    missing = [
        g.question
        for g in gold
        if hashlib.sha256(f"{index.model}\n{g.question}".encode()).hexdigest() not in cache
    ]
    guard = default_guard()
    est = guard.cost(MODEL_KEY, Usage(sum(estimate_tokens(q) for q in missing), 0))
    print(f"queries to embed: {len(missing)} of {len(gold)}; upper-bound cost ${est}")
    if not confirm or not missing:
        return 0
    key = get_secret("OPENAI_API_KEY")
    if not key:
        print("refusing: OPENAI_API_KEY is empty. Set it in .env (never in chat).")
        return 2
    raw = OpenAIEmbedder(key, model=MODEL)
    try:
        searcher = DenseSearcher(
            index, GuardedEmbedder(raw, guard, phase="p6"), QUERY_CACHE, label="p6"
        )
        for q in missing:
            searcher.search(q, 1)
    finally:
        raw.close()
    print(f"p6 spent: ${guard.ledger.spent(phase='p6')}")
    return 0


def main(argv: list[str]) -> int:
    chunks = load_chunks(CHUNKS_DIR / "chunks.jsonl")
    if "--contextual-embed" in argv:
        return build_contextual_index(chunks, confirm="--confirm" in argv)
    which = _arg(argv, "--gold", "dev")
    gold: list[GoldItem] = load_gold(REPO_ROOT / GOLD_FILES[which])
    if "--embed-queries" in argv:
        return embed_queries(gold, confirm="--confirm" in argv)
    index = DenseIndex.load(INDEX_DIR / f"dense_{MODEL}.npz")
    ctx_index = DenseIndex.load(CTX_INDEX_PATH)
    if index is None or ctx_index is None:
        print("dense indexes missing; build them first")
        return 2
    bm25 = BM25Index([c.chunk_id for c in chunks], [c.text for c in chunks])
    dense = CacheOnlyDense(index, QUERY_CACHE)
    ctx = contextual_chunks(chunks)
    ctx_bm25 = BM25Index([c.chunk_id for c in ctx], [c.text for c in ctx])
    ctx_dense = CacheOnlyDense(ctx_index, QUERY_CACHE)
    v2 = hybrid(bm25.search, dense.search)
    v5 = hybrid(ctx_bm25.search, ctx_dense.search)
    variants: dict[str, Search] = {
        "V0 BM25": bm25.search,
        "V1 Dense": dense.search,
        "V2 Hybrid RRF": v2,
        "V4 Dense contextual": ctx_dense.search,
        "V5 Hybrid contextual": v5,
    }
    pairs = [
        ("V2 Hybrid RRF", "V0 BM25"),
        ("V2 Hybrid RRF", "V1 Dense"),
        ("V4 Dense contextual", "V1 Dense"),
        ("V5 Hybrid contextual", "V2 Hybrid RRF"),
        ("V5 Hybrid contextual", "V1 Dense"),
        ("V5 Hybrid contextual", "V0 BM25"),
    ]
    rerankers: dict[str, Reranker] = {}
    live = "--rerank" in argv
    confirm = "--confirm" in argv
    provider: OpenAIProvider | None = None
    guard = default_guard()
    questions = [g.question for g in gold]
    rprompt = load_prompt(RERANK_PROMPT)
    eval_run = f"p6-{which}"
    try:
        if live and confirm:
            key = get_secret("OPENAI_API_KEY")
            if not key:
                print("refusing: OPENAI_API_KEY is empty. Set it in .env (never in chat).")
                return 2
            provider = OpenAIProvider(key, CTX_MODEL)
        for name, base in (("V3 Hybrid + rerank", v2), ("V6 Hybrid contextual + rerank", v5)):
            if which == "heldout" and name != WINNER:
                continue
            r = Reranker(base, chunks, provider, guard, rprompt, RERANK_CACHE, eval_run_id=eval_run)
            pending = r.pending_estimate(questions)
            if pending:
                total = Usage(
                    sum(u.input_tokens for u in pending), sum(u.output_tokens for u in pending)
                )
                print(
                    f"{name}: {len(pending)} uncached rerank calls; upper-bound "
                    f"${guard.cost(MODEL_KEY_LLM, total)}"
                )
                if not (live and confirm):
                    continue
                with ThreadPoolExecutor(max_workers=4) as pool:  # warm the cache in parallel
                    list(pool.map(lambda q, r=r: r.search(q, 10), questions))
            variants[name] = r.search
            rerankers[name] = r
        pairs += [
            ("V3 Hybrid + rerank", "V2 Hybrid RRF"),
            ("V3 Hybrid + rerank", "V1 Dense"),
            ("V6 Hybrid contextual + rerank", "V5 Hybrid contextual"),
            ("V6 Hybrid contextual + rerank", "V3 Hybrid + rerank"),
        ]
        ranks = {}
        for name, search in variants.items():
            if which == "heldout" and name not in HELDOUT_VARIANTS:
                continue
            print(format_metrics(f"{name} [{which}]", evaluate(gold, chunks, search)))
            ranks[name] = first_hit_rank(gold, chunks, search)
        for cand, base_name in pairs:
            if cand in ranks and base_name in ranks:
                d = compare(ranks[cand], ranks[base_name])
                print(
                    f"{cand} vs {base_name}: gained {len(d.gained)} {list(d.gained)}, "
                    f"lost {len(d.lost)} {list(d.lost)}, "
                    f"rank better {d.improved_rank}, worse {d.worsened_rank}"
                )
        for name, r in rerankers.items():
            st = r.stats
            print(
                f"{name}: model calls {st.calls}, cached {st.cached}, invalid {st.invalid}, "
                f"provider errors {st.provider_errors}, total call time {st.seconds:.0f}s"
            )
    finally:
        if provider is not None:
            provider.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
