"""Judge calibration against the owner's hand labels, by the pre-registered rule.

    uv run python -m claims_copilot.evals.calibrate           # needs eval/phase7_hand_labels.jsonl

Inputs: the owner's labels (written by `labels ingest` from the owner-filled sheet, `labeller` is
always "owner") and the judge's labels for the same answers (`data/runs/p7-dev-lexical/judgments/`).
The judge is accepted only if `judge_acceptance` says so (kappa, false "supported", minority-class
size). Otherwise it is reported as uncalibrated and faithfulness comes from the owner's labels
alone.
This module never writes a label: it refuses rows whose labeller is not "owner".
"""

from __future__ import annotations

import contextlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from claims_copilot.evals.judge import read_judgments
from claims_copilot.evals.labels import DEV_RUN, HAND_LABELS_PATH
from claims_copilot.evals.metrics import (
    MetricError,
    cohens_kappa,
    judge_acceptance,
    wilson_interval,
)
from claims_copilot.evals.prereg import load_preregistration
from claims_copilot.project import REPO_ROOT, RUNS_DIR

CALIBRATION_PATH = REPO_ROOT / "eval" / "scorecards" / "phase7_judge_calibration.json"
SUPPORTED = "SUPPORTED"


class LabelSourceError(ValueError):
    """A label row is not the owner's."""


def read_hand_labels(path: Path = HAND_LABELS_PATH) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    bad = [r.get("item") for r in rows if r.get("labeller") != "owner"]
    if bad:
        raise LabelSourceError(f"rows not labelled by the owner: {bad[:5]}")
    return rows


def _interval(successes: int, n: int) -> dict[str, float | int] | None:
    if n < 1:
        return None
    w = wilson_interval(successes, n)
    return {"rate": round(w.rate, 4), "low": round(w.low, 4), "high": round(w.high, 4), "n": n}


def calibrate(hand: list[dict[str, Any]], judgments: dict[str, dict[str, Any]]) -> dict[str, Any]:
    prereg = load_preregistration()
    statements = [r for r in hand if r["kind"] == "statement"]
    human: list[bool] = []
    judge: list[bool] = []
    confusion: Counter[tuple[str, str]] = Counter()
    unjudged = 0
    for r in statements:
        j = judgments.get(r["run_file"])
        labels = j["labels"] if j else None
        if not labels or str(r["n"]) not in labels:
            unjudged += 1  # a bad judge parse is a recorded failure, never a guessed label
            continue
        jl = labels[str(r["n"])]
        human.append(r["label"] == SUPPORTED)
        judge.append(jl == SUPPORTED)
        confusion[(r["label"], jl)] += 1
    out: dict[str, Any] = {
        "statements_labelled_by_owner": len(statements),
        "statements_with_judge_label": len(human),
        "statements_without_judge_label": unjudged,
        "owner_label_counts": dict(Counter(r["label"] for r in statements)),
        "owner_supported_rate": _interval(
            sum(r["label"] == SUPPORTED for r in statements), len(statements)
        ),
        "confusion_owner_by_judge": {f"{h}|{j}": n for (h, j), n in sorted(confusion.items())},
    }
    if human:
        verdict = None
        try:
            verdict = judge_acceptance(
                human,
                judge,
                kappa_min=prereg.kappa_min,
                false_supported_max=prereg.false_supported_max,
                min_minority_class_statements=prereg.min_minority_class_statements,
            )
            out["judge"] = {
                "accepted": verdict.accepted,
                "reason": verdict.reason,
                "kappa": None if verdict.kappa is None else round(verdict.kappa, 4),
                "false_supported": verdict.false_supported,
                "minority_class_statements": verdict.minority_statements,
            }
        except MetricError as exc:
            out["judge"] = {"accepted": False, "reason": f"kappa undefined: {exc}"}
        out["raw_agreement"] = round(
            sum(a == b for a, b in zip(human, judge, strict=True)) / len(human), 4
        )
        if verdict is not None and verdict.kappa is None:
            with contextlib.suppress(MetricError):
                out["kappa_for_information"] = round(cohens_kappa(human, judge), 4)
    out["conflict"] = _conflict(hand, judgments, prereg.conflict_min_labelled_answers)
    honest = [r for r in hand if r["kind"] == "honest"]
    out["honest_non_answers"] = _interval(sum(r["label"] == "HONEST" for r in honest), len(honest))
    return out


def _conflict(
    hand: list[dict[str, Any]], judgments: dict[str, dict[str, Any]], minimum: int
) -> dict[str, Any]:
    rows = [r for r in hand if r["kind"] == "conflict"]
    out: dict[str, Any] = {"labelled_answers": len(rows)}
    by_pattern: dict[str, Counter[str]] = {}
    for r in rows:
        by_pattern.setdefault(r["pattern"], Counter())[r["label"]] += 1
    out["owner_labels_by_pattern"] = {p: dict(c) for p, c in sorted(by_pattern.items())}
    out["owner_warranted_rate"] = _interval(sum(r["label"] == "WARRANTED" for r in rows), len(rows))
    if len(rows) < minimum:
        out["judge"] = (
            f"not calibrated: fewer than {minimum} labelled conflict answers; hand labels only"
        )
        return out
    pairs = [
        (r["label"] == "WARRANTED", j["conflict_label"] == "WARRANTED")
        for r in rows
        if (j := judgments.get(r["run_file"])) and j.get("conflict_label")
    ]
    out["judge_pairs"] = len(pairs)
    if pairs:
        out["judge_raw_agreement"] = round(sum(a == b for a, b in pairs) / len(pairs), 4)
        try:
            out["judge_kappa"] = round(
                cohens_kappa([a for a, _ in pairs], [b for _, b in pairs]), 4
            )
        except MetricError as exc:
            out["judge_kappa"] = f"undefined: {exc}"
    return out


def main() -> int:
    hand = read_hand_labels()
    result = calibrate(hand, read_judgments(RUNS_DIR / DEV_RUN / "judgments"))
    CALIBRATION_PATH.write_text(
        json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
