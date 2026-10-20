"""LLM reranker over fused candidates (Phase 6, variants V3 and V6).

The model sees the question and up to 20 candidate passages labelled C1..Cn and returns labels in
preferred order. Plain code accepts only labels that were offered (no repeats, no new labels) and
maps them back to chunk ids, so the reranker can reorder text but never add or change it: a prompt
injection inside a chunk cannot put new content in front of the agent. Anything else keeps the
fused order (fail-safe, counted in `stats`). All paid calls go through CostGuard.
"""

from __future__ import annotations

import functools
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claims_copilot.agent.prompt import Prompt
from claims_copilot.agent.types import Provider, ProviderError, UserMessage
from claims_copilot.budget import CostGuard, Usage, estimate_tokens
from claims_copilot.ingest.chunk import Chunk
from claims_copilot.retrieval.bm25 import Hit
from claims_copilot.retrieval.fusion import CANDIDATE_DEPTH, Search

PHASE = "p6"
PROMPT_VERSION = "rerank_v1"
MAX_OUTPUT_TOKENS = 400

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"ranking": {"type": "array", "items": {"type": "string"}}},
    "required": ["ranking"],
    "additionalProperties": False,
}


class RankingError(ValueError):
    pass


def parse_ranking(text: str, offered: int) -> list[int]:
    """Return 0-based candidate positions in the model's order, or raise RankingError."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise RankingError("not valid JSON") from None
    if not isinstance(data, dict) or set(data) != {"ranking"}:
        raise RankingError("wrong JSON shape")
    labels = data["ranking"]
    if not isinstance(labels, list) or len(labels) > offered:
        raise RankingError("ranking must be a list no longer than the candidate list")
    allowed = {f"C{i}": i - 1 for i in range(1, offered + 1)}
    out: list[int] = []
    for label in labels:
        if not isinstance(label, str) or label not in allowed:
            raise RankingError("unknown candidate label")
        if allowed[label] in out:
            raise RankingError("repeated candidate label")
        out.append(allowed[label])
    return out


def apply_ranking(candidates: list[Hit], order: list[int]) -> list[Hit]:
    """Listed candidates first in the model's order, the rest after in their fused order."""
    listed = set(order)
    return [candidates[i] for i in order] + [h for i, h in enumerate(candidates) if i not in listed]


def build_message(question: str, texts: list[str]) -> str:
    body = "\n".join(f'<candidate id="C{i}">{t}</candidate>' for i, t in enumerate(texts, start=1))
    return f"<question>{question}</question>\n{body}"


@dataclass
class RerankStats:
    calls: int = 0
    cached: int = 0
    invalid: int = 0
    provider_errors: int = 0
    seconds: float = 0.0
    fallbacks: list[str] = field(default_factory=list)


class Reranker:
    def __init__(
        self,
        base: Search,
        chunks: list[Chunk],
        provider: Provider | None,
        guard: CostGuard | None,
        prompt: Prompt,
        cache_path: Path,
        *,
        depth: int = CANDIDATE_DEPTH,
        eval_run_id: str | None = None,
        model_key: str = "openai/gpt-6-luna",
        phase: str = PHASE,
    ) -> None:
        self._phase = phase
        self._base = base
        self._by_id = {c.chunk_id: c for c in chunks}
        self._provider, self._guard, self._prompt = provider, guard, prompt
        self._cache_path, self._depth, self._eval_run_id = cache_path, depth, eval_run_id
        self._model_key = provider.model_key if provider else model_key
        self.stats = RerankStats()
        self._cache: dict[str, list[int]] = {}
        if cache_path.exists():
            for line in cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._cache[row["key"]] = row["order"]

    def _key(self, question: str, candidates: list[Hit], model: str) -> str:
        parts = [self._prompt.sha256, model, question]
        parts += [f"{h.chunk_id}:{self._by_id[h.chunk_id].sha256}" for h in candidates]
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()

    def pending_estimate(self, questions: list[str]) -> list[Usage]:
        """Conservative usage of every call a run over `questions` would make (cache misses)."""
        out = []
        for q in questions:
            candidates = self._base(q, self._depth)
            if len(candidates) < 2:
                continue
            if self._key(q, candidates, self._model_key) in self._cache:
                continue
            message = build_message(q, [self._by_id[h.chunk_id].text for h in candidates])
            out.append(Usage(estimate_tokens(self._prompt.text + message), MAX_OUTPUT_TOKENS))
        return out

    def search(self, question: str, k: int) -> list[Hit]:
        return self.search_with_status(question, k)[0]

    def search_with_status(self, question: str, k: int) -> tuple[list[Hit], bool]:
        """Hits and whether the model's order was applied (False: fused order kept)."""
        candidates = self._base(question, self._depth)
        if len(candidates) < 2:
            return candidates[:k], True
        key = self._key(question, candidates, self._model_key)
        order = self._cache.get(key)
        if order is not None:
            self.stats.cached += 1
        else:
            order = self._ask(question, candidates, key)
        return apply_ranking(candidates, order or [])[:k], order is not None

    def _ask(self, question: str, candidates: list[Hit], key: str) -> list[int] | None:
        if self._provider is None or self._guard is None:
            raise RuntimeError("uncached rerank needs a provider and guard (offline mode)")
        texts = [self._by_id[h.chunk_id].text for h in candidates]
        message = build_message(question, texts)
        estimate = Usage(estimate_tokens(self._prompt.text + message), MAX_OUTPUT_TOKENS)
        started = time.perf_counter()
        try:
            turn = self._guard.call(
                functools.partial(
                    self._provider.complete,
                    system=self._prompt.text,
                    messages=[UserMessage(message)],
                    tools=[],
                    schema=SCHEMA,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    allow_tools=False,
                ),
                usage_of=lambda t: t.usage,
                phase=self._phase,
                model_key=self._provider.model_key,
                purpose="p6 rerank",
                estimated_usage=estimate,
                eval_run_id=self._eval_run_id,
            )
        except ProviderError:
            self.stats.seconds += time.perf_counter() - started
            self.stats.provider_errors += 1
            self.stats.fallbacks.append(question[:40])
            return None
        self.stats.seconds += time.perf_counter() - started
        self.stats.calls += 1
        try:
            order = parse_ranking(turn.text, len(candidates))
        except RankingError:
            self.stats.invalid += 1
            self.stats.fallbacks.append(question[:40])
            return None
        self._cache[key] = order
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "order": order}) + "\n")
        return order
