"""Shared POST-with-retries for provider adapters.

Errors carry an HTTP status or an exception class name only. Response bodies and request headers
are never put in messages: auth failures can echo part of a key.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from claims_copilot.agent.types import ProviderError

RETRY_STATUSES = frozenset({408, 409, 429})


def should_retry(status: int) -> bool:
    return status in RETRY_STATUSES or status >= 500


def post_json(
    client: httpx.Client,
    url: str,
    body: dict[str, Any],
    *,
    what: str,
    max_attempts: int = 3,
    backoff_s: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    last = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.post(url, json=body)
        except httpx.TransportError as exc:
            last = type(exc).__name__
        else:
            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError:
                    raise ProviderError(f"{what}: response was not JSON") from None
                if not isinstance(payload, dict):
                    raise ProviderError(f"{what}: unexpected response shape")
                return payload
            if not should_retry(response.status_code):
                raise ProviderError(f"{what} failed: HTTP {response.status_code}")
            last = f"HTTP {response.status_code}"
        if attempt < max_attempts:
            sleep(backoff_s * 2 ** (attempt - 1))
    raise ProviderError(f"{what} gave up after {max_attempts} attempts ({last})")
