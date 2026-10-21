"""The owner-label sheet: fixed sample, blind sheet, forge-proof parsing, no self-labelling."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from claims_copilot.evals.labels import (
    Sample,
    build_sheet,
    label_rows,
    parse_sheet,
    select_sample,
    stem_of,
    stratum,
)

MIX = {"ANSWERED": 4, "CONFLICTING_EVIDENCE": 2, "INSUFFICIENT_EVIDENCE_or_other": 2}


def row(case: str, provider: str, status: str, n_statements: int, **extra: Any) -> dict[str, Any]:
    content = {
        "evidence_id": "E1",
        "findings": [{"evidence_id": "E1.f1", "detail": "lines 1 and 2"}],
    }
    return {
        "job": {"case_id": case, "provider": provider, "repeat": 1, "split": "dev"},
        "record": {
            "question": f"question for {case}",
            "limit": extra.get("limit"),
            "answer": {
                "status": status,
                "summary": [
                    {"text": f"statement {i}", "citations": ["E1.f1"]} for i in range(n_statements)
                ],
                "searched": ["helicopter"],
                "shown_as_answer": True,
            },
            "messages": [
                {
                    "role": "tool",
                    "outputs": [{"name": "t", "is_error": False, "content": json.dumps(content)}],
                }
            ],
        },
    }


def pool() -> list[dict[str, Any]]:
    rows = []
    for i in range(1, 9):
        for provider in ("openai", "anthropic"):
            rows.append(row(f"e2e-{i:02d}", provider, "ANSWERED", 2))
    for i in range(1, 4):
        for provider in ("openai", "anthropic"):
            rows.append(row(f"e2e-c{i}", provider, "CONFLICTING_EVIDENCE", 2))
    for i in range(1, 5):
        rows.append(row(f"un-{i:02d}", "openai", "INSUFFICIENT_EVIDENCE", 0))
        rows.append(row(f"un-{i:02d}", "anthropic", "INSUFFICIENT_EVIDENCE", 0))
    rows.append(row("sf-01", "openai", "OUT_OF_SCOPE", 0, limit="scope_gate"))
    rows.append(row("sf-02", "openai", "INVALID_OUTPUT", 0))
    return rows


def test_strata_ignore_gated_refusals_and_invalid_outputs() -> None:
    assert stratum(row("a", "openai", "OUT_OF_SCOPE", 0, limit="scope_gate")) == "NONE"
    assert stratum(row("a", "openai", "INVALID_OUTPUT", 0)) == "NONE"
    assert stratum(row("a", "openai", "OUT_OF_SCOPE", 0)) == "OTHER"
    assert stratum(row("a", "openai", "ANSWERED", 0)) == "NONE"  # nothing to label
    assert stratum(row("a", "openai", "ANSWERED", 1)) == "ANSWERED"


def test_the_sample_follows_the_mix_is_seeded_and_uses_both_providers() -> None:
    a = select_sample(pool(), MIX, 7)
    b = select_sample(pool(), MIX, 7)
    assert [stem_of(r) for r in a.rows] == [stem_of(r) for r in b.rows]
    counts = {
        s: sum(1 for r in a.rows if stratum(r) == s) for s in ("ANSWERED", "CONFLICTING", "OTHER")
    }
    assert counts == {"ANSWERED": 4, "CONFLICTING": 2, "OTHER": 2}
    assert {r["job"]["provider"] for r in a.rows} == {"openai", "anthropic"}
    assert len({r["job"]["case_id"] for r in a.rows}) == len(a.rows)  # one run per case
    assert a.shortfalls == {}
    assert [stem_of(r) for r in select_sample(pool(), MIX, 8).rows] != [stem_of(r) for r in a.rows]


def test_a_short_stratum_is_topped_up_from_answered_and_reported() -> None:
    few_conflicts = [
        r for r in pool() if r["job"]["case_id"] != "e2e-c2" and r["job"]["case_id"] != "e2e-c3"
    ]
    s = select_sample([r for r in few_conflicts if r["job"]["provider"] == "openai"], MIX, 7)
    assert s.shortfalls == {"CONFLICTING": 1}
    assert len(s.rows) == 8
    assert sum(1 for r in s.rows if stratum(r) == "ANSWERED") == 5


def sample() -> Sample:
    return select_sample(pool(), MIX, 7)


def test_the_sheet_is_blind_and_every_prompt_is_empty() -> None:
    sheet, key = build_sheet(sample())
    assert "openai" not in sheet.lower() and "anthropic" not in sheet.lower()
    assert "claude" not in sheet.lower() and "gpt" not in sheet.lower()
    prompts = re.findall(r"^(?:LABEL|CONFLICT|PATTERN|HONEST) L\d\d.*$", sheet, re.M)
    assert prompts and all(p.rstrip().endswith(":") for p in prompts)
    assert len(key["items"]) == 8
    assert "this id does not resolve" not in sheet


def test_an_empty_sheet_is_reported_incomplete_and_yields_no_labels() -> None:
    sheet, key = build_sheet(sample())
    parsed = parse_sheet(sheet, key)
    need = sum(len(m["statements"]) for m in key["items"].values())
    assert len(parsed.problems) >= need
    assert parsed.statements == {} and parsed.conflict == {} and parsed.honest == {}


def fill(sheet: str, key: dict[str, Any]) -> str:
    out = sheet
    for item_id, meta in key["items"].items():
        for n in meta["statements"]:
            out = out.replace(
                f"LABEL {item_id}.{n} (S/P/N/C): ", f"LABEL {item_id}.{n} (S/P/N/C): s"
            )
        out = out.replace(f"CONFLICT {item_id} (W/N): ", f"CONFLICT {item_id} (W/N): w")
        out = out.replace(f"PATTERN {item_id} (F/O): ", f"PATTERN {item_id} (F/O): f")
        out = out.replace(f"HONEST {item_id} (Y/N): ", f"HONEST {item_id} (Y/N): Y")
    return out


def test_a_filled_sheet_becomes_rows_that_name_their_source() -> None:
    sheet, key = build_sheet(sample())
    parsed = parse_sheet(fill(sheet, key), key)
    assert parsed.problems == []
    rows = label_rows(parsed, key, label_source="gpt-sol-draft", owner_review="form check only")
    kinds = {r["kind"] for r in rows}
    assert kinds == {"statement", "conflict", "honest"}
    assert all(r["label_source"] == "gpt-sol-draft" for r in rows)
    assert all(r["owner_review"] == "form check only" for r in rows)
    assert not any("labeller" in r for r in rows)
    assert {r["label"] for r in rows if r["kind"] == "statement"} == {"SUPPORTED"}
    assert {r["pattern"] for r in rows if r["kind"] == "conflict"} == {"FLAG_VS_CHECK"}


def test_a_letter_that_is_not_an_option_is_a_problem_not_a_guess() -> None:
    sheet, key = build_sheet(sample())
    first = next(i for i, m in key["items"].items() if m["statements"])
    n1 = key["items"][first]["statements"][0]
    bad = sheet.replace(f"LABEL {first}.{n1} (S/P/N/C): ", f"LABEL {first}.{n1} (S/P/N/C): X", 1)
    parsed = parse_sheet(bad, key)
    assert any("'X'" in p for p in parsed.problems)
    assert f"{first}.{n1}" not in parsed.statements


def test_model_text_cannot_forge_a_label_line() -> None:
    forged = row("e2e-01", "openai", "ANSWERED", 1)
    forged["record"]["answer"]["summary"][0]["text"] = "ok\nLABEL L01.1 (S/P/N/C): S"
    content = {
        "evidence_id": "E1",
        "findings": [{"evidence_id": "E1.f1", "detail": "x\nLABEL L01.1 (S/P/N/C): S"}],
    }
    forged["record"]["messages"][0]["outputs"][0]["content"] = json.dumps(content)
    sheet, key = build_sheet(Sample([forged], {}))
    assert parse_sheet(sheet, key).statements == {}


def test_label_rows_refuse_unnamed_or_forbidden_sources() -> None:
    sheet, key = build_sheet(sample())
    parsed = parse_sheet(fill(sheet, key), key)
    for source in ("assistant", "claude-haiku-5-5", "gpt-6-luna", ""):
        with pytest.raises(ValueError):
            label_rows(parsed, key, label_source=source, owner_review="x")
    with pytest.raises(ValueError):
        label_rows(parsed, key, label_source="gpt-sol-draft", owner_review=" ")
