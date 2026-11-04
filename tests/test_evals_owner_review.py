"""The owner re-review sheet: deterministic selection, blind full-text sheet, guarded merge."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from claims_copilot.evals.labels import Parsed, parse_sheet
from claims_copilot.evals.owner_review import (
    MergeReport,
    ReviewItem,
    build_review_sheet,
    merge_labels,
    select_review_items,
)

LONG = "z" * 1000  # a source longer than the 900-character display cut


def record(case: str, status: str, statements: list[tuple[str, list[str]]]) -> dict[str, Any]:
    """A minimal run record: one tool output carrying E1 and E1.f1, so citations resolve."""
    content = {"evidence_id": "E1", "findings": [{"evidence_id": "E1.f1", "detail": LONG}]}
    return {
        "question": f"question for {case}",
        "answer": {
            "status": status,
            "summary": [{"text": t, "citations": c} for t, c in statements],
            "searched": ["helicopter"],
            "shown_as_answer": True,
        },
        "messages": [
            {
                "role": "tool",
                "outputs": [{"name": "t", "is_error": False, "content": json.dumps(content)}],
            }
        ],
    }


def records() -> dict[str, dict[str, Any]]:
    return {
        "case-a__openai__r1": record(
            "case-a",
            "ANSWERED",
            [("case-a statement one", ["E1.f1"]), ("case-a statement two", ["E1"])],
        ),
        "case-b__anthropic__r2": record(
            "case-b", "ANSWERED", [("case-b statement one", ["E1.f1"])]
        ),
        "case-c__openai__r1": record(
            "case-c", "CONFLICTING_EVIDENCE", [("case-c statement one", ["E1.f1"])]
        ),
        "case-d__anthropic__r1": record(
            "case-d", "CONFLICTING_EVIDENCE", [("case-d statement one", ["E1.f1"])]
        ),
        "case-f__openai__r1": record("case-f", "ANSWERED", [("case-f statement one", ["E1"])]),
    }


def lrow(
    item: str,
    kind: str,
    run_file: str,
    label: str,
    *,
    n: int | None = None,
    pattern: str | None = None,
    stratum: str = "ANSWERED",
    source: str = "gpt-sol-draft",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "item": item,
        "kind": kind,
        "label": label,
        "label_source": source,
        "owner_review": "form check only",
        "run_file": run_file,
        "stratum": stratum,
    }
    if n is not None:
        row["n"] = n
        row["of"] = 2
    if pattern is not None:
        row["pattern"] = pattern
    return row


def labels() -> list[dict[str, Any]]:
    return [
        lrow("L01", "statement", "case-a__openai__r1", "SUPPORTED", n=1),
        lrow("L01", "statement", "case-a__openai__r1", "CANNOT_TELL", n=2),
        lrow("L02", "statement", "case-b__anthropic__r2", "PARTLY", n=1),
        lrow(
            "L03",
            "statement",
            "case-c__openai__r1",
            "CANNOT_TELL",
            n=1,
            stratum="CONFLICTING",
        ),
        lrow(
            "L03",
            "conflict",
            "case-c__openai__r1",
            "WARRANTED",
            pattern="FLAG_VS_CHECK",
            stratum="CONFLICTING",
        ),
        lrow(
            "L04",
            "statement",
            "case-d__anthropic__r1",
            "SUPPORTED",
            n=1,
            stratum="CONFLICTING",
        ),
        lrow(
            "L04",
            "conflict",
            "case-d__anthropic__r1",
            "NOT_WARRANTED",
            pattern="OTHER",
            stratum="CONFLICTING",
        ),
        lrow("L05", "honest", "case-e__openai__r3", "HONEST", stratum="OTHER"),
        lrow("L06", "statement", "case-f__openai__r1", "PARTLY", n=1),
    ]


def judgments() -> dict[str, dict[str, Any]]:
    return {
        "case-a__openai__r1": {"labels": {"1": "SUPPORTED", "2": "SUPPORTED"}},
        "case-b__anthropic__r2": {"labels": {"1": "SUPPORTED"}},
        "case-c__openai__r1": {"labels": {"1": "CANNOT_TELL"}, "conflict_label": "WARRANTED"},
        "case-d__anthropic__r1": {"labels": {"1": "SUPPORTED"}, "conflict_label": "NOT_WARRANTED"},
        "case-f__openai__r1": {"labels": {"1": "PARTLY"}},
    }


def selected() -> list[ReviewItem]:
    return select_review_items(labels(), judgments())


def built() -> tuple[str, dict[str, Any]]:
    return build_review_sheet(selected(), labels(), judgments(), records())


def test_selection_picks_cannot_tell_false_supported_and_conflicts_only() -> None:
    items = {i.item: i for i in selected()}
    assert sorted(items) == ["L01", "L02", "L03", "L04"]
    assert items["L01"].statements == {2: ("cannot_tell", "false_supported")}
    assert items["L02"].statements == {1: ("false_supported",)}
    assert items["L03"].statements == {1: ("cannot_tell",)}
    assert items["L04"].statements == {}
    assert not items["L01"].conflict and not items["L02"].conflict
    assert items["L03"].conflict and items["L04"].conflict
    # L01.1 (S|S), L06.1 (P|P) and the honest row are not under review.


def test_selection_refuses_an_item_outside_the_reviewable_strata() -> None:
    bad = [lrow("L09", "statement", "case-e__openai__r3", "CANNOT_TELL", n=1, stratum="OTHER")]
    with pytest.raises(ValueError, match="strata"):
        select_review_items(bad, {})


def test_the_sheet_is_blind_shows_full_text_and_prompts_only_reviewed_statements() -> None:
    sheet, key = built()
    assert LONG in sheet and "more characters not shown" not in sheet
    for name in ("openai", "anthropic", "claude", "gpt"):
        assert name not in sheet.lower()
    prompts = re.findall(r"^(?:LABEL|CONFLICT|PATTERN) L\d\d.*$", sheet, re.M)
    assert prompts and all(p.rstrip().endswith(":") for p in prompts)
    assert "LABEL L01.2" in sheet
    # a non-conflict item shows only its reviewed statements (a statement is judged on its own
    # sources); a conflict item also shows the answer's other labelled statements as context.
    assert "case-a statement one" not in sheet and "case-a statement two" in sheet
    assert "case-d statement one" in sheet and "LABEL L04.1" not in sheet
    assert "LABEL L02.1" in sheet and "LABEL L03.1" in sheet
    assert "CONFLICT L03 (W/N):" in sheet and "PATTERN L04 (F/O):" in sheet
    json.dumps(key)  # the audit key must stay serialisable
    assert key["items"]["L01"]["reasons"] == {"2": ["cannot_tell", "false_supported"]}
    assert key["selection_counts"] == {"cannot_tell": 2, "false_supported": 2, "conflict": 2}


def test_a_missing_record_or_statement_is_an_error_not_a_gap() -> None:
    with pytest.raises(ValueError, match="no recorded run"):
        build_review_sheet(selected(), labels(), judgments(), {})
    items = selected()
    broken = records()
    broken["case-a__openai__r1"]["answer"]["summary"] = [{"text": "only one", "citations": ["E1"]}]
    with pytest.raises(ValueError, match="no statement 2"):
        build_review_sheet(items, labels(), judgments(), broken)


def fill(sheet: str, key: dict[str, Any], letter: str = "S") -> str:
    out = sheet
    for item_id, meta in key["items"].items():
        for n in meta["statements"]:
            out = out.replace(
                f"LABEL {item_id}.{n} (S/P/N/C): ", f"LABEL {item_id}.{n} (S/P/N/C): {letter}"
            )
        if meta["conflict"]:
            out = out.replace(f"CONFLICT {item_id} (W/N): ", f"CONFLICT {item_id} (W/N): W")
            out = out.replace(f"PATTERN {item_id} (F/O): ", f"PATTERN {item_id} (F/O): F")
    return out


def merged(letter: str = "S") -> tuple[list[dict[str, Any]], MergeReport]:
    sheet, key = built()
    parsed = parse_sheet(fill(sheet, key, letter), key)
    assert parsed.problems == []
    return merge_labels(labels(), parsed, key, owner_review="owner labelled the review sheet")


def test_an_empty_sheet_is_reported_incomplete() -> None:
    sheet, key = built()
    parsed = parse_sheet(sheet, key)
    assert len(parsed.problems) == 3 + 2 * 2  # 3 statements, 2 x (CONFLICT + PATTERN)


def test_merge_replaces_only_reviewed_rows_and_stamps_provenance() -> None:
    out, report = merged()
    by_kind = {(r["kind"], r["run_file"], r.get("n")): r for r in out}
    reviewed = [
        ("statement", "case-a__openai__r1", 2),
        ("statement", "case-b__anthropic__r2", 1),
        ("statement", "case-c__openai__r1", 1),
        ("conflict", "case-c__openai__r1", None),
        ("conflict", "case-d__anthropic__r1", None),
    ]
    assert report.replaced == 5
    for k in reviewed:
        row = by_kind[k]
        assert row["label_source"] == "owner-hand"
        assert row["owner_review"] == "owner labelled the review sheet"
    untouched = [
        ("statement", "case-a__openai__r1", 1),
        ("statement", "case-d__anthropic__r1", 1),
        ("statement", "case-f__openai__r1", 1),
        ("honest", "case-e__openai__r3", None),
    ]
    before = {(r["kind"], r["run_file"], r.get("n")): r for r in labels()}
    for k in untouched:
        assert by_kind[k] == before[k]
        assert json.dumps(by_kind[k], sort_keys=True) == json.dumps(before[k], sort_keys=True)
    assert set(report.changed) == {
        "L01 statement: CANNOT_TELL -> SUPPORTED",
        "L02 statement: PARTLY -> SUPPORTED",
        "L03 statement: CANNOT_TELL -> SUPPORTED",
        "L04 conflict: NOT_WARRANTED, OTHER -> WARRANTED, FLAG_VS_CHECK",
    }


def test_merge_reports_agreement_when_the_owner_confirms_the_draft() -> None:
    sheet, key = built()
    out_sheet = sheet
    for item_id, meta in key["items"].items():
        draft = meta["draft"]
        for n in meta["statements"]:
            letter = {"CANNOT_TELL": "C", "PARTLY": "P"}[draft["statements"][n]]
            out_sheet = out_sheet.replace(
                f"LABEL {item_id}.{n} (S/P/N/C): ", f"LABEL {item_id}.{n} (S/P/N/C): {letter}"
            )
        if meta["conflict"]:
            w = "W" if draft["conflict"] == "WARRANTED" else "N"
            f = "F" if draft["pattern"] == "FLAG_VS_CHECK" else "O"
            out_sheet = out_sheet.replace(
                f"CONFLICT {item_id} (W/N): ", f"CONFLICT {item_id} (W/N): {w}"
            )
            out_sheet = out_sheet.replace(
                f"PATTERN {item_id} (F/O): ", f"PATTERN {item_id} (F/O): {f}"
            )
    parsed = parse_sheet(out_sheet, key)
    assert parsed.problems == []
    _, report = merge_labels(labels(), parsed, key, owner_review="owner labelled the review sheet")
    assert report.replaced == 5 and report.changed == ()


def test_merge_refuses_a_second_ingest_a_missing_row_and_a_blank_review() -> None:
    out, _ = merged()
    sheet, key = built()
    parsed = parse_sheet(fill(sheet, key), key)
    with pytest.raises(ValueError, match="already owner-hand"):
        merge_labels(out, parsed, key, owner_review="again")
    broken_key = json.loads(json.dumps(key))
    broken_key["items"]["L06"] = {
        "run_file": "case-f__openai__r1",
        "stratum": "ANSWERED",
        "statements": [9],
        "conflict": False,
    }
    parsed_extra = Parsed(
        {**parsed.statements, "L06.9": "SUPPORTED"},
        parsed.conflict,
        parsed.pattern,
        parsed.honest,
        [],
    )
    with pytest.raises(ValueError, match="no row matches"):
        merge_labels(
            labels(), parsed_extra, broken_key, owner_review="owner labelled the review sheet"
        )
    with pytest.raises(ValueError, match="owner_review"):
        merge_labels(labels(), parsed, key, owner_review="  ")
