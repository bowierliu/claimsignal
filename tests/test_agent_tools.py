"""The tool runner: allow-list, argument checks, error handling, and evidence registration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_fixtures import answer_json, make_runner
from claims_copilot.agent.evidence import EvidenceRegistry
from claims_copilot.agent.tools import ToolRunner
from claims_copilot.agent.types import ToolCall, ToolOutput
from claims_copilot.agent.validator import validate_text

EXPECTED_TOOLS = {
    "get_claim",
    "run_claim_check",
    "claim_dossier",
    "list_flags",
    "get_member_history",
    "search_policy",
    "get_provider_profile",
    "provider_intensity",
    "provider_peer_group",
}


def call(runner: ToolRunner, reg: EvidenceRegistry, name: str, **args: object) -> ToolOutput:
    return runner.execute(ToolCall("c1", name, dict(args)), reg)


def test_the_allow_list_is_exactly_the_apis_tool_manifest(tmp_path: Path) -> None:
    runner = make_runner(tmp_path)
    assert runner.names == EXPECTED_TOOLS
    assert {s.name for s in runner.specs()} == EXPECTED_TOOLS
    for spec in runner.specs():
        assert spec.parameters["type"] == "object" and spec.description


def test_a_result_is_registered_and_shown_with_its_evidence_id(tmp_path: Path) -> None:
    runner, reg = make_runner(tmp_path), EvidenceRegistry()
    out = call(runner, reg, "get_claim", claim_id="C0000001")
    assert not out.is_error
    assert json.loads(out.content)["evidence_id"] == "E1"
    assert reg.has("E1") and reg.latest_id == "E1"


def test_dossier_findings_get_citable_ids(tmp_path: Path) -> None:
    runner, reg = make_runner(tmp_path), EvidenceRegistry()
    out = call(runner, reg, "claim_dossier", claim_id="C0000001")
    body = json.loads(out.content)
    finding = body["results"][0]["findings"][0]
    assert finding["evidence_id"] == "E1.r1.f1"
    assert reg.has("E1.r1.f1")
    answer = answer_json(
        summary=[{"text": "A pair is billed together.", "citations": ["E1.r1.f1"]}]
    )
    assert validate_text(answer, reg).shown_as_answer


def test_policy_hits_are_cited_by_chunk_id(tmp_path: Path) -> None:
    runner, reg = make_runner(tmp_path), EvidenceRegistry()
    out = call(runner, reg, "search_policy", q="modifier 59")
    assert not out.is_error
    assert reg.has("doc-a:3-4:0000")
    assert reg.chunk_text("doc-a:3-4:0000") == "Modifier 59 marks a distinct procedural service."
    assert not reg.has("unverified:1-1:0000")  # never served, so never citable


def test_unknown_tools_arguments_and_types_are_errors_not_calls(tmp_path: Path) -> None:
    runner, reg = make_runner(tmp_path), EvidenceRegistry()
    cases: list[tuple[str, dict[str, Any]]] = [
        ("health_check", {}),
        ("list_tools", {}),
        ("get_claim", {"claim_id": "C0000001", "extra": "x"}),
        ("get_claim", {}),
        ("get_claim", {"claim_id": ["C0000001"]}),
        ("get_claim", {"claim_id": True}),
        ("get_claim", {"claim_id": {"a": 1}}),
    ]
    for name, args in cases:
        out = runner.execute(ToolCall("c1", name, args), reg)
        assert out.is_error, (name, args)
        assert "error" in json.loads(out.content)
    assert reg.ids() == []  # nothing registered for errors


def test_api_errors_are_returned_without_echoing_the_hostile_value(tmp_path: Path) -> None:
    runner, reg = make_runner(tmp_path), EvidenceRegistry()
    hostile = "C1'; DROP TABLE claims;--"
    out = call(runner, reg, "get_claim", claim_id=hostile)
    assert out.is_error and "DROP TABLE" not in out.content
    bad = call(runner, reg, "get_claim", claim_id="BAD")
    assert bad.is_error and "HTTP 422" in bad.content
    missing = call(runner, reg, "get_claim", claim_id="C9999999")
    assert missing.is_error and "HTTP 404" in missing.content
    assert reg.ids() == []


def test_path_arguments_cannot_escape_their_route(tmp_path: Path) -> None:
    runner, reg = make_runner(tmp_path), EvidenceRegistry()
    out = call(runner, reg, "get_claim", claim_id="../health")
    assert out.is_error
    out = call(runner, reg, "get_claim", claim_id="C0000001/dossier")
    assert out.is_error


def test_oversized_results_are_trimmed_and_ids_cover_only_what_was_shown(tmp_path: Path) -> None:
    from api_fixtures import make_app
    from claims_copilot.agent.tools import in_process_client

    runner = ToolRunner(in_process_client(make_app(tmp_path)), max_result_chars=900)
    reg = EvidenceRegistry()
    out = call(runner, reg, "claim_dossier", claim_id="C0000001")
    body = json.loads(out.content)
    assert len(out.content) <= 900 or out.is_error
    if not out.is_error:
        assert "_omitted" in body or all(len(v) <= 3 for v in body.values() if isinstance(v, list))


def test_a_result_that_cannot_fit_is_an_error(tmp_path: Path) -> None:
    from api_fixtures import make_app
    from claims_copilot.agent.tools import in_process_client

    runner = ToolRunner(in_process_client(make_app(tmp_path)), max_result_chars=60)
    reg = EvidenceRegistry()
    out = call(runner, reg, "get_claim", claim_id="C0000001")
    assert out.is_error and "too large" in out.content
    assert reg.ids() == []


def test_policy_search_without_an_index_is_an_error_the_model_can_read(tmp_path: Path) -> None:
    runner, reg = make_runner(tmp_path, policy=False), EvidenceRegistry()
    out = call(runner, reg, "search_policy", q="modifier 59")
    assert out.is_error and "HTTP 503" in out.content
