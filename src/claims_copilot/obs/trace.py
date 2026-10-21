"""A small structured tracer: nested spans written as JSON lines, with metadata and no payloads.

Policy (tested):
- A span records ids, names, timing, status, counts, sizes, model and tool names, and hashes. It
  never records a question, a prompt, a model's text, a tool's output, or a request body: keys that
  carry payload are replaced by an omission marker, and every string value is scrubbed with
  `redact` and cut short.
- A trace never changes behaviour. A failure to write is swallowed and counted; the run goes on.
- Spans are written when they end, so a crash loses only the open spans.

This is deliberately a plain file format (one JSON object per line) so it can be read with `jq`
and shipped to any collector. `OTEL_COMPATIBLE_FIELDS` documents the mapping.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from claims_copilot.obs.redact import redact
from claims_copilot.project import REPO_ROOT

TRACE_DIR = REPO_ROOT / "data" / "traces"
MAX_VALUE_CHARS = 200
OMITTED = "[omitted: payload key]"
# Keys that would carry a payload. Matched on the whole key and on any "_"-separated word.
PAYLOAD_WORDS = frozenset(
    {
        "question",
        "prompt",
        "text",
        "content",
        "body",
        "answer",
        "summary",
        "quote",
        "message",
        "messages",
        "output",
        "arguments",
        "authorization",
        "header",
        "headers",
        "cookie",
        "secret",
        "password",
        "key",
        "token",
    }
)
OTEL_COMPATIBLE_FIELDS = {
    "trace_id": "trace_id",
    "span_id": "span_id",
    "parent_id": "parent_span_id",
    "name": "name",
    "start": "start_time",
    "duration_ms": "end_time - start_time",
    "status": "status.code",
    "attrs": "attributes",
}

_current: contextvars.ContextVar[Span | None] = contextvars.ContextVar("span", default=None)


# A payload word is allowed when the key says it is a size, a count, a hash, or a version.
SAFE_SUFFIXES = ("_sha256", "_len", "_count", "_chars", "_version", "_tokens", "_usd", "_id")


def _is_payload_key(key: str) -> bool:
    words = set(key.lower().split("_"))
    return bool(words & PAYLOAD_WORDS) and not key.endswith(SAFE_SUFFIXES)


def clean_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    """Scrub attribute values and drop payload keys. Only scalars survive."""
    out: dict[str, Any] = {}
    for key, value in attrs.items():
        if _is_payload_key(key):
            out[key] = OMITTED
        elif isinstance(value, bool | int | float) or value is None:
            out[key] = value
        else:
            out[key] = redact(str(value))[:MAX_VALUE_CHARS]
    return out


class Span:
    def __init__(self, trace_id: str, parent_id: str | None, name: str, attrs: dict[str, Any]):
        self.trace_id = trace_id
        self.span_id = uuid.uuid4().hex[:16]
        self.parent_id = parent_id
        self.name = name
        self.attrs = dict(attrs)
        self.status = "ok"

    def set(self, **attrs: Any) -> None:
        self.attrs.update(attrs)


class Tracer:
    """Writes one JSON line per finished span to `sink` (or keeps them in memory when None)."""

    def __init__(
        self,
        sink: Path | None = None,
        *,
        now: Callable[[], str] | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._sink = sink
        self._now = now or (lambda: datetime.now(UTC).isoformat(timespec="milliseconds"))
        self._clock = clock
        self._lock = threading.Lock()
        self.spans: list[dict[str, Any]] = []
        self.write_failures = 0

    @contextlib.contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[Span]:
        parent = _current.get()
        trace_id = parent.trace_id if parent else uuid.uuid4().hex
        span = Span(trace_id, parent.span_id if parent else None, name, attrs)
        token = _current.set(span)
        start, t0 = self._now(), self._clock()
        try:
            yield span
        except BaseException as exc:
            span.status = "error"
            span.attrs["error_type"] = type(exc).__name__  # the class only, never the message
            raise
        finally:
            _current.reset(token)
            self._emit(span, start, (self._clock() - t0) * 1000)

    def _emit(self, span: Span, start: str, duration_ms: float) -> None:
        record = {
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "parent_id": span.parent_id,
            "name": span.name,
            "start": start,
            "duration_ms": round(duration_ms, 3),
            "status": span.status,
            "attrs": clean_attrs(span.attrs),
        }
        with self._lock:
            self.spans.append(record)
            if self._sink is None:
                return
            try:
                self._sink.parent.mkdir(parents=True, exist_ok=True)
                with self._sink.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, sort_keys=True) + "\n")
            except OSError:
                self.write_failures += 1


class NullTracer(Tracer):
    """Does nothing. The default, so tracing is opt-in and costs nothing when off."""

    @contextlib.contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[Span]:
        yield Span("0" * 32, None, name, {})


def default_sink(day: str | None = None) -> Path:
    return TRACE_DIR / f"{day or datetime.now(UTC).date().isoformat()}.jsonl"
