"""The audit log is append-only and hash-chained: any edit, deletion, or reorder is detected."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claims_copilot.obs.audit import GENESIS, AuditLog, main

FAKE_KEY = "sk-" + "q1w2e3r4t5" * 3


def log(tmp_path: Path) -> AuditLog:
    return AuditLog(tmp_path / "audit.jsonl", now=lambda: "2026-01-01T00:00:00+00:00")


def filled(tmp_path: Path, n: int = 4) -> AuditLog:
    a = log(tmp_path)
    for i in range(n):
        a.append("key:abcd1234", "api_request", f"/v1/claims/{i}", status=200)
    return a


def rewrite(path: Path, entries: list[dict[str, object]]) -> None:
    text = "".join(json.dumps(e, sort_keys=True) + "\n" for e in entries)
    path.write_text(text, encoding="utf-8")


def test_entries_are_numbered_and_chained(tmp_path: Path) -> None:
    entries = filled(tmp_path).read()
    assert [e["seq"] for e in entries] == [1, 2, 3, 4]
    assert entries[0]["prev_hash"] == GENESIS
    assert all(entries[i]["prev_hash"] == entries[i - 1]["hash"] for i in range(1, 4))
    assert log(tmp_path).verify().ok


def test_an_empty_or_missing_log_verifies(tmp_path: Path) -> None:
    result = log(tmp_path).verify()
    assert result.ok and result.entries == 0


def test_editing_an_entry_is_detected_at_that_entry(tmp_path: Path) -> None:
    a = filled(tmp_path)
    entries = a.read()
    entries[1]["details"] = {"status": 204}
    rewrite(tmp_path / "audit.jsonl", entries)
    result = a.verify()
    assert not result.ok and result.first_bad_seq == 2 and "changed" in result.reason


def test_deleting_an_entry_is_detected(tmp_path: Path) -> None:
    a = filled(tmp_path)
    entries = a.read()
    del entries[1]
    rewrite(tmp_path / "audit.jsonl", entries)
    result = a.verify()
    assert not result.ok and result.first_bad_seq == 2


def test_reordering_entries_is_detected(tmp_path: Path) -> None:
    a = filled(tmp_path)
    entries = a.read()
    entries[1], entries[2] = entries[2], entries[1]
    rewrite(tmp_path / "audit.jsonl", entries)
    assert not a.verify().ok


def test_a_forged_link_is_detected(tmp_path: Path) -> None:
    a = filled(tmp_path)
    entries = a.read()
    entries[3]["prev_hash"] = "f" * 64
    rewrite(tmp_path / "audit.jsonl", entries)
    result = a.verify()
    assert not result.ok and result.first_bad_seq == 4


def test_a_garbled_line_is_reported_and_blocks_appending(tmp_path: Path) -> None:
    a = filled(tmp_path, 2)
    with (tmp_path / "audit.jsonl").open("a", encoding="utf-8") as f:
        f.write("not json\n")
    assert not a.verify().ok
    with pytest.raises(ValueError):
        a.append("x", "y")


def test_details_hold_no_payload_and_no_secret(tmp_path: Path) -> None:
    a = log(tmp_path)
    entry = a.append(
        f"actor {FAKE_KEY}", "ask", "C0000001", question="Is it fraud?", note=f"saw {FAKE_KEY}"
    )
    text = json.dumps(entry)
    assert FAKE_KEY not in text and "Is it fraud" not in text


def test_the_command_line_reports_the_chain(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    filled(tmp_path, 2)
    assert main(["--path", str(tmp_path / "audit.jsonl")]) == 0
    assert "chain ok: True" in capsys.readouterr().out
    entries = log(tmp_path).read()
    entries[0]["actor"] = "someone-else"
    rewrite(tmp_path / "audit.jsonl", entries)
    assert main(["--path", str(tmp_path / "audit.jsonl")]) == 1
