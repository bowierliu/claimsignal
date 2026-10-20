"""Case files: one JSON object per line, committed under `eval/`; never edited after a run."""

from __future__ import annotations

import json
from pathlib import Path

from claims_copilot.evals.schema import EvalCase, check_unique


def write_cases(path: Path, cases: list[EvalCase]) -> None:
    check_unique(cases)
    lines = [json.dumps(c.to_dict(), ensure_ascii=False, sort_keys=True) for c in cases]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_cases(path: Path) -> list[EvalCase]:
    cases = [
        EvalCase.from_dict(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    check_unique(cases)
    return cases
