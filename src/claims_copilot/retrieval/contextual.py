"""Contextual chunk descriptions (Phase 6, variants V4 to V6).

Each chunk gets one or two generated sentences saying what it covers and where it sits. The text
embedded for the contextual index is `description + chunk`. Descriptions are used for ranking
ONLY: never shown to the agent, cited, or used by the quote check, which runs on the original
chunk text. All paid calls go through CostGuard. Output is untrusted and validated here.

Run: `uv run python -m claims_copilot.retrieval.contextual`                   (dry run, no spend)
     `uv run python -m claims_copilot.retrieval.contextual --confirm [--limit N]`
"""

from __future__ import annotations

import functools
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claims_copilot.agent.prompt import Prompt, load_prompt
from claims_copilot.agent.providers import OpenAIProvider
from claims_copilot.agent.types import ModelTurn, Provider, ProviderError, UserMessage
from claims_copilot.budget import CostGuard, Usage, default_guard, estimate_tokens
from claims_copilot.ingest.chunk import Chunk
from claims_copilot.project import CACHE_DIR, CHUNKS_DIR, REPO_ROOT
from claims_copilot.retrieval.evaluate import load_chunks
from claims_copilot.secrets import get_secret
from claims_copilot.sources.catalog import load_catalog

PHASE = "p6"
PROMPT_VERSION = "contextualize_v1"
MODEL = "gpt-6-luna"
MODEL_KEY = f"openai/{MODEL}"
NEIGHBOUR_CHARS = 400
MAX_OUTPUT_TOKENS = 400
MAX_DESCRIPTION_CHARS = 500
LIVE_CEILING_USD = 2.00  # owner-approved Phase 6 live spend ceiling (inside the $8 p6 cap)
WORKERS = 4

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"description": {"type": "string"}},
    "required": ["description"],
    "additionalProperties": False,
}


class DescriptionError(ValueError):
    pass


@dataclass(frozen=True)
class Job:
    chunk: Chunk
    message: str
    key: str


def validate_description(text: str) -> str:
    """Parse the model's JSON and return a clean one-line description, or raise."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise DescriptionError("not valid JSON") from None
    if not isinstance(data, dict) or set(data) != {"description"}:
        raise DescriptionError("wrong JSON shape")
    value = data["description"]
    if not isinstance(value, str):
        raise DescriptionError("description must be a string")
    clean = " ".join(value.split())
    if not clean:
        raise DescriptionError("description is empty")
    if len(clean) > MAX_DESCRIPTION_CHARS:
        raise DescriptionError("description too long")
    return clean


def build_jobs(
    chunks: list[Chunk], titles: dict[str, str], prompt: Prompt, model: str = MODEL
) -> list[Job]:
    jobs: list[Job] = []
    for i, chunk in enumerate(chunks):
        prev = chunks[i - 1] if i > 0 and chunks[i - 1].source_id == chunk.source_id else None
        nxt = (
            chunks[i + 1]
            if i + 1 < len(chunks) and chunks[i + 1].source_id == chunk.source_id
            else None
        )
        message = (
            f"<document_title>{titles.get(chunk.source_id, chunk.source_id)}</document_title>\n"
            f"<section_path>{chunk.section}</section_path>\n"
            f"<previous_passage_end>{prev.text[-NEIGHBOUR_CHARS:] if prev else ''}"
            "</previous_passage_end>\n"
            f"<passage>{chunk.text}</passage>\n"
            f"<next_passage_start>{nxt.text[:NEIGHBOUR_CHARS] if nxt else ''}"
            "</next_passage_start>"
        )
        key = hashlib.sha256(
            "\n".join(
                [
                    prompt.sha256,
                    model,
                    chunk.sha256,
                    prev.sha256 if prev else "",
                    nxt.sha256 if nxt else "",
                ]
            ).encode()
        ).hexdigest()
        jobs.append(Job(chunk, message, key))
    return jobs


class DescriptionCache:
    """Append-only JSONL: key -> description. A rerun with the same inputs costs nothing."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.rows: dict[str, str] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self.rows[row["key"]] = row["description"]

    def put(self, key: str, chunk_id: str, description: str) -> None:
        self.rows[key] = description
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "chunk_id": chunk_id, "description": description}))
            f.write("\n")


