"""Typed client for the OpenAI embeddings endpoint (POST /v1/embeddings).

Request/response shape checked against the OpenAI OpenAPI spec (CreateEmbeddingRequest /
CreateEmbeddingResponse). This client does no budgeting itself: callers must go through
CostGuard (see retrieval.dense.GuardedEmbedder). Error messages never include response bodies for
auth failures, since those can echo part of the key.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.openai.com/v1"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class EmbeddingError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    prompt_tokens: int


class OpenAIEmbedder:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "text-embedding-3-small",
        base_url: str = DEFAULT_BASE_URL,
        transport: httpx.BaseTransport | None = None,
        max_attempts: int = 4,
        backoff_s: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        timeout_s: float = 60.0,
    ) -> None:
        if not api_key:
            raise EmbeddingError("OPENAI_API_KEY is not set")
        self.model = model
        self._url = f"{base_url}/embeddings"
        self._max_attempts = max_attempts
        self._backoff_s = backoff_s
        self._sleep = sleep
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout_s,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        if not texts:
            return EmbeddingBatch([], 0)
        body: dict[str, Any] = {"model": self.model, "input": texts}
        last = "no attempt made"
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.post(self._url, json=body)
            except httpx.TransportError as exc:
                last = type(exc).__name__
            else:
                if response.status_code == 200:
                    return self._parse(response, len(texts))
                if response.status_code not in RETRY_STATUSES:
                    raise EmbeddingError(f"embeddings request failed: HTTP {response.status_code}")
                last = f"HTTP {response.status_code}"
            if attempt < self._max_attempts:
                self._sleep(self._backoff_s * 2 ** (attempt - 1))
        raise EmbeddingError(
            f"embeddings request gave up after {self._max_attempts} attempts ({last})"
        )

    @staticmethod
    def _parse(response: httpx.Response, expected: int) -> EmbeddingBatch:
        try:
            payload = response.json()
            items = sorted(payload["data"], key=lambda d: d["index"])
            vectors = [[float(x) for x in item["embedding"]] for item in items]
            tokens = int(payload["usage"]["prompt_tokens"])
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError(
                f"unexpected embeddings response shape: {type(exc).__name__}"
            ) from exc
        if len(vectors) != expected or [i["index"] for i in items] != list(range(expected)):
            raise EmbeddingError(f"expected {expected} embeddings, got {len(vectors)}")
        if len({len(v) for v in vectors}) != 1:
            raise EmbeddingError("embeddings have inconsistent dimensions")
        return EmbeddingBatch(vectors, tokens)
