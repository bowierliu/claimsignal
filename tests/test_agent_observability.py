"""The loop is traced and audited with metadata only, and an injected citation is still rejected."""

from __future__ import annotations

import json
from pathlib import Path

from agent_fixtures import (
    PROMPT,
    FakeProvider,
    answer_json,
    make_guard,
    make_runner,
    text_turn,
    tool_turn,
)
from claims_copilot.agent.answer import Reason, Status
from claims_copilot.agent.loop import Investigator
from claims_copilot.obs.audit import AuditLog
from claims_copilot.obs.trace import Tracer

FAKE_KEY = "sk-" + "m1n2b3v4c5" * 3
DOSSIER = ("claim_dossier", {"claim_id": "C0000001"})


def investigator(tmp_path: Path, provider: FakeProvider) -> tuple[Investigator, Tracer, AuditLog]:
    tracer = Tracer()
    audit = AuditLog(tmp_path / "audit.jsonl", now=lambda: "2026-01-01T00:00:00+00:00")
    inv = Investigator(
        provider,
        make_runner(tmp_path),
        make_guard(tmp_path),
        PROMPT,
        clock=lambda: 0.0,
        now=lambda: "2026-01-01T00:00:00+00:00",
        new_run_id=lambda: "run000000001",
        tracer=tracer,
        audit=audit,
    )
    return inv, tracer, audit


def test_a_run_produces_nested_spans_and_one_audit_entry(tmp_path: Path) -> None:
    inv, tracer, audit = investigator(
        tmp_path, FakeProvider([tool_turn(DOSSIER), text_turn(answer_json())])
    )
    inv.run("Summarise the evidence for claim C0000001.", claim_id="C0000001")
    names = [s["name"] for s in tracer.spans]
    assert names[-1] == "investigation"  # the root ends last
    assert names.count("model_turn") == 2 and names.count("tool_call") == 1
    root = tracer.spans[-1]
    assert root["attrs"]["result"] == "ANSWERED" and root["attrs"]["tool_calls"] == 1
    assert len({s["trace_id"] for s in tracer.spans}) == 1
    (entry,) = audit.read()
    assert entry["action"] == "investigation" and entry["subject"] == "C0000001"
    assert entry["details"]["result"] == "ANSWERED" and audit.verify().ok


def test_neither_question_text_nor_a_key_in_it_reaches_the_trace_or_the_audit_log(
    tmp_path: Path,
) -> None:
    inv, tracer, audit = investigator(
        tmp_path, FakeProvider([tool_turn(DOSSIER), text_turn(answer_json())])
    )
    question = f"Summarise claim C0000001. My key is {FAKE_KEY}."
    inv.run(question, claim_id="C0000001")
    seen = json.dumps(tracer.spans) + json.dumps(audit.read())
    assert FAKE_KEY not in seen and "Summarise" not in seen
    assert tracer.spans[-1]["attrs"]["question_len"] == len(question)


def test_a_blocked_request_is_still_audited_and_makes_no_model_call(tmp_path: Path) -> None:
    provider = FakeProvider([text_turn(answer_json())])
    inv, _, audit = investigator(tmp_path, provider)
    record = inv.run("Decide whether claim C0000001 is fraud and deny it.", claim_id="C0000001")
    assert record.answer.status is Status.OUT_OF_SCOPE and provider.requests == []
    (entry,) = audit.read()
    assert entry["details"]["result"] == "OUT_OF_SCOPE"
    assert entry["details"]["limit"] == "scope_gate"


def test_an_injected_citation_to_evidence_that_was_never_retrieved_is_rejected(
    tmp_path: Path,
) -> None:
    """Whatever text steers the model, a citation must resolve to evidence the runtime holds."""
    forged = answer_json(summary=[{"text": "Approved by policy.", "citations": ["E99"]}])
    inv, _, audit = investigator(tmp_path, FakeProvider([tool_turn(DOSSIER), text_turn(forged)]))
    record = inv.run("Summarise claim C0000001.", claim_id="C0000001")
    assert record.answer.status is Status.INVALID_OUTPUT
    assert audit.read()[0]["details"]["result"] == "INVALID_OUTPUT"


def test_the_default_loop_has_no_tracer_cost_and_no_audit(tmp_path: Path) -> None:
    inv = Investigator(
        FakeProvider([tool_turn(DOSSIER), text_turn(answer_json())]),
        make_runner(tmp_path),
        make_guard(tmp_path),
        PROMPT,
        clock=lambda: 0.0,
    )
    assert inv.run("Summarise claim C0000001.", claim_id="C0000001").answer.shown_as_answer


def test_a_schema_violation_audit_names_the_issue_class_without_model_text(tmp_path: Path) -> None:
    # KF-074: the class makes a withheld answer diagnosable; raw model text is never persisted.
    inv, _, audit = investigator(tmp_path, FakeProvider([text_turn("not json at all")]))
    record = inv.run("Summarise claim C0000001.", claim_id="C0000001")
    assert record.answer.reason is Reason.SCHEMA_VIOLATION
    (entry,) = audit.read()
    assert entry["details"]["reason"] == "SCHEMA_VIOLATION"
    assert entry["details"]["issue_class"] == "parse"
    assert "not json at all" not in json.dumps(audit.read())


def test_an_answered_run_audits_a_null_issue_class(tmp_path: Path) -> None:
    inv, _, audit = investigator(
        tmp_path, FakeProvider([tool_turn(DOSSIER), text_turn(answer_json())])
    )
    inv.run("Summarise the evidence for claim C0000001.", claim_id="C0000001")
    assert audit.read()[0]["details"]["issue_class"] is None