def estimate_job(job: Job, prompt: Prompt) -> Usage:
    """Conservative: tokens by bytes/3, and the output counted at the full output cap."""
    return Usage(estimate_tokens(prompt.text + job.message), MAX_OUTPUT_TOKENS)


def describe(job: Job, provider: Provider, guard: CostGuard, prompt: Prompt) -> str | None:
    """One guarded call. Returns a validated description, or None if the output was unusable."""
    turn: ModelTurn = guard.call(
        functools.partial(
            provider.complete,
            system=prompt.text,
            messages=[UserMessage(job.message)],
            tools=[],
            schema=SCHEMA,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            allow_tools=False,
        ),
        usage_of=lambda t: t.usage,
        phase=PHASE,
        model_key=provider.model_key,
        purpose=f"p6 contextual description {job.chunk.chunk_id}",
        estimated_usage=estimate_job(job, prompt),
    )
    try:
        return validate_description(turn.text)
    except DescriptionError:
        return None


def run(
    jobs: list[Job],
    cache: DescriptionCache,
    provider: Provider,
    guard: CostGuard,
    prompt: Prompt,
    *,
    ceiling_usd: float = LIVE_CEILING_USD,
    workers: int = WORKERS,
) -> tuple[int, int]:
    """Describe every uncached job. Returns (described, unusable). Stops at the live ceiling."""
    todo = [j for j in jobs if j.key not in cache.rows]
    done = bad = 0

    def one(job: Job) -> tuple[Job, str | None, bool]:
        if float(guard.ledger.spent(phase=PHASE)) >= ceiling_usd:
            return job, None, True
        try:
            return job, describe(job, provider, guard, prompt), False
        except ProviderError:
            return job, None, False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for job, description, stopped in pool.map(one, todo):
            if stopped:
                raise RuntimeError("phase 6 live ceiling reached; stopping")
            if description is None:
                bad += 1
            else:
                cache.put(job.key, job.chunk.chunk_id, description)
                done += 1
    return done, bad


def main(argv: list[str]) -> int:
    confirm = "--confirm" in argv
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    chunks = load_chunks(CHUNKS_DIR / "chunks.jsonl")
    titles = {e.source_id: e.title for e in load_catalog(REPO_ROOT / "SOURCES/catalog.toml")}
    prompt = load_prompt(PROMPT_VERSION)
    cache = DescriptionCache(CACHE_DIR / f"contextual_{PROMPT_VERSION}_{MODEL}.jsonl")
    jobs = build_jobs(chunks, titles, prompt)
    todo = [j for j in jobs if j.key not in cache.rows]
    if limit is not None:
        todo = todo[:limit]
    guard = default_guard()
    total = Usage(0, 0)
    for j in todo:
        u = estimate_job(j, prompt)
        total = Usage(total.input_tokens + u.input_tokens, total.output_tokens + u.output_tokens)
    est = guard.cost(MODEL_KEY, total)
    print(f"prompt {prompt.version} sha256 {prompt.sha256[:12]}; model {MODEL}")
    print(f"chunks: {len(chunks)}; uncached: {len(todo)}; cached: {len(chunks) - len(todo)}")
    print(f"conservative upper-bound estimate: {total.input_tokens} in, {total.output_tokens} out")
    print(f"conservative upper-bound cost: ${est} (real cost is lower; see the pilot)")
    print(f"p6 spent so far: ${guard.ledger.spent(phase=PHASE)}; live ceiling ${LIVE_CEILING_USD}")
    if not confirm:
        print("dry run only; re-run with --confirm to spend.")
        return 0
    key = get_secret("OPENAI_API_KEY")
    if not key:
        print("refusing: OPENAI_API_KEY is empty. Set it in .env (never in chat).")
        return 2
    provider = OpenAIProvider(key, MODEL)
    try:
        target = {j.key for j in todo}
        done, bad = run([j for j in jobs if j.key in target], cache, provider, guard, prompt)
    finally:
        provider.close()
    print(f"described {done}, unusable {bad}; p6 spent: ${guard.ledger.spent(phase=PHASE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
