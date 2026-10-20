"""Judge calibration: the pre-registered rule applied to synthetic label files, owner-only rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from claims_copilot.evals.calibrate import LabelSourceError, calibrate, read_hand_labels


def stmt(i: int, label: str, run: str = "r1") -> dict[str, Any]:
    return {
        "item": f"L{i:02d}",
        "run_file": f"{run}-{i}",
        "kind": "statement",
        "n": 1,
        "of": 1,
        "label": label,
        "labeller": "owner",
    }


def judged(i: int, label: str, run: str = "r1") -> tuple[str, dict[str, Any]]:
    return f"{run}-{i}", {"labels": {"1": label}, "conflict_label": None}


def build(pairs: list[tuple[str, str]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    hand = [stmt(i, h) for i, (h, _) in enumerate(pairs)]
    judgments = dict(judged(i, j) for i, (_, j) in enumerate(pairs))
    return hand, judgments


def test_agreeing_judge_is_accepted() -> None:
    pairs = [("SUPPORTED", "SUPPORTED")] * 20 + [("NOT_SUPPORTED", "NOT_SUPPORTED")] * 16
    hand, judgments = build(pairs)
    out = calibrate(hand, judgments)
    assert out["judge"]["accepted"] is True
    assert out["judge"]["kappa"] == 1.0
    assert out["raw_agreement"] == 1.0


def test_false_supported_rejects_even_with_good_kappa() -> None:
    pairs = (
        [("SUPPORTED", "SUPPORTED")] * 30
        + [("NOT_SUPPORTED", "NOT_SUPPORTED")] * 20
        + [("NOT_SUPPORTED", "SUPPORTED")] * 3
    )
    out = calibrate(*build(pairs))
    assert out["judge"]["accepted"] is False
    assert out["judge"]["reason"] == "too many false 'supported'"


def test_small_minority_class_is_uncalibrated() -> None:
    pairs = [("SUPPORTED", "SUPPORTED")] * 40 + [("NOT_SUPPORTED", "NOT_SUPPORTED")] * 5
    out = calibrate(*build(pairs))
    assert out["judge"]["accepted"] is False
    assert "minority" in out["judge"]["reason"]


def test_all_one_class_does_not_crash() -> None:
    out = calibrate(*build([("SUPPORTED", "SUPPORTED")] * 20))
    assert out["judge"]["accepted"] is False


def test_unjudged_statements_are_counted_not_guessed() -> None:
    hand, judgments = build([("SUPPORTED", "SUPPORTED")] * 3)
    judgments["r1-1"] = {"labels": None, "conflict_label": None}
    out = calibrate(hand, judgments)
    assert out["statements_without_judge_label"] == 1
    assert out["statements_with_judge_label"] == 2


def test_conflict_below_minimum_is_hand_labels_only() -> None:
    hand = [
        {
            "item": "L01",
            "run_file": "c1",
            "kind": "conflict",
            "label": "WARRANTED",
            "pattern": "OTHER",
            "labeller": "owner",
        }
    ]
    out = calibrate(hand, {})
    assert "hand labels only" in out["conflict"]["judge"]
    assert out["conflict"]["owner_warranted_rate"]["n"] == 1


def test_rows_not_from_the_owner_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "labels.jsonl"
    path.write_text(json.dumps({**stmt(1, "SUPPORTED"), "labeller": "assistant"}) + "\n")
    with pytest.raises(LabelSourceError):
        read_hand_labels(path)
