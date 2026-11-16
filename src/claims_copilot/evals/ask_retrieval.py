"""Ask extension, step 1: retrieval variants for investigator questions (2026-11-15).

Variants (fixed in DECISIONS.md 2026-11-15 before the fresh set was run):
  V0  BM25 (the agent's current policy search; free)
  V3  BM25 + dense, RRF, then LLM rerank of the top 20 (Phase 6 winner)
  V7  LLM query rewrite into 1-3 keyword queries; V2 per query and for the question, RRF, then the
      same rerank against the investigator's question
  +R  any of them with the minimum-relevance filter (`relevance.py`) against the question

Sets: `dev` = Phase 0 gold (40 answerable) + Phase 7 unanswerable dev split; `fresh` = the
independently authored `eval/ask_cases_v1.jsonl` (policy kinds + unanswerable); `old` = Phase 6
held-out gold + Phase 7 unanswerable test split (report only; never used to choose anything).

Dry run by default: everything cached runs offline and the paid remainder is estimated.
`--confirm` spends (phase p6, eval_run_id `ask-s1-<set>`).
Run: `uv run python -m claims_copilot.evals.ask_retrieval --set dev [--confirm] [--json FILE]`
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

from claims_copilot.agent.prompt import load_prompt
from claims_copilot.agent.providers import OpenAIProvider
from claims_copilot.budget import CostGuard, Usage, default_guard, estimate_tokens
from claims_copilot.evals.casefile import read_cases
from claims_copilot.evals.split import assign_splits
from claims_copilot.ingest.chunk import Chunk
from claims_copilot.project import CACHE_DIR, CHUNKS_DIR, INDEX_DIR, REPO_ROOT
from claims_copilot.retrieval.bm25 import BM25Index, Hit
from claims_copilot.retrieval.dense import MODEL, MODEL_KEY, DenseIndex, GuardedEmbedder
from claims_copilot.retrieval.embed import OpenAIEmbedder
from claims_copilot.retrieval.evaluate import GoldItem, is_hit, load_chunks, load_gold
from claims_copilot.retrieval.fusion import CANDIDATE_DEPTH, TOP_K, Search, hybrid, rrf
from claims_copilot.retrieval.relevance import Vector, filter_hits
from claims_copilot.retrieval.rerank import MAX_OUTPUT_TOKENS as RERANK_OUT
from claims_copilot.retrieval.rerank import PROMPT_VERSION as RERANK_PROMPT
from claims_copilot.retrieval.rerank import Reranker
from claims_copilot.retrieval.rewrite import PROMPT_VERSION as REWRITE_PROMPT
from claims_copilot.retrieval.rewrite import Rewriter
from claims_copilot.secrets import get_secret
from claims_copilot.sources.verify import normalize

LLM_MODEL = "gpt-6-luna"
LLM_KEY = f"openai/{LLM_MODEL}"
PHASE = "p6"
QUERY_CACHE = INDEX_DIR / "query_embeddings.json"
RERANK_CACHE = CACHE_DIR / f"rerank_{RERANK_PROMPT}_{LLM_MODEL}.jsonl"
REWRITE_CACHE = CACHE_DIR / f"rewrite_{REWRITE_PROMPT}_{LLM_MODEL}.jsonl"
FRESH_CASES = REPO_ROOT / "eval/ask_cases_v1.jsonl"
THRESHOLD_GRID = tuple(round(0.20 + 0.01 * i, 2) for i in range(41))  # 0.20 .. 0.60
MAX_GOLD_LOSS = 1  # pre-registered: tau may cost at most 1 of the dev questions V3 finds
# Two-tier rule, added after the fresh and old results were seen (labelled as such): the gate
# stays at the pre-registered tau; the keep floor is chosen on dev only (choose_keep_floor).
TWO_TIER_GATE = 0.51


@dataclass(frozen=True)
class QuestionSet:
    name: str
    gold: list[GoldItem]
    unanswerable: list[tuple[str, str]]  # (case id, question)
    # The fresh author checked quotes with all whitespace removed (the agent's quote rule), so
    # that set is scored the same way; dev and old keep the Phase 0 rule for comparability.
    whitespace_free: bool = False


def gold_hit(item: GoldItem, chunk: Chunk, *, whitespace_free: bool) -> bool:
    if not whitespace_free:
        return is_hit(item, chunk)
    needle = "".join(normalize(item.evidence).split())
    return chunk.source_id == item.source_id and needle in "".join(normalize(chunk.text).split())


def load_set(name: str) -> QuestionSet:
    unans = read_cases(REPO_ROOT / "eval/phase7_unanswerable.jsonl")
    splits = assign_splits(unans)
    if name == "dev":
        gold = load_gold(REPO_ROOT / "eval/phase0_retrieval_gold.jsonl")
        return QuestionSet(
            name, gold, [(c.case_id, c.question) for c in unans if splits[c.case_id] == "dev"]
        )
    if name == "old":
        gold = load_gold(REPO_ROOT / "eval/phase6_retrieval_gold.jsonl")
        return QuestionSet(
            name, gold, [(c.case_id, c.question) for c in unans if splits[c.case_id] == "test"]
        )
    if name == "fresh":
        rows = [
            json.loads(line)
            for line in FRESH_CASES.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        gold = [
            GoldItem(
                r["case_id"],
                "paraphrase" if r["kind"] == "policy_paraphrase" else "direct",
                r["question"],
                r["expected_in_sources"][0],
                r["gold_quote"],
            )
            for r in rows
            if r["kind"] in ("policy", "policy_paraphrase")
        ]
        unanswerable = [(r["case_id"], r["question"]) for r in rows if r["kind"] == "unanswerable"]
        return QuestionSet(name, gold, unanswerable, whitespace_free=True)
    raise ValueError(f"unknown set: {name}")


class QueryVectors:
    """Question embeddings from the shared on-disk cache; embeds misses only when live."""

    def __init__(self, index: DenseIndex, embedder: GuardedEmbedder | None) -> None:
        self._index, self._embedder = index, embedder
        self._cache: dict[str, list[float]] = (
            json.loads(QUERY_CACHE.read_text()) if QUERY_CACHE.exists() else {}
        )

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self._index.model}\n{text}".encode()).hexdigest()

    def missing(self, texts: list[str]) -> list[str]:
        return sorted({t for t in texts if self._key(t) not in self._cache})

    def vector(self, text: str) -> Vector:
        key = self._key(text)
        if key not in self._cache:
            if self._embedder is None:
                raise KeyError("query embedding not cached (offline mode)")
            vec = self._embedder.embed([text], purpose="p6 ask step 1: embed query")[0]
            self._cache[key] = [float(x) for x in vec]
            QUERY_CACHE.write_text(json.dumps(self._cache))
        return np.asarray(self._cache[key], dtype=np.float32)

    def search(self, text: str, k: int) -> list[Hit]:
        return self._index.search_vector(self.vector(text), k)


def ranks_after_filter(
    hits: list[Hit],
    keep: set[str] | None,
    item: GoldItem,
    by_id: dict[str, Chunk],
    *,
    whitespace_free: bool = False,
) -> tuple[int | None, int]:
    """(rank of the first gold hit after removing withheld hits, number of hits kept)."""
    shown = [h for h in hits if keep is None or h.chunk_id in keep]
    rank = next(
        (
            i
            for i, h in enumerate(shown, 1)
            if gold_hit(item, by_id[h.chunk_id], whitespace_free=whitespace_free)
        ),
        None,
    )
    return rank, len(shown)


def metrics(ranks: list[int | None]) -> dict[str, float]:
    n = len(ranks)
    out = {f"R@{k}": sum(1 for r in ranks if r is not None and r <= k) / n for k in (1, 5, 10)}
    out["MRR@10"] = sum(1 / r for r in ranks if r is not None and r <= 10) / n
    return out


class Rig:
    """Searches for every variant, over cached or live embeddings, rewrites and reranks."""

    def __init__(self, chunks: list[Chunk], *, live: bool, guard: CostGuard, run_id: str) -> None:
        index = DenseIndex.load(INDEX_DIR / f"dense_{MODEL}.npz")
        if index is None:
            raise SystemExit("dense index missing; build it first")
        self.index = index
        self._row = {cid: i for i, cid in enumerate(index.ids)}
        self.chunks = chunks
        self.provider: OpenAIProvider | None = None
        embedder: GuardedEmbedder | None = None
        raw: OpenAIEmbedder | None = None
        if live:
            key = get_secret("OPENAI_API_KEY")
            if not key:
                raise SystemExit("refusing: OPENAI_API_KEY is empty. Set it in .env.")
            raw = OpenAIEmbedder(key, model=MODEL)
            embedder = GuardedEmbedder(raw, guard, phase=PHASE, eval_run_id=run_id)
            self.provider = OpenAIProvider(key, LLM_MODEL)
        self._raw = raw
        self.qv = QueryVectors(index, embedder)
        self.bm25 = BM25Index([c.chunk_id for c in chunks], [c.text for c in chunks])
        self.v2: Search = hybrid(self.bm25.search, self.qv.search)
        rprompt = load_prompt(RERANK_PROMPT)
        self.rewriter = Rewriter(
            self.provider,
            guard if live else None,
            load_prompt(REWRITE_PROMPT),
            REWRITE_CACHE,
            phase=PHASE,
            eval_run_id=run_id,
        )
        live_guard = guard if live else None
        self.v3 = Reranker(
            self.v2,
            chunks,
            self.provider,
            live_guard,
            rprompt,
            RERANK_CACHE,
            eval_run_id=run_id,
            phase=PHASE,
        )
        self.v7 = Reranker(
            self.v7_candidates,
            chunks,
            self.provider,
            live_guard,
            rprompt,
            RERANK_CACHE,
            eval_run_id=run_id,
            phase=PHASE,
        )
        self._live = live
        self.offline_fallbacks = 0

    def _reranked(self, reranker: Reranker, base: Search) -> Search:
        """Offline, a rerank that is not cached (live, it failed validation and was never
        cached) keeps the fused order, which is what the live run showed; counted."""

        def search(question: str, k: int) -> list[Hit]:
            try:
                return reranker.search(question, k)
            except RuntimeError:
                if self._live:
                    raise
                self.offline_fallbacks += 1
                return base(question, k)

        return search

    def close(self) -> None:
        if self.provider is not None:
            self.provider.close()
        if self._raw is not None:
            self._raw.close()

    def v7_candidates(self, question: str, k: int) -> list[Hit]:
        lists = [self.v2(question, CANDIDATE_DEPTH)]
        lists += [self.v2(q, CANDIDATE_DEPTH) for q in self.rewriter.queries(question)]
        return rrf(lists)[:k]

    def chunk_vector(self, chunk_id: str) -> Vector:
        vec: Vector = self.index.vectors[self._row[chunk_id]]
        return vec

    def searches(self) -> dict[str, Search]:
        return {
            "V0 BM25": self.bm25.search,
            "V3 Hybrid + rerank": self._reranked(self.v3, self.v2),
            "V7 Rewrite + hybrid + rerank": self._reranked(self.v7, self.v7_candidates),
        }


def pending(rig: Rig, questions: list[str]) -> dict[str, Any]:
    """Uncached paid work for the whole set, with an upper-bound cost.

    Rerank candidates are unknown until the question is embedded and rewritten, so every
    question is assumed to need two uncached reranks (V3 and V7) of the 20 longest chunks.
    """
    guard = default_guard()
    emb = rig.qv.missing(questions)
    rewrites = [q for q in questions if not rig.rewriter.cached(q)]
    longest = sorted((estimate_tokens(c.text) for c in rig.chunks), reverse=True)
    rerank_in = estimate_tokens(load_prompt(RERANK_PROMPT).text) + sum(longest[:CANDIDATE_DEPTH])
    n = len(questions)
    cost = guard.cost(MODEL_KEY, Usage(sum(estimate_tokens(q) for q in emb) + 3 * 20 * n, 0))
    cost += guard.cost(
        LLM_KEY,
        Usage(
            sum(rig.rewriter.estimate(q).input_tokens for q in rewrites) + 2 * n * rerank_in,
            sum(rig.rewriter.estimate(q).output_tokens for q in rewrites) + 2 * n * RERANK_OUT,
        ),
    )
    return {
        "questions": n,
        "embed_questions": len(emb),
        "rewrite_calls": len(rewrites),
        "rerank_calls_upper": 2 * n,
        "upper_bound_usd": str(cost),
    }


def evaluate_set(rig: Rig, qs: QuestionSet, thresholds: tuple[float, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {"set": qs.name, "answerable_n": len(qs.gold)}
    result["unanswerable_n"] = len(qs.unanswerable)
    variants: dict[str, Any] = {}
    for name, search in rig.searches().items():
        try:
            variants[name] = _evaluate_variant(rig, qs, search, thresholds)
        except (KeyError, RuntimeError) as exc:
            variants[name] = {"skipped": f"needs paid work not yet done ({type(exc).__name__})"}
    result["variants"] = variants
    return result


def _evaluate_variant(
    rig: Rig, qs: QuestionSet, search: Search, thresholds: tuple[float, ...]
) -> dict[str, Any]:
    by_id = {c.chunk_id: c for c in rig.chunks}
    ans_hits = {g.id: search(g.question, TOP_K) for g in qs.gold}
    un_hits = {cid: search(q, TOP_K) for cid, q in qs.unanswerable}
    ws = qs.whitespace_free
    base = [
        ranks_after_filter(ans_hits[g.id], None, g, by_id, whitespace_free=ws)[0] for g in qs.gold
    ]
    row: dict[str, Any] = {
        "no_filter": metrics(base),
        "ranks": dict(zip([g.id for g in qs.gold], base, strict=True)),
        "unanswerable_top3": {cid: [h.chunk_id for h in un_hits[cid][:3]] for cid in un_hits},
    }

    def filtered(hits: list[Hit], question: str, gate: float, keep: float) -> list[Hit]:
        vectors, refs = _vectors(rig, hits), [rig.qv.vector(question)]
        return filter_hits(hits, vectors, refs, gate, keep_threshold=keep).kept

    def stats(gate: float, keep_at: float) -> dict[str, Any]:
        ranks: list[int | None] = []
        kept_counts: list[int] = []
        for g in qs.gold:
            keep = {h.chunk_id for h in filtered(ans_hits[g.id], g.question, gate, keep_at)}
            r, kept = ranks_after_filter(ans_hits[g.id], keep, g, by_id, whitespace_free=ws)
            ranks.append(r)
            kept_counts.append(kept)
        return {
            **metrics(ranks),
            "gold_lost_by_filter": [
                g.id for g, b, r in zip(qs.gold, base, ranks, strict=True) if b and r is None
            ],
            "answerable_all_withheld": sum(1 for k in kept_counts if k == 0),
            "mean_hits_kept": sum(kept_counts) / len(kept_counts),
            "unanswerable_all_withheld": [
                cid for cid, q in qs.unanswerable if not filtered(un_hits[cid], q, gate, keep_at)
            ],
        }

    row["filtered"] = {f"{t:.2f}": stats(t, t) for t in thresholds}
    row["two_tier"] = {
        f"{TWO_TIER_GATE:.2f}/{k:.2f}": stats(TWO_TIER_GATE, k)
        for k in thresholds
        if k <= TWO_TIER_GATE
    }
    row["unanswerable_best_cosine"] = {
        cid: round(
            filter_hits(
                un_hits[cid], _vectors(rig, un_hits[cid]), [rig.qv.vector(q)], 0.0
            ).best_cosine
            or 0.0,
            4,
        )
        for cid, q in qs.unanswerable
    }
    return row


def _vectors(rig: Rig, hits: list[Hit]) -> dict[str, Vector]:
    return {h.chunk_id: rig.chunk_vector(h.chunk_id) for h in hits}


def choose_threshold(dev: dict[str, Any], variant: str = "V3 Hybrid + rerank") -> float | None:
    """Pre-registered rule: the largest tau on the grid at which the filter removes the gold hit
    from the top 10 for at most MAX_GOLD_LOSS dev questions that the variant finds."""
    row = dev["variants"].get(variant, {})
    best = None
    for tau_s, m in row.get("filtered", {}).items():
        if len(m["gold_lost_by_filter"]) <= MAX_GOLD_LOSS:
            best = max(best or 0.0, float(tau_s))
    return best


def choose_keep_floor(dev: dict[str, Any], variant: str = "V3 Hybrid + rerank") -> float | None:
    """Two-tier keep floor: the largest value at which the dev questions the variant finds lose
    no gold hit beyond those the gate itself withholds (post hoc; see TWO_TIER_GATE)."""
    row = dev["variants"].get(variant, {})
    gate_only = row.get("two_tier", {}).get(f"{TWO_TIER_GATE:.2f}/0.20", {})
    allowed = set(gate_only.get("gold_lost_by_filter", []))
    best = None
    for key, m in row.get("two_tier", {}).items():
        if set(m["gold_lost_by_filter"]) <= allowed:
            best = max(best or 0.0, float(key.split("/")[1]))
    return best


def spend_by_purpose(guard: CostGuard, run_id: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, Decimal]] = {}
    for e in guard.ledger.entries():
        if e.eval_run_id == run_id and e.status == "ok":
            d = out.setdefault(e.purpose, {"calls": Decimal(0), "usd": Decimal(0)})
            d["calls"] += 1
            d["usd"] += e.cost_usd
    return {
        p: {"calls": str(d["calls"]), "usd": str(d["usd"]), "mean_usd": str(d["usd"] / d["calls"])}
        for p, d in out.items()
    }


def _warm(rig: Rig, questions: list[str]) -> None:
    for q in questions:  # embeddings and rewrites first, serially (they share on-disk caches)
        rig.qv.vector(q)
        for x in rig.rewriter.queries(q):
            rig.qv.vector(x)
    work: list[Callable[[], object]] = []
    for q in questions:
        work.append(lambda q=q: rig.v3.search(q, TOP_K))  # type: ignore[misc]
        work.append(lambda q=q: rig.v7.search(q, TOP_K))  # type: ignore[misc]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda f: f(), work))


def _filter_line(label: str, f: dict[str, Any], n_unanswerable: int) -> str:
    return (
        f"{label:<30} R@1 {f['R@1']:.2f}  R@5 {f['R@5']:.2f}  R@10 {f['R@10']:.2f}  "
        f"gold lost {f['gold_lost_by_filter']}  answerable all-withheld "
        f"{f['answerable_all_withheld']}  mean kept {f['mean_hits_kept']:.1f}  "
        f"unanswerable all-withheld {len(f['unanswerable_all_withheld'])}/{n_unanswerable}"
    )


def _print(result: dict[str, Any], tau: float | None, keep: float | None) -> None:
    n_un = result["unanswerable_n"]
    print(f"== set {result['set']}: answerable {result['answerable_n']}, unanswerable {n_un}")
    for name, row in result["variants"].items():
        if "skipped" in row:
            print(f"{name}: skipped ({row['skipped']})")
            continue
        m = row["no_filter"]
        print(
            f"{name:<30} R@1 {m['R@1']:.2f}  R@5 {m['R@5']:.2f}  R@10 {m['R@10']:.2f}  "
            f"MRR {m['MRR@10']:.3f}"
        )
        if tau is not None:
            print(_filter_line(f"  + filter tau={tau:.2f}", row["filtered"][f"{tau:.2f}"], n_un))
        if keep is not None:
            key = f"{TWO_TIER_GATE:.2f}/{keep:.2f}"
            print(_filter_line(f"  + two-tier {key}", row["two_tier"][key], n_un))


def main(argv: list[str]) -> int:
    which = argv[argv.index("--set") + 1] if "--set" in argv else "dev"
    confirm = "--confirm" in argv
    run_id = f"ask-s1-{which}"
    qs = load_set(which)
    chunks = load_chunks(CHUNKS_DIR / "chunks.jsonl")
    guard = default_guard()
    questions = [g.question for g in qs.gold] + [q for _, q in qs.unanswerable]
    rig = Rig(chunks, live=confirm, guard=guard, run_id=run_id)
    try:
        todo = pending(rig, questions)
        print(f"paid work not cached: {todo}")
        if confirm:
            _warm(rig, questions)
        result = evaluate_set(rig, qs, THRESHOLD_GRID)
        result["model_stats"] = {
            name: {k: v for k, v in vars(stats).items() if k != "fallbacks"}
            for name, stats in (
                ("rerank_v3", rig.v3.stats),
                ("rerank_v7", rig.v7.stats),
                ("rewrite", rig.rewriter.stats),
            )
        }
        print(f"model call stats (this process): {result['model_stats']}")
    finally:
        rig.close()
    tau: float | None
    if "--tau" in argv:
        tau = float(argv[argv.index("--tau") + 1])
    else:
        tau = choose_threshold(result) if which == "dev" else None
    keep: float | None
    if "--keep" in argv:
        keep = float(argv[argv.index("--keep") + 1])
    else:
        keep = choose_keep_floor(result) if which == "dev" else None
    result["tau"], result["two_tier_keep"] = tau, keep
    result["offline_rerank_fallbacks"] = rig.offline_fallbacks
    result["spend"] = spend_by_purpose(guard, run_id)
    result["p6_spent_total"] = str(guard.ledger.spent(phase=PHASE))
    print(f"offline rerank fallbacks (fused order kept): {rig.offline_fallbacks}")
    _print(result, tau, keep)
    print(f"spend for {run_id}: {result['spend']}")
    if "--json" in argv:
        Path(argv[argv.index("--json") + 1]).write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
