"""Agent-level evaluation of "Ask the agent" on `eval/ask_cases_v1.jsonl` (owner demo extension).

`uv run python -m claims_copilot.evals.ask_agent --split dev|test [--provider anthropic]
[--confirm]`. Dry run by default: prints the cases and the estimated cost. With `--confirm` it runs
every case through the real `AskService` (the same code the workbench calls): one fresh session per
case, multi-turn scripts turn by turn in one session. Injection cases never run live (owner brief:
fakes only; they are covered by the test suite). Spend goes through CostGuard under per-session
`askeval-<run>-...` ledger ids; the run stops at `--ceiling`.

The split reuses the pre-registered salt and the Phase 7 rule (per kind, the first (n + 1) // 3 ids
by hash are dev). The test author never saw the implementation; labels are the author's expected
statuses (model-written), not human labels.
"""

from __future__ import annotations

import argparse
import json
import statistics
import warnings
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from claims_copilot.agent.ask_setup import ASK_PROMPT
from claims_copilot.agent.validator import VERDICT_PATTERN
from claims_copilot.budget import Usage, default_guard
from claims_copilot.evals.metrics import wilson_interval
from claims_copilot.evals.prereg import load_preregistration
from claims_copilot.evals.split import split_key
from claims_copilot.project import REPO_ROOT, RUNS_DIR
from claims_copilot.tools.repository import DEFAULT_PAYER_PATH

CASES_PATH = REPO_ROOT / "eval" / "ask_cases_v1.jsonl"
LIVE_KINDS = ("policy", "policy_paraphrase", "claim", "multiturn", "unanswerable", "out_of_scope")
DEFAULT_CEILING = Decimal("2.50")
# Planning figures from Phase 7 (Haiku median turn mix) plus about 2 hybrid searches per question.
ASSUMED_USAGE = Usage(14_000, 900)
SEARCH_USD = Decimal("0.0025")


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def assign(cases: list[dict[str, Any]], salt: str) -> dict[str, str]:
    by_kind: dict[str, list[str]] = defaultdict(list)
    for c in cases:
        by_kind[c["kind"]].append(c["case_id"])
    out: dict[str, str] = {}
    for ids in by_kind.values():
        ordered = sorted(ids, key=lambda cid: split_key(salt, cid))
        n_dev = (len(ordered) + 1) // 3
        for i, cid in enumerate(ordered):
            out[cid] = "dev" if i < n_dev else "test"
    return out


def turns_of(case: dict[str, Any]) -> list[dict[str, Any]]:
    if case.get("turns"):
        return list(case["turns"])
    return [
        {
            "question": case["question"],
            "claim_id": case["claim_id"],
            "expected_status": case["expected_status"],
        }
    ]


def _record(record_dir: Path, run_id: str) -> dict[str, Any] | None:
    found = sorted(record_dir.glob(f"*-{run_id}.json"))
    return json.loads(found[0].read_text(encoding="utf-8")) if found else None


def check_turn(view: dict[str, Any], record: dict[str, Any] | None) -> dict[str, Any]:
    """Deterministic checks on one shown answer: fabricated citations and verdict words."""
    fabricated = 0
    numbers = {s["n"] for s in view["sources"]}
    for s in view["statements"]:
        fabricated += sum(1 for n in s["refs"] if n not in numbers)
    if record is not None:
        known = set(record["evidence_ids"])
        for s in record["answer"]["summary"]:
            fabricated += sum(1 for c in s["citations"] if c not in known)
    verdict = [s["text"] for s in view["statements"] if VERDICT_PATTERN.search(s["text"])]
    sources = sorted({s["source_id"] for s in view["sources"] if s["kind"] == "policy"})
    return {"fabricated": fabricated, "verdict": len(verdict), "policy_sources": sources}


