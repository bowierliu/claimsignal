from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from claims_copilot.sources.http import USER_AGENT, FetchError, HttpClient

URL = "https://example.invalid/doc.pdf"


class Recorder:
    def __init__(self, statuses: list[int], body: bytes = b"hello") -> None:
        self.statuses = statuses
        self.body = body
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status = self.statuses[min(len(self.requests) - 1, len(self.statuses) - 1)]
        return httpx.Response(status, content=self.body, headers={"content-type": "text/plain"})


def make_client(
    tmp_path: Path, handler: Recorder, sleeps: list[float], clock: list[float] | None = None
) -> HttpClient:
    ticks = clock if clock is not None else [0.0]
    return HttpClient(
        tmp_path,
        min_interval_s=1.0,
        max_attempts=3,
        backoff_s=2.0,
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        monotonic=lambda: ticks[0],
        now=lambda: "2026-10-15T00:00:00+00:00",
    )


def test_sends_descriptive_user_agent_and_hashes_content(tmp_path: Path) -> None:
    handler = Recorder([200])
    client = make_client(tmp_path, handler, [])
    result = client.get(URL)
    assert handler.requests[0].headers["user-agent"] == USER_AGENT
    assert result.status == 200
    assert result.content == b"hello"
    assert result.sha256 == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert not result.from_cache


def test_second_get_is_served_from_cache_without_network(tmp_path: Path) -> None:
    handler = Recorder([200])
    client = make_client(tmp_path, handler, [])
    first = client.get(URL)
    second = client.get(URL)
    assert len(handler.requests) == 1
    assert second.from_cache
    assert second.content == first.content
    assert second.retrieved_at == first.retrieved_at == "2026-10-15T00:00:00+00:00"


def test_retries_transient_errors_with_exponential_backoff(tmp_path: Path) -> None:
    handler = Recorder([503, 429, 200])
    sleeps: list[float] = []
    result = make_client(tmp_path, handler, sleeps).get(URL)
    assert result.status == 200
    assert len(handler.requests) == 3
    assert [s for s in sleeps if s >= 2.0] == [2.0, 4.0]


def test_gives_up_after_max_attempts(tmp_path: Path) -> None:
    handler = Recorder([503])
    with pytest.raises(FetchError, match="gave up after 3 attempts"):
        make_client(tmp_path, handler, []).get(URL)
    assert len(handler.requests) == 3


def test_client_errors_are_not_retried_or_cached(tmp_path: Path) -> None:
    handler = Recorder([404])
    client = make_client(tmp_path, handler, [])
    with pytest.raises(FetchError, match="HTTP 404"):
        client.get(URL)
    assert len(handler.requests) == 1
    assert list(tmp_path.iterdir()) == []


def test_requests_to_one_host_are_spaced_by_min_interval(tmp_path: Path) -> None:
    handler = Recorder([200])
    sleeps: list[float] = []
    client = make_client(tmp_path, handler, sleeps, clock=[10.0])
    client.get("https://example.invalid/a")
    client.get("https://example.invalid/b")
    assert sleeps == [1.0]
    client.get("https://other.invalid/c")
    assert sleeps == [1.0]
