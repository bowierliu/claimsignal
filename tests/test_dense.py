from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import numpy as np
import pytest

from claims_copilot.budget import CostGuard, Ledger, load_caps, load_prices
from claims_copilot.ingest.chunk import Chunk
from claims_copilot.project import BUDGET_DIR
from claims_copilot.retrieval.dense import (
    BATCH_SIZE,
    DenseIndex,
    DenseSearcher,
    GuardedEmbedder,
    build_index,
    normalize_rows,
    pending_chunks,
)
from claims_copilot.retrieval.embed import EmbeddingBatch, EmbeddingError, OpenAIEmbedder
from claims_copilot.secrets import get_secret, has_secret

SECRET = "sk-test-not-a-real-key"  # noqa: S105 - dummy value used to prove it never leaks


def ok_response(request: httpx.Request, dims: int = 3) -> httpx.Response:
    texts = json.loads(request.content)["input"]
    # Return out of order to prove the client sorts by `index`.
    data = [
        {"object": "embedding", "index": i, "embedding": [float(i + 1)] + [0.0] * (dims - 1)}
        for i in reversed(range(len(texts)))
    ]
    usage = {"prompt_tokens": 10 * len(texts), "total_tokens": 10 * len(texts)}
    return httpx.Response(200, json={"object": "list", "data": data, "usage": usage})


def embedder(handler: httpx.MockTransport, **kw: object) -> OpenAIEmbedder:
    return OpenAIEmbedder(SECRET, transport=handler, sleep=lambda s: None, **kw)  # type: ignore[arg-type]


def test_request_shape_and_ordering() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok_response(request)

    batch = embedder(httpx.MockTransport(handler)).embed(["a", "b"])
    request = seen[0]
    assert str(request.url) == "https://api.openai.com/v1/embeddings"
    assert request.headers["authorization"] == f"Bearer {SECRET}"
    assert json.loads(request.content) == {"model": "text-embedding-3-small", "input": ["a", "b"]}
    assert [v[0] for v in batch.vectors] == [1.0, 2.0]
    assert batch.prompt_tokens == 20


def test_retries_on_429_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429) if calls["n"] < 3 else ok_response(request)

    assert len(embedder(httpx.MockTransport(handler)).embed(["a"]).vectors) == 1
    assert calls["n"] == 3


def test_gives_up_after_max_attempts() -> None:
    handler = httpx.MockTransport(lambda r: httpx.Response(503))
    with pytest.raises(EmbeddingError, match="gave up after 4 attempts"):
        embedder(handler).embed(["a"])


def test_auth_error_does_not_retry_or_leak_body() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": {"message": f"Incorrect API key: {SECRET}"}})

    with pytest.raises(EmbeddingError) as info:
        embedder(httpx.MockTransport(handler)).embed(["a"])
    assert calls["n"] == 1
    assert SECRET not in str(info.value)
    assert "401" in str(info.value)


