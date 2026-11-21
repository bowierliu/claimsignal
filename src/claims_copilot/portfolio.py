"""Reproducible recruiter case files and the allowlisted live investigation."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from claims_copilot.evals.handbuilt import build_handbuilt
from claims_copilot.project import PRODUCT_NAME, PROMPTS_DIR, REPO_ROOT
from claims_copilot.tools.edits import check_bundling, check_service_dates, check_unit_limits
from claims_copilot.tools.repository import Repository
from claims_copilot.tools.rules import SyntheticRules


@dataclass(frozen=True)
class Case:
    title: str
    claim: str
    question: str
    check: str


CASES = {
    "units": Case(
        "Billed units", "C9000004", "How do the billed units compare with the line limit?", "units"
    ),
    "modifier": Case(
        "Exception modifier",
        "C9000002",
        "Does the component carry the exception modifier for this code pair?",
        "bundle",
    ),
    "dates": Case(
        "Service window", "C9000007", "Which service dates fall outside the claim window?", "dates"
    ),
}
CHECKS = {
    "units": "Compare units on an individual line against the invented per-line limit.",
    "bundle": "Examine same-date synthetic code pairs and their exception modifier.",
    "dates": "Compare each service date with the inclusive claim window.",
}


class Investigation(Protocol):
    def model(self, instructions: str, prompt: str) -> str: ...
    def tool[T](self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T: ...


class InvalidSelectionError(ValueError):
    """The provider's response did not support a displayable evidence selection."""


def read_dossier(path: Path, case: Case) -> dict[str, Any]:
    repo = Repository.open(path)
    try:
        claim = repo.claim(case.claim)
        return {
            "claim": claim.claim_id,
            "window": [claim.service_from.isoformat(), claim.service_to.isoformat()],
            "lines": [
                {
                    "id": line.line_id,
                    "code": line.code,
                    "units": line.units,
                    "date": line.service_date.isoformat(),
                    "modifiers": list(line.modifiers),
                }
                for line in repo.lines(case.claim)
            ],
        }
    finally:
        repo.close()


def inspect(path: Path, case: Case, check: str) -> dict[str, Any]:
    repo = Repository.open(path)
    try:
        if check == "dates":
            result = check_service_dates(repo, case.claim)
        elif check == "units":
            result = check_unit_limits(repo, SyntheticRules(repo), case.claim)
        elif check == "bundle":
            result = check_bundling(repo, SyntheticRules(repo), case.claim)
        else:
            raise InvalidSelectionError
        return {
            "tool": result.tool,
            "examined": result.examined,
            "status": result.status(),
            "limits": list(result.limits),
            "evidence": [
                {
                    "id": f"E{i}",
                    "text": item.summary,
                    "refs": [{"kind": ref.kind, "id": ref.id} for ref in item.refs],
                }
                for i, item in enumerate((*result.findings, *result.observations), start=1)
            ],
        }
    finally:
        repo.close()


def selection(raw: str, key: str, choices: set[str]) -> str:
    # Only an exact whitelisted value can affect the next step or reach the view.
    try:
        value = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise InvalidSelectionError from exc
    if not isinstance(value, dict) or set(value) != {key}:
        raise InvalidSelectionError
    selected = value[key]
    if not isinstance(selected, str) or selected not in choices:
        raise InvalidSelectionError
    return selected


def investigate(run: Investigation, path: Path, case: Case) -> dict[str, Any]:
    dossier = run.tool(read_dossier, path, case)
    plan = run.model(
        (PROMPTS_DIR / "portfolio_plan_v1.md").read_text(),
        json.dumps({"question": case.question, "dossier": dossier, "checks": CHECKS}),
    )
    choice = selection(plan, "check", set(CHECKS))
    if choice != case.check:
        raise InvalidSelectionError
    result = run.tool(inspect, path, case, choice)
    pick = run.model(
        (PROMPTS_DIR / "portfolio_evidence_v1.md").read_text(),
        json.dumps({"question": case.question, "tool_result": result}),
    )
    evidence_id = selection(pick, "evidence", {item["id"] for item in result["evidence"]})
    result["evidence"] = [item for item in result["evidence"] if item["id"] == evidence_id]
    return {"dossier": dossier, "result": result, "mode": "live"}


def replay_asset(path: Path) -> str:
    cases = {
        key: {
            "title": case.title,
            "question": case.question,
            "dossier": read_dossier(path, case),
            "result": inspect(path, case, case.check),
        }
        for key, case in CASES.items()
    }
    data = json.dumps({"name": PRODUCT_NAME, "cases": cases}, indent=2, ensure_ascii=True)
    header = "// Generated by python -m claims_copilot.portfolio from synthetic records."
    return f"{header}\nconst REPLAY = {data};\n"


def main() -> None:
    with TemporaryDirectory() as root:
        path = Path(root) / "payer.sqlite"
        build_handbuilt(path)
        (REPO_ROOT / "docs/demo/cases.js").write_text(replay_asset(path), encoding="utf-8")


if __name__ == "__main__":
    main()
