"""Validator Rule 8 (spec item 6): a search that ran is not evidence by itself."""

from __future__ import annotations

from typing import Any

from agent_fixtures import answer_json
from claims_copilot.agent.answer import Reason, Status
from claims_copilot.agent.evidence import EvidenceRegistry
from claims_copilot.agent.validator import validate_text

CHUNK_ID = "doc-a:3-4:0000"
CHUNK_TEXT = "Modifier 59 marks a distinct procedural service."


def registry() -> tuple[EvidenceRegistry, dict[str, str]]:
    """E1: an empty search; E2: a check with one finding; E3: a search with one hit;
    E4: another empty search."""
    r = EvidenceRegistry()
    ids = {
        "empty": r.register_result({"hits": []}),
        "check": r.register_result(
            {"tool": "check_unit_limits", "findings": [{"summary": "Line 3 bills 5 units."}]}
        ),
        "search": r.register_result(
            {"hits": [{"chunk_id": CHUNK_ID, "text": CHUNK_TEXT, "source": {"source_id": "doc-a"}}]}
        ),
        "empty2": r.register_result({"hits": []}),
    }
    return r, ids


def summary(*items: tuple[str, list[str]]) -> list[dict[str, Any]]:
    return [{"text": text, "citations": cites} for text, cites in items]


def test_is_search_result_marks_only_whole_searches() -> None:
    r, ids = registry()
    assert r.is_search_result(ids["empty"]) and r.is_search_result(ids["search"])
    assert not r.is_search_result(ids["check"])
    assert not r.is_search_result(ids["check"] + ".f1")
    assert not r.is_search_result(CHUNK_ID)
    assert not r.is_search_result("E99")


def test_answered_citing_only_an_empty_search_becomes_insufficient() -> None:
    r, ids = registry()
    out = validate_text(
        answer_json(summary=summary(("The sources do not address this.", [ids["empty"]]))), r
    )
    assert (out.status, out.reason) == (Status.INSUFFICIENT_EVIDENCE, Reason.NO_RELEVANT_SOURCE)
    assert out.statements == () and out.policy_quotes == ()


def test_answered_citing_only_search_ids_with_a_quote_still_shows_no_quote() -> None:
    r, ids = registry()
    out = validate_text(
        answer_json(
            summary=summary(
                ("The search ran.", [ids["search"]]), ("Another search.", [ids["empty"]])
            ),
            policy_quotes=[{"chunk_id": CHUNK_ID, "quote": "marks a distinct procedural"}],
        ),
        r,
    )
    assert (out.status, out.reason) == (Status.INSUFFICIENT_EVIDENCE, Reason.NO_RELEVANT_SOURCE)
    assert out.statements == () and out.policy_quotes == ()


def test_answered_citing_a_real_chunk_stays_answered() -> None:
    r, _ = registry()
    out = validate_text(
        answer_json(
            summary=summary(("The manual describes modifier 59.", [CHUNK_ID])),
            policy_quotes=[{"chunk_id": CHUNK_ID, "quote": "marks a distinct procedural"}],
        ),
        r,
    )
    assert (out.status, out.reason) == (Status.ANSWERED, Reason.SUPPORTED)
    assert len(out.statements) == 1 and len(out.policy_quotes) == 1


def test_answered_citing_a_tool_finding_stays_answered() -> None:
    r, ids = registry()
    out = validate_text(
        answer_json(summary=summary(("Line 3 bills 5 units.", [ids["check"] + ".f1"]))), r
    )
    assert (out.status, out.reason) == (Status.ANSWERED, Reason.SUPPORTED)


def test_answered_citing_a_search_and_a_real_chunk_stays_answered() -> None:
    r, ids = registry()
    out = validate_text(
        answer_json(summary=summary(("The manual describes it.", [ids["search"], CHUNK_ID]))), r
    )
    assert out.status is Status.ANSWERED


def test_conflicting_evidence_cannot_rest_on_two_search_results() -> None:
    r, ids = registry()
    out = validate_text(
        answer_json(
            status="CONFLICTING_EVIDENCE",
            reason="SOURCES_DISAGREE",
            summary=summary(
                ("One search says one thing.", [ids["empty"]]),
                ("Another search says another.", [ids["empty2"]]),
            ),
        ),
        r,
    )
    assert out.status is Status.INVALID_OUTPUT
    assert not out.shown_as_answer
    assert out.statements == ()


def test_conflicting_evidence_with_a_chunk_and_a_finding_is_allowed() -> None:
    r, ids = registry()
    out = validate_text(
        answer_json(
            status="CONFLICTING_EVIDENCE",
            reason="SOURCES_DISAGREE",
            summary=summary(
                ("The check counts 5 units.", [ids["check"] + ".f1"]),
                ("The manual counts units per line.", [CHUNK_ID]),
            ),
        ),
        r,
    )
    assert out.status is Status.CONFLICTING_EVIDENCE
