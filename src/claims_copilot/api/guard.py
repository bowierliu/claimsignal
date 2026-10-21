"""Access control for the API: an optional API key, a per-caller rate limit, and an audit trail.

Design (docs/SECURITY.md):
- Keys are compared by SHA-256 digest with `hmac.compare_digest`, so the configured key is never
  held as plain text after startup and the comparison does not leak its length or prefix.
- A denial says only "unauthorized" or "rate limited". It never repeats the supplied key, and the
  audit entry records the fact of the denial, not the credential.
- The rate limiter is a token bucket per caller (the key's digest prefix when a key is used, else
  the client address). It is in-process: one worker, one budget. A real deployment also limits at
  the load balancer (docs/SECURITY.md).
- Every guarded request is written to the hash-chained audit log: caller, method, route template,
  and status. Never the query string, a body, or a header value.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from claims_copilot.obs.audit import AuditLog

API_KEY_HEADER = "X-API-Key"
OPEN_PATHS = frozenset({"/v1/health"})  # liveness probes carry no credentials and no data
WORKBENCH_PREFIX = "/workbench"  # static page files; every record still needs the key
MAX_CALLERS = 10_000


def key_digest(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GuardConfig:
    """`key_digests` empty means no authentication (loopback development only)."""

    key_digests: frozenset[str] = frozenset()
    requests_per_minute: int = 120
    burst: int = 30

    @classmethod
    def from_keys(cls, *keys: str, requests_per_minute: int = 120, burst: int = 30) -> GuardConfig:
        return cls(frozenset(key_digest(k) for k in keys if k), requests_per_minute, burst)


@dataclass(frozen=True)
class Denial:
    status: int
    kind: str
    title: str
    detail: str
    retry_after: int | None = None


class RateLimiter:
    """Token bucket per caller, bounded in memory (least recently seen caller is dropped)."""

    def __init__(
        self, per_minute: int, burst: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if per_minute < 1 or burst < 1:
            raise ValueError("rate limit and burst must be at least 1")
        self._rate = per_minute / 60.0
        self._burst = float(burst)
        self._clock = clock
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()

    def allow(self, caller: str) -> int | None:
        """None if the request may proceed, else the seconds to wait."""
        now = self._clock()
        tokens, seen = self._buckets.pop(caller, (self._burst, now))
        tokens = min(self._burst, tokens + (now - seen) * self._rate)
        allowed = tokens >= 1.0
        if allowed:
            tokens -= 1.0
        self._buckets[caller] = (tokens, now)
        while len(self._buckets) > MAX_CALLERS:
            self._buckets.popitem(last=False)
        return None if allowed else max(1, int((1.0 - tokens) / self._rate) + 1)


class Guard:
    def __init__(
        self,
        config: GuardConfig,
        audit: AuditLog | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._audit = audit
        self._limiter = RateLimiter(config.requests_per_minute, config.burst, clock)

    @property
    def authenticates(self) -> bool:
        return bool(self._config.key_digests)

    def is_open(self, path: str) -> bool:
        return (
            path in OPEN_PATHS
            or path == WORKBENCH_PREFIX
            or path.startswith(WORKBENCH_PREFIX + "/")
        )

    def caller(self, supplied_key: str | None, client: str | None) -> str | None:
        """An opaque caller label, or None when a key is required and this one is wrong."""
        if not self.authenticates:
            return f"anon:{client or 'unknown'}"
        if not supplied_key:
            return None
        digest = key_digest(supplied_key)
        matched = False
        for known in self._config.key_digests:  # no early exit: constant work per known key
            matched |= hmac.compare_digest(digest, known)
        return f"key:{digest[:8]}" if matched else None

    def check(self, supplied_key: str | None, client: str | None) -> tuple[str, Denial | None]:
        who = self.caller(supplied_key, client)
        if who is None:
            return "unauthenticated", Denial(
                401, "unauthorized", "Unauthorized", "A valid API key is required."
            )
        wait = self._limiter.allow(who)
        if wait is not None:
            return who, Denial(429, "rate-limited", "Rate limited", "Too many requests.", wait)
        return who, None

    def record(self, who: str, method: str, route: str, status: int, request_id: str) -> None:
        if self._audit is not None:
            self._audit.append(
                who, "api_request", route, method=method, status=status, request_id=request_id
            )
