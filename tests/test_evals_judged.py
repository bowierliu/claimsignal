"""Judged faithfulness summaries: case is the unit, intervals are deterministic."""

from __future__ import annotations

from collections import Counter

from claims_copilot.evals.judged import PROVENANCE, bootstrap_interval, summarise


def answer(case: str, supported: int, total: int, cannot_tell: int = 0) -> dict[str, object]:
    labels = Counter({"SUPPORTED": supported, "CANNOT_TELL": cannot_tell})
    labels["PARTLY"] = total - supported - cannot_tell
    return {"case": case, "supported": supported, "total": total, "labels": +labels}


def test_each_case_counts_once_whatever_its_repeats() -> None:
    rows = [answer("a", 10, 10), answer("a", 10, 10), answer("a", 10, 10), answer("b", 0, 4)]
    out = summarise(rows)
    assert out["cases"] == 2
    assert out["case_mean_supported"]["rate"] == 0.5  # (1.0 + 0.0) / 2, not 30/34
    assert out["pooled_statement_supported"]["n_statements"] == 34


def test_bootstrap_is_deterministic_and_brackets_the_mean() -> None:
    values = [1.0, 0.9, 0.8, 1.0, 0.7, 1.0]
    first = bootstrap_interval(values)
    assert first == bootstrap_interval(values)
    assert first[0] <= sum(values) / len(values) <= first[1]


def test_empty_input_is_reported_not_crashed() -> None:
    assert summarise([]) == {"answers": 0, "cases": 0}


def test_cannot_tell_share_is_shown() -> None:
    out = summarise([answer("a", 6, 10, cannot_tell=2)])
    assert out["cannot_tell_share"] == 0.2


def test_provenance_names_model_drafted_labels_not_human_ones() -> None:
    assert "model-drafted" in PROVENANCE
    assert "human-labelled" not in PROVENANCE
