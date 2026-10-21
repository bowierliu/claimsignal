"""Spans carry metadata only: payload keys are omitted, values scrubbed, failures never leak."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claims_copilot.obs.trace import OMITTED, NullTracer, Tracer, clean_attrs

FAKE_KEY = "sk-" + "z9y8x7w6v5" * 3


def tracer(sink: Path | None = None) -> Tracer:
    ticks = iter(float(i) for i in range(100))
    return Tracer(sink, now=lambda: "2026-01-01T00:00:00.000+00:00", clock=lambda: next(ticks))


def test_nested_spans_share_a_trace_and_link_to_their_parent() -> None:
    t = tracer()
    with t.span("outer"), t.span("inner"):
        pass
    inner, outer = t.spans  # spans are written when they end: inner first
    assert inner["trace_id"] == outer["trace_id"]
    assert inner["parent_id"] == outer["span_id"] and outer["parent_id"] is None


def test_payload_keys_are_omitted_but_sizes_hashes_and_versions_are_kept() -> None:
    out = clean_attrs(
        {
            "question": "Is claim C0000001 fraud?",
            "prompt": "system text",
            "answer": "...",
            "api_key": "x",
            "question_len": 24,
            "prompt_sha256": "ab" * 32,
            "prompt_version": "v3",
            "model": "claude-haiku-5-5",
        }
    )
    assert out["question"] == out["prompt"] == out["answer"] == out["api_key"] == OMITTED
    assert out["question_len"] == 24 and out["prompt_version"] == "v3"
    assert out["model"] == "claude-haiku-5-5" and out["prompt_sha256"] == "ab" * 32


def test_string_values_are_scrubbed_and_cut_short() -> None:
    out = clean_attrs({"note": f"saw {FAKE_KEY} here " + "x" * 500})
    assert FAKE_KEY not in out["note"] and len(out["note"]) <= 200


def test_an_exception_marks_the_span_and_records_only_the_class() -> None:
    t = tracer()
    with pytest.raises(ValueError), t.span("work"):
        raise ValueError(f"secret detail {FAKE_KEY}")
    span = t.spans[0]
    assert span["status"] == "error" and span["attrs"]["error_type"] == "ValueError"
    assert FAKE_KEY not in json.dumps(span)


def test_spans_are_written_as_json_lines(tmp_path: Path) -> None:
    sink = tmp_path / "t" / "trace.jsonl"
    t = tracer(sink)
    with t.span("a", claim_id="C0000001"):
        pass
    lines = sink.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["attrs"] == {"claim_id": "C0000001"}


def test_a_write_failure_is_counted_and_does_not_stop_the_run(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    t = tracer(blocker / "sub" / "trace.jsonl")  # parent is a file: cannot be created
    with t.span("a"):
        result = 1 + 1
    assert result == 2 and t.write_failures == 1 and len(t.spans) == 1


def test_the_null_tracer_records_nothing() -> None:
    t = NullTracer()
    with t.span("a", question="q") as span:
        span.set(x=1)
    assert t.spans == []
