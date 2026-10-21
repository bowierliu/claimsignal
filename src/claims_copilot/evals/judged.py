"""Judged faithfulness, from recorded runs and judgments. No provider call.

    uv run python -m claims_copilot.evals.judged --run p7-test-lexical --out FILE

The judge is accepted by the registered rule against **model-drafted labels** (amendment A4), so
every number here is "judged faithfulness, judge calibrated against model-drafted labels, owner
review: form check only". The unit is the case: statements are pooled per answer, answers are
averaged per case, and every case counts once. A pooled statement rate with a Wilson interval is
shown beside it (optimistic, because statements in one answer are correlated). The conflict judge
is not calibrated (fewer than 10 labelled conflict answers), so its output is counted but not
reported as a metric.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from claims_copilot.evals.judge import read_judgments
from claims_copilot.evals.labels import stem_of
from claims_copilot.evals.metrics import wilson_interval
from claims_copilot.evals.runner import read_run
from claims_copilot.project import REPO_ROOT, RUNS_DIR

SCORECARD_DIR = REPO_ROOT / "eval" / "scorecards"
SUPPORTED = "SUPPORTED"
BOOTSTRAP_SEED = 7
BOOTSTRAP_DRAWS = 2000
PROVENANCE = (
    "judge accepted by the registered rule against model-drafted labels (GPT Sol), owner review: "
    "form check only (amendment A4, KF-041); not human-validated"
)


def bootstrap_interval(values: list[float]) -> tuple[float, float]:
    """Seeded percentile bootstrap of the mean over cases (95%)."""
    rng = random.Random(BOOTSTRAP_SEED)  # noqa: S311
    means = sorted(
        statistics.fmean(rng.choice(values) for _ in values) for _ in range(BOOTSTRAP_DRAWS)
    )
    return means[int(0.025 * BOOTSTRAP_DRAWS)], means[int(0.975 * BOOTSTRAP_DRAWS) - 1]


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """`rows`: one per judged answer: case, supported, total, labels (Counter)."""
    if not rows:
        return {"answers": 0, "cases": 0}
    per_case: dict[str, list[float]] = defaultdict(list)
    counts: Counter[str] = Counter()
    for r in rows:
        counts.update(r["labels"])
        if r["total"]:
            per_case[r["case"]].append(r["supported"] / r["total"])
    case_rates = [statistics.fmean(v) for v in per_case.values()]
    statements = sum(counts.values())
    out: dict[str, Any] = {
        "answers": len(rows),
        "cases": len(per_case),
        "statements": statements,
        "label_counts": dict(sorted(counts.items())),
    }
    if case_rates:
        low, high = bootstrap_interval(case_rates)
        out["case_mean_supported"] = {
            "rate": round(statistics.fmean(case_rates), 4),
            "low": round(low, 4),
            "high": round(high, 4),
            "n_cases": len(case_rates),
        }
        w = wilson_interval(counts[SUPPORTED], statements)
        out["pooled_statement_supported"] = {
            "rate": round(w.rate, 4),
            "low": round(w.low, 4),
            "high": round(w.high, 4),
            "n_statements": statements,
            "note": "statements within an answer are correlated; this interval is optimistic",
        }
        out["cannot_tell_share"] = round(counts["CANNOT_TELL"] / statements, 4)
    return out


def judged_scorecard(run: Path) -> dict[str, Any]:
    judgments = read_judgments(run / "judgments")
    rows = read_run(run)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    conflict: Counter[str] = Counter()
    unjudged = 0
    for row in rows:
        j = judgments.get(stem_of(row))
        shown = row["record"]["answer"]["status"] in ("ANSWERED", "CONFLICTING_EVIDENCE")
        if not j or not shown:
            unjudged += bool(shown)
            continue
        if j["labels"] is None:
            unjudged += 1
            continue
        counts = Counter(j["labels"].values())
        item = {
            "case": row["case"]["case_id"],
            "supported": counts[SUPPORTED],
            "total": sum(counts.values()),
            "labels": counts,
        }
        layer = row["case"]["layer"]
        provider = row["job"]["provider"]
        for key in ("all", f"layer:{layer}", f"provider:{provider}", f"{layer}/{provider}"):
            buckets[key].append(item)
        if j.get("conflict_label") not in (None, "NOT_APPLICABLE"):
            conflict[f"{j['conflict_pattern']}|{j['conflict_label']}"] += 1
    return {
        "run": run.name,
        "provenance": PROVENANCE,
        "target_pre_registered": 0.85,
        "shown_answers_without_a_judgment": unjudged,
        "judged": {k: summarise(v) for k, v in sorted(buckets.items())},
        "conflict_judge": {
            "calibrated": False,
            "reason": "fewer than 10 labelled conflict answers; counts only, not a metric",
            "counts_pattern_label": dict(sorted(conflict.items())),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_copilot.evals.judged", description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    result = judged_scorecard(RUNS_DIR / args.run)
    text = json.dumps(result, indent=1, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
