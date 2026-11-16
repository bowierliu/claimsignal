"""LLM query rewrite: an investigator question becomes 1-3 short keyword queries (variant V7).

The model sees only the question and returns `{"queries": [...]}`. Plain code accepts 1 to 3
strings of 2 to 10 words and at most 80 characters each; anything else is discarded and the
caller searches with the question alone (counted in `stats`). Rewrites only choose what to search
for: they never reach the agent as evidence, a citation, or a quote. Every paid call goes through
CostGuard; results are cached on disk by prompt hash, model and question.
"""

from __future__ import annotations

import functools
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claims_copilot.agent.prompt import Prompt
from claims_copilot.agent.types import Provider, ProviderError, UserMessage
from claims_copilot.budget import CostGuard, Usage, estimate_tokens

PROMPT_VERSION = "query_rewrite_v1"
PURPOSE = "p6 query rewrite"
MAX_OUTPUT_TOKENS = 200
MAX_QUERIES = 3
MAX_CHARS = 80
WORDS = (2, 10)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["queries"],
    "additionalProperties": False,
}


def parse_queries(text: str) -> list[str] | None:
    """The accepted queries, or None when the output breaks any rule."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or set(data) != {"queries"}:
        return None
    queries = data["queries"]
    if not isinstance(queries, list) or not 1 <= len(queries) <= MAX_QUERIES:
        return None
    out: list[str] = []
    for q in queries:
        if not isinstance(q, str):
            return None
        q = " ".join(q.split())
        if len(q) > MAX_CHARS or not WORDS[0] <= len(q.split()) <= WORDS[1]:
            return None
        if q.lower() not in (x.lower() for x in out):
            out.append(q)
    return out


@dataclass
class RewriteStats:
    calls: int = 0
    cached: int = 0
    invalid: int = 0
    provider_errors: int = 0


class Rewriter:
    def __init__(
        self,
        provider: Provider | None,
        guard: CostGuard | None,
        prompt: Prompt,
        cache_path: Path,
        *,
        phase: str = "p6",
        eval_run_id: str | None = None,
        model_key: str = "openai/gpt-6-luna",
    ) -> None:
        self._provider, self._guard, self._prompt = provider, guard, prompt
        self._cache_path, self._phase, self._eval_run_id = cache_path, phase, eval_run_id
        self._model_key = provider.model_key if provider else model_key
        self.stats = RewriteStats()
        self._cache: dict[str, list[str]] = {}
        if cache_path.exists():
            for line in cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._cache[row["key"]] = row["queries"]

    def _key(self, question: str) -> str:
        parts = [self._prompt.sha256, self._model_key, question]
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()

    def cached(self, question: str) -> bool:
        return self._key(question) in self._cache

    def estimate(self, question: str) -> Usage:
        return Usage(estimate_tokens(self._prompt.text + question) + 20, MAX_OUTPUT_TOKENS)

    def queries(self, question: str) -> list[str]:
        """Keyword queries for `question`; [] when the model output was refused or failed."""
        key = self._key(question)
        if key in self._cache:
            self.stats.cached += 1
            return self._cache[key]
        if self._provider is None or self._guard is None:
            raise KeyError("rewrite not cached and no provider (offline mode)")
        message = f"<question>{question.replace('</question>', '')}</question>"
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
                purpose=PURPOSE,
                estimated_usage=self.estimate(question),
                eval_run_id=self._eval_run_id,
            )
        except ProviderError:
            self.stats.provider_errors += 1
            return []
        self.stats.calls += 1
        parsed = parse_queries(turn.text)
        if parsed is None:
            self.stats.invalid += 1
            parsed = []
        self._cache[key] = parsed
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "queries": parsed}) + "\n")
        return parsed
