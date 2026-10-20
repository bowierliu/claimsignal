"""The smoke harness: deterministic case selection, ceiling stop, records on disk. No network."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from agent_fixtures import (
    FakeProvider,
    answer_json,
    make_guard,
    make_investigator,
    make_runner,
    text_turn,
    tool_turn,
)
from api_fixtures import make_app
from claims_copilot.agent.smoke import Case, build_cases, run_smoke
from claims_copilot.agent.tools import in_process_client
from claims_copilot.budget import Usage


def test_cases_are_deterministic_and_include_the_edge_cases(tmp_path: Path) -> None:
    client = in_process_client(make_app(tmp_path))
    a = build_cases(client, seed=1, n_claims=3)
    b = build_cases(client, seed=1, n_claims=3)
    assert a == b
    ids = [c.case_id for c in a]
    assert ids[-4:] == ["edge-decision-1", "edge-decision-2", "edge-injection", "edge-unanswerable"]
    assert len(set(ids)) == len(ids)
    assert all(c.claim_id is None or c.claim_id in c.question for c in a)


def test_run_smoke_writes_one_record_per_case_and_stops_at_the_ceiling(tmp_path: Path) -> None:
    guard = make_guard(tmp_path)
    provider = FakeProvider(
        [
            tool_turn(("claim_dossier", {"claim_id": "C0000001"})),
            text_turn(answer_json()),
        ]
    )
    inv = make_investigator(tmp_path, provider, make_runner(tmp_path), guard=guard)
    cases = [
        Case(f"c{i}", "dossier", "Summarise the evidence for claim C0000001.", "C0000001", "x")
        for i in range(3)
    ]
    out = tmp_path / "runs"
    lines: list[str] = []
    one_run = guard.cost(inv._provider.model_key, Usage(1000, 100)) * 2
    rows = run_smoke(
        cases,
        [inv],
        eval_run_id="t1",
        out_dir=out,
        spent=lambda: guard.ledger.spent(eval_run_id="t1"),
        ceiling=one_run + Decimal("0.0000001"),  # spend after one run is just under it
        echo=lines.append,
    )
    assert len(rows) == 2  # the second run crosses the ceiling; the third never starts
    assert any(line.startswith("STOP") for line in lines)
    written = sorted(out.glob("*.json"))
    assert len(written) == len(rows)
    record = json.loads(written[0].read_text(encoding="utf-8"))
    assert record["answer"]["status"] == "ANSWERED"
    assert rows[0]["status"] == "ANSWERED" and rows[0]["tool_calls"] == 1