def test_rejects_wrong_count_and_bad_shape() -> None:
    def short(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [{"index": 0, "embedding": [1.0]}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    with pytest.raises(EmbeddingError, match="expected 2"):
        embedder(httpx.MockTransport(short)).embed(["a", "b"])
    with pytest.raises(EmbeddingError, match="shape"):
        embedder(httpx.MockTransport(lambda r: httpx.Response(200, json={}))).embed(["a"])


def test_empty_key_is_refused() -> None:
    with pytest.raises(EmbeddingError):
        OpenAIEmbedder("")


class FakeEmbedder:
    """Deterministic embedder: vector is a function of the text, tracks calls."""

    model = "fake"

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        self.batches.append(texts)
        vectors = [[float(len(t)), float(t.count("a")), 1.0] for t in texts]
        # Large fake usage so the cost is visible at the ledger's $0.000001 precision.
        return EmbeddingBatch(vectors, prompt_tokens=50_000 * len(texts))


def real_guard(tmp_path: Path) -> CostGuard:
    return CostGuard(
        load_caps(BUDGET_DIR / "caps.toml"),
        load_prices(BUDGET_DIR / "prices.toml"),
        Ledger(tmp_path / "ledger.jsonl"),
    )


def make_chunk(cid: str, text: str, sha: str | None = None) -> Chunk:
    return Chunk(cid, cid.split(":")[0], 1, 1, "", text, sha or f"sha-{text}")


def test_guarded_embedder_ledgers_every_batch(tmp_path: Path) -> None:
    guard = real_guard(tmp_path)
    fake = FakeEmbedder()
    vectors = GuardedEmbedder(fake, guard).embed(["t"] * (BATCH_SIZE + 1), purpose="test")
    assert len(fake.batches) == 2
    assert vectors.shape == (BATCH_SIZE + 1, 3)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-6)
    entries = guard.ledger.entries()
    assert len(entries) == 2
    assert guard.ledger.spent(phase="p0") > Decimal(0)


def test_build_index_is_incremental(tmp_path: Path) -> None:
    guard = real_guard(tmp_path)
    fake = FakeEmbedder()
    emb = GuardedEmbedder(fake, guard)
    chunks = [make_chunk("a:1-1:0", "alpha"), make_chunk("b:1-1:0", "beta")]
    index = build_index(chunks, None, emb)
    assert index.ids == ["a:1-1:0", "b:1-1:0"]

    path = tmp_path / "idx.npz"
    index.save(path)
    loaded = DenseIndex.load(path)
    assert loaded is not None and loaded.ids == index.ids
    assert np.allclose(loaded.vectors, index.vectors)

    # Unchanged corpus: nothing to embed. Changed + new chunk: only those are embedded.
    assert pending_chunks(chunks, loaded) == []
    changed = [
        make_chunk("a:1-1:0", "alpha"),
        make_chunk("b:1-1:0", "beta v2"),
        make_chunk("c:1-1:0", "c"),
    ]
    assert [c.chunk_id for c in pending_chunks(changed, loaded)] == ["b:1-1:0", "c:1-1:0"]
    fake.batches.clear()
    updated = build_index(changed, loaded, emb)
    assert fake.batches == [["beta v2", "c"]]
    assert updated.ids == ["a:1-1:0", "b:1-1:0", "c:1-1:0"]


def test_load_missing_index_returns_none(tmp_path: Path) -> None:
    assert DenseIndex.load(tmp_path / "nope.npz") is None


def test_searcher_ranks_by_cosine_and_caches_queries(tmp_path: Path) -> None:
    vectors = normalize_rows(np.array([[1, 0, 0], [0, 1, 0], [0.9, 0.1, 0]], dtype=np.float32))
    index = DenseIndex(["x", "y", "z"], ["h"] * 3, vectors, "fake")

    class QueryEmbedder:
        model = "fake"
        calls = 0

        def embed(self, texts: list[str]) -> EmbeddingBatch:
            QueryEmbedder.calls += 1
            return EmbeddingBatch([[1.0, 0.0, 0.0]] * len(texts), 1)

    searcher = DenseSearcher(
        index, GuardedEmbedder(QueryEmbedder(), real_guard(tmp_path)), tmp_path / "q.json"
    )
    assert [h.chunk_id for h in searcher.search("question", 2)] == ["x", "z"]
    searcher.search("question", 2)
    assert QueryEmbedder.calls == 1
    # A fresh searcher reads the cache from disk instead of paying again.
    again = DenseSearcher(
        index, GuardedEmbedder(QueryEmbedder(), real_guard(tmp_path)), tmp_path / "q.json"
    )
    again.search("question", 1)
    assert QueryEmbedder.calls == 1


def test_secret_loader_reads_env_file_and_ignores_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MY_TEST_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("# comment\nMY_TEST_KEY=\nOTHER='quoted'\n")
    assert not has_secret("MY_TEST_KEY", env)
    assert get_secret("OTHER", env) == "quoted"
    env.write_text("MY_TEST_KEY=abc123\n")
    assert get_secret("MY_TEST_KEY", env) == "abc123"
    monkeypatch.setenv("MY_TEST_KEY", "from-env")
    assert get_secret("MY_TEST_KEY", env) == "from-env"
    assert get_secret("MISSING", tmp_path / "absent.env") is None