def run_live(
    cases: list[dict[str, Any]], *, provider: str, run_id: str, ceiling: Decimal, prompt: str
) -> list[dict[str, Any]]:
    warnings.filterwarnings("ignore", module="starlette")
    from claims_copilot.agent.ask_setup import build_ask_service

    out_dir = RUNS_DIR / "ask_eval" / run_id
    label = f"askeval-{run_id}-"
    service = build_ask_service(
        DEFAULT_PAYER_PATH,
        provider="openai" if provider == "openai" else "anthropic",
        record_dir=out_dir,
        label_prefix=label,
        prompt_version=prompt,
    )
    guard = default_guard()

    def spent() -> Decimal:
        return sum(
            (e.cost_usd for e in guard.ledger.entries() if (e.eval_run_id or "").startswith(label)),
            Decimal(0),
        )

    rows: list[dict[str, Any]] = []
    for case in cases:
        token = None
        for i, turn in enumerate(turns_of(case), start=1):
            if spent() >= ceiling:
                print(f"STOP: run spend reached the ${ceiling} ceiling")
                return rows
            view = service.ask(token, turn["question"], turn.get("claim_id"))
            token = view["session"]["token"]
            checks = check_turn(view, _record(out_dir, view["run"]["run_id"]))
            row = {
                "case_id": case["case_id"],
                "kind": case["kind"],
                "turn": i,
                "expected": turn["expected_status"],
                "status": view["status"],
                "reason": view["reason"],
                "expected_in_sources": case.get("expected_in_sources") if i == 1 else None,
                **checks,
                "model_turns": view["run"]["model_turns"],
                "tool_calls": view["run"]["tool_calls"],
                "cost_usd": view["run"]["turn_cost_usd"],
                "elapsed_s": view["run"]["elapsed_s"],
                "limit": view["run"]["limit"],
                "claim_in_scope": view["session"]["claim_id"],
            }
            rows.append(row)
            print(
                f"{case['case_id']:<7} t{i} {row['status']:<22} want {row['expected']:<22} "
                f"${row['cost_usd']} {row['elapsed_s']}s"
            )
    return rows


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def rate(sel: list[dict[str, Any]], ok: Any) -> dict[str, Any] | None:
        if not sel:
            return None
        k = sum(1 for r in sel if ok(r))
        w = wilson_interval(k, len(sel))
        return {
            "k": k,
            "n": len(sel),
            "rate": round(w.rate, 3),
            "low": round(w.low, 3),
            "high": round(w.high, 3),
        }

    last = {}
    for r in rows:
        last[r["case_id"]] = r  # final turn of each case
    unans = [r for r in rows if r["expected"] == "INSUFFICIENT_EVIDENCE"]
    oos = [r for r in rows if r["expected"] == "OUT_OF_SCOPE"]
    answerable = [r for r in rows if r["expected"] == "ANSWERED"]
    policy_first = [
        r for r in rows if r["kind"] in ("policy", "policy_paraphrase") and r["turn"] == 1
    ]
    shown = [r for r in rows if r["status"] in ("ANSWERED", "CONFLICTING_EVIDENCE")]
    costs = [Decimal(r["cost_usd"]) for r in rows]
    return {
        "turns": len(rows),
        "cases": len(last),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "abstention_unanswerable": rate(unans, lambda r: r["status"] == "INSUFFICIENT_EVIDENCE"),
        "refusal_out_of_scope": rate(oos, lambda r: r["status"] == "OUT_OF_SCOPE"),
        "answered_when_answerable": rate(
            answerable, lambda r: r["status"] in ("ANSWERED", "CONFLICTING_EVIDENCE")
        ),
        "policy_expected_source_cited": rate(
            [r for r in policy_first if r["status"] == "ANSWERED"],
            lambda r: bool(set(r["policy_sources"]) & set(r["expected_in_sources"] or [])),
        ),
        "multiturn_turn_match": rate(
            [r for r in rows if r["kind"] == "multiturn"], lambda r: r["status"] == r["expected"]
        ),
        "invalid_output": sum(1 for r in rows if r["status"] == "INVALID_OUTPUT"),
        "fabricated_citations_in_shown": sum(r["fabricated"] for r in shown),
        "verdict_statements_in_shown": sum(r["verdict"] for r in shown),
        "false_refusals": sum(
            1 for r in rows if r["status"] == "OUT_OF_SCOPE" and r["expected"] != "OUT_OF_SCOPE"
        ),
        "total_cost_usd": str(sum(costs, Decimal(0))),
        "median_cost_usd": str(statistics.median(costs)) if costs else "0",
        "median_elapsed_s": statistics.median([r["elapsed_s"] for r in rows]) if rows else 0,
        "p90_elapsed_s": (
            sorted(r["elapsed_s"] for r in rows)[int(0.9 * (len(rows) - 1))] if rows else 0
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_copilot.evals.ask_agent", description=__doc__)
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--provider", choices=("anthropic", "openai"), default="anthropic")
    parser.add_argument("--confirm", action="store_true", help="spend money (default: dry run)")
    parser.add_argument("--ceiling", type=Decimal, default=DEFAULT_CEILING)
    parser.add_argument("--kinds", default=",".join(LIVE_KINDS))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--prompt", default=ASK_PROMPT, help="prompt version (default: Ask's)")
    args = parser.parse_args(argv)

    cases = load_cases()
    split = assign(cases, load_preregistration().split_salt)
    kinds = [k for k in args.kinds.split(",") if k in LIVE_KINDS]
    chosen = [c for c in cases if split[c["case_id"]] == args.split and c["kind"] in kinds]
    n_turns = sum(len(turns_of(c)) for c in chosen)
    guard = default_guard()
    model_key = (
        "anthropic/claude-haiku-5-5" if args.provider == "anthropic" else "openai/gpt-6-luna"
    )
    per_turn = guard.cost(model_key, ASSUMED_USAGE) * 2 + SEARCH_USD
    mix = dict(Counter(c["kind"] for c in chosen))
    print(f"split {args.split}: {len(chosen)} cases, {n_turns} turns {mix}")
    print(f"estimated cost: about ${per_turn * n_turns:.2f} (${per_turn:.4f} per turn)")
    print(f"run ceiling ${args.ceiling}")
    if not args.confirm:
        print("dry run: nothing spent. Re-run with --confirm to spend.")
        return 0
    run_id = args.run_id or f"{args.split}-{args.provider}-{datetime.now(UTC):%Y%m%dT%H%M%S}"
    rows = run_live(
        chosen, provider=args.provider, run_id=run_id, ceiling=args.ceiling, prompt=args.prompt
    )
    summary = summarise(rows)
    out = RUNS_DIR / "ask_eval" / run_id / "results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"rows": rows, "summary": summary}, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
