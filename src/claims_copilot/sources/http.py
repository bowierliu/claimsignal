"""Typed, polite HTTP client for fetching public sources.

Features: descriptive user agent (CDC rejects bare browser strings), certificate verification
always on, per-host minimum interval, bounded retries with exponential backoff on transient
failures, and an on-disk response cache so repeated runs never re-download. Tests inject an
httpx.MockTransport, so they never touch the network.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

# Names the library and this project, truthfully. CDC's CDN (Akamai) returns 403 for unfamiliar
# agent strings but accepts library-identifying ones (observed 2026-10-15); we do not imitate a
# browser.
USER_AGENT = f"python-httpx/{httpx.__version__} claimsignal-research/0.1"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    status: int
    content_type: str
    content: bytes
    retrieved_at: str
    from_cache: bool

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class HttpClient:
    def __init__(
        self,
        cache_dir: Path,
        *,
        min_interval_s: float = 1.0,
        max_attempts: int = 4,
        backoff_s: float = 2.0,
        timeout_s: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], str] = _utc_now,
    ) -> None:
        self._cache_dir = cache_dir
        self._min_interval_s = min_interval_s
        self._max_attempts = max_attempts
        self._backoff_s = backoff_s
        self._sleep = sleep
        self._monotonic = monotonic
        self._now = now
        self._last_request: dict[str, float] = {}
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout_s,
            follow_redirects=True,
            transport=transport,
            verify=True,
        )

    def close(self) -> None:
        self._client.close()

    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self._cache_dir / f"{key}.body", self._cache_dir / f"{key}.json"

    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        last = self._last_request.get(host)
        if last is not None:
            wait = self._min_interval_s - (self._monotonic() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_request[host] = self._monotonic()

    def get(self, url: str, *, use_cache: bool = True) -> FetchResult:
        body_path, meta_path = self._cache_paths(url)
        if use_cache and body_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return FetchResult(
                url=url,
                final_url=meta["final_url"],
                status=meta["status"],
                content_type=meta["content_type"],
                content=body_path.read_bytes(),
                retrieved_at=meta["retrieved_at"],
                from_cache=True,
            )

        last_error = "no attempt made"
        for attempt in range(1, self._max_attempts + 1):
            self._throttle(url)
            try:
                response = self._client.get(url)
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code in RETRY_STATUSES:
                    last_error = f"HTTP {response.status_code}"
                elif response.status_code >= 400:
                    raise FetchError(f"{url}: HTTP {response.status_code}")
                else:
                    return self._store(url, response)
            if attempt < self._max_attempts:
                self._sleep(self._backoff_s * 2 ** (attempt - 1))
        raise FetchError(f"{url}: gave up after {self._max_attempts} attempts ({last_error})")

    def _store(self, url: str, response: httpx.Response) -> FetchResult:
        result = FetchResult(
            url=url,
            final_url=str(response.url),
            status=response.status_code,
            content_type=response.headers.get("content-type", ""),
            content=response.content,
            retrieved_at=self._now(),
            from_cache=False,
        )
        body_path, meta_path = self._cache_paths(url)
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_bytes(result.content)
        meta_path.write_text(
            json.dumps(
                {
                    "url": url,
                    "final_url": result.final_url,
                    "status": result.status,
                    "content_type": result.content_type,
                    "retrieved_at": result.retrieved_at,
                }
            ),
            encoding="utf-8",
        )
        return result
