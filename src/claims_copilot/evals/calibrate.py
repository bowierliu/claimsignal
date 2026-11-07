"""Judge calibration against the reference labels, by the pre-registered rule.

    uv run python -m claims_copilot.evals.calibrate   # needs eval/phase7_model_drafted_labels.jsonl

Inputs: the reference labels (written by `labels ingest`; every row names its `label_source` and the
`owner_review` the owner gave) and the judge's labels for the same answers
(`data/runs/p7-dev-lexical/judgments/`). The judge is accepted only if `judge_acceptance` says so
(kappa, false "supported", minority-class size). Otherwise it is reported as uncalibrated.

Amendment A4: the reference labels are model-drafted (GPT Sol), not human. Agreement with them is
agreement with another LLM, which shares failure modes with the judge. Reports must say so. Rows
from the assistant or from the judge models are refused. This module never writes a label.
"""

from __future__ import annotations

import contextlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from claims_copilot.evals.judge import read_judgments
from claims_copilot.evals.labels import (
    DEV_RUN,
    LABEL_SOURCES,
    LABELS_PATH,
    MODEL_REVIEW_SOURCE,
    LabelSourceError,
    validate_model_rows,
)
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


__all__ = ["LabelSourceError", "calibrate", "provenance", "read_labels"]


def read_labels(path: Path = LABELS_PATH) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    validate_model_rows(rows)
    accepted = LABEL_SOURCES | {MODEL_REVIEW_SOURCE}
    bad = [r.get("item") for r in rows if r.get("label_source") not in accepted]
    if bad:
        raise LabelSourceError(f"rows without an accepted label_source: {bad[:5]}")
    if not all(str(r.get("owner_review", "")).strip() for r in rows):
        raise LabelSourceError("every row must record the owner_review that was done")
    return rows


def provenance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sources = {r["label_source"] for r in rows}
    counts = Counter(r["label_source"] for r in rows)
    has_model_review = MODEL_REVIEW_SOURCE in sources
    if has_model_review:
        description = (
            "mixed-model reference: GPT Sol drafted labels, with the rows reviewed in the blind "
            "Claude Sonnet 5.5 re-review replaced by the Claude labels; every row is "
            "model-generated and not human validated"
        )
    elif sources == {"gpt-sol-draft"}:
        description = "model-drafted labels (GPT Sol); the owner's review is as stated, not assumed"
    else:
        description = "see label_sources"
    return {
        "label_sources": sorted(sources),
        "source_counts": dict(sorted(counts.items())),
        "owner_review": sorted({r["owner_review"] for r in rows}),
        # True only when every row is the owner's own label; a mixed or model source is never it.
        "human_validated": sources == {"owner-hand"},
        "shares_model_family_with_judge": has_model_review,
        "description": description,
    }


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
        "statements_labelled": len(statements),
        "statements_with_judge_label": len(human),
        "statements_without_judge_label": unjudged,
        "label_counts": dict(Counter(r["label"] for r in statements)),
        "supported_rate": _interval(
            sum(r["label"] == SUPPORTED for r in statements), len(statements)
        ),
        "confusion_reference_by_judge": {f"{h}|{j}": n for (h, j), n in sorted(confusion.items())},
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
    out["sensitivity_excluding_cannot_tell"] = _without_cannot_tell(statements, judgments, prereg)
    out["conflict"] = _conflict(hand, judgments, prereg.conflict_min_labelled_answers)
    honest = [r for r in hand if r["kind"] == "honest"]
    out["honest_non_answers"] = _interval(sum(r["label"] == "HONEST" for r in honest), len(honest))
    return out


def _without_cannot_tell(
    statements: list[dict[str, Any]], judgments: dict[str, dict[str, Any]], prereg: Any
) -> dict[str, Any]:
    """For information only: the same rule with CANNOT_TELL reference statements removed. The
    registered rule (CANNOT_TELL counts as not supported) is what decides acceptance."""
    human: list[bool] = []
    judge: list[bool] = []
    for r in statements:
        j = judgments.get(r["run_file"])
        labels = j["labels"] if j else None
        if r["label"] == "CANNOT_TELL" or not labels or str(r["n"]) not in labels:
            continue
        human.append(r["label"] == SUPPORTED)
        judge.append(labels[str(r["n"])] == SUPPORTED)
    out: dict[str, Any] = {"statements": len(human), "informational_only": True}
    if not human:
        return out
    try:
        v = judge_acceptance(
            human,
            judge,
            kappa_min=prereg.kappa_min,
            false_supported_max=prereg.false_supported_max,
            min_minority_class_statements=prereg.min_minority_class_statements,
        )
        out.update(
            accepted=v.accepted,
            reason=v.reason,
            kappa=None if v.kappa is None else round(v.kappa, 4),
            false_supported=v.false_supported,
            minority_class_statements=v.minority_statements,
        )
    except MetricError as exc:
        out["reason"] = f"undefined: {exc}"
    return out


def _conflict(
    hand: list[dict[str, Any]], judgments: dict[str, dict[str, Any]], minimum: int
) -> dict[str, Any]:
    rows = [r for r in hand if r["kind"] == "conflict"]
    out: dict[str, Any] = {"labelled_answers": len(rows)}
    by_pattern: dict[str, Counter[str]] = {}
    for r in rows:
        by_pattern.setdefault(r["pattern"], Counter())[r["label"]] += 1
    out["labels_by_pattern"] = {p: dict(c) for p, c in sorted(by_pattern.items())}
    out["warranted_rate"] = _interval(sum(r["label"] == "WARRANTED" for r in rows), len(rows))
    if len(rows) < minimum:
        out["judge"] = (
            f"not calibrated: fewer than {minimum} labelled conflict answers; "
            "reference (model-drafted) labels only"
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
    hand = read_labels()
    result = calibrate(hand, read_judgments(RUNS_DIR / DEV_RUN / "judgments"))
    result["provenance"] = provenance(hand)
    CALIBRATION_PATH.write_text(
        json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
