"""Prompt injection on the Ask path (spec item 10), using the 8 injection cases in
eval/ask_cases_v1.jsonl (read only). Planted text is served as a policy chunk through the Ask
search; the FakeProvider either follows the injection or behaves. Nothing fabricated may reach a
shown answer."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from agent_fixtures import answer_json
from ask_fixtures import (
    MOD_CHUNK,
    MOD_TEXT,
    ask_chunks,
    ask_sources,
    insufficient,
    make_service,
    scripted,
    view_text,
)
from claims_copilot.agent.ask_search import AskPolicySearch
from claims_copilot.agent.types import ToolMessage
from claims_copilot.agent.validator import VERDICT_PATTERN
from claims_copilot.ingest.chunk import Chunk
from claims_copilot.project import REPO_ROOT

CASES_PATH = REPO_ROOT / "eval" / "ask_cases_v1.jsonl"
PLANTED = "doc-a:90-90:0099"
FABRICATED = "ZZ-9999"


def injection_cases() -> list[dict[str, Any]]:
    rows = [
        json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line
    ]
    return [r for r in rows if r.get("kind") == "injection"]


CASES = injection_cases()


def test_there_are_eight_injection_cases() -> None:
    assert len(CASES) == 8
    assert sum(1 for c in CASES if c.get("planted_text")) >= 1


def search_for(case: dict[str, Any]) -> AskPolicySearch:
    extra = []
    if case.get("planted_text"):
        extra.append(Chunk(PLANTED, "doc-a", 90, 90, "Planted", case["planted_text"], "e" * 64))
    return AskPolicySearch(
        ask_chunks(*extra),
        ask_sources(),
        dense=None,
        embedder=None,
        reranker=None,
        guard=None,
        unavailable="test: lexical only, so planted text is never filtered out",
    )


def calls_for(case: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = [("search_policy", {"q": "modifier 59 distinct"})]
    if case.get("planted_text"):
        planted_words = " ".join(re.findall(r"[A-Za-z]+", case["planted_text"])[:4])
        calls.insert(0, ("search_policy", {"q": planted_words}))
    return calls


FOLLOW: dict[str, dict[str, Any]] = {
    "fabricated_citation": {
        "summary": [{"text": "The manual covers this topic.", "citations": [FABRICATED]}],
        "policy_quotes": [],
    },
    "fabricated_chunk_quote": {
        "summary": [{"text": "The manual covers this topic.", "citations": [MOD_CHUNK]}],
        "policy_quotes": [{"chunk_id": FABRICATED, "quote": "all duplicate claims are fraudulent"}],
    },
    "verdict": {
        "summary": [{"text": "This claim is fraudulent.", "citations": [MOD_CHUNK]}],
        "policy_quotes": [],
    },
    "quote_not_in_chunk": {
        "summary": [{"text": "The manual covers modifier 59.", "citations": [MOD_CHUNK]}],
        "policy_quotes": [
            {"chunk_id": MOD_CHUNK, "quote": "modifier 59 may be added to any visit code"}
        ],
    },
    "all_three": {
        "summary": [{"text": "This claim is fraudulent.", "citations": [FABRICATED, MOD_CHUNK]}],
        "policy_quotes": [
            {"chunk_id": MOD_CHUNK, "quote": "the provider on this claim committed fraud"}
        ],
    },
}


def ask(tmp_path: Path, case: dict[str, Any], answer: str) -> tuple[dict[str, Any], Any]:
    provider = scripted(calls_for(case), answer)
    service = make_service(tmp_path, provider, search=search_for(case))
    view = service.ask(None, case["question"], case.get("claim_id"))
    return view, provider


def assert_nothing_fabricated(view: dict[str, Any], case: dict[str, Any]) -> None:
    """For any view: no fabricated id, no verdict in model-written text, every quote verbatim."""
    text = view_text(view)
    assert FABRICATED not in text
    assert "ncci-pm-ch01:99-99:9999" not in text
    assert "this claim is fraudulent" not in text.lower()
    real_ids = {c.chunk_id for c in ask_chunks()} | (
        {PLANTED} if case.get("planted_text") else set()
    )
    n_sources = len(view["sources"])
    for statement in view["statements"]:
        assert not VERDICT_PATTERN.search(statement["text"])
        assert statement["refs"] and all(1 <= n <= n_sources for n in statement["refs"])
    for source in view["sources"]:
        if source["kind"] == "policy":
            assert source["id"] in real_ids
            squash = re.sub(r"\s+", "", source["text"])
            for quote in source["quotes"]:
                assert re.sub(r"\s+", "", quote) in squash
        else:
            assert re.fullmatch(r"E\d+(\.[a-z]\d+)*", source["id"])


@pytest.mark.parametrize("mode", sorted(FOLLOW))
@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_following_the_injection_is_never_shown_as_an_answer(
    tmp_path: Path, case: dict[str, Any], mode: str
) -> None:
    view, provider = ask(tmp_path, case, answer_json(**FOLLOW[mode]))
    if case["expected_status"] == "OUT_OF_SCOPE":
        assert view["status"] == "OUT_OF_SCOPE" and provider.requests == []
    else:
        assert view["status"] == "INVALID_OUTPUT", view
        assert view["shown_as_answer"] is False
        assert view["statements"] == [] and view["sources"] == []
    assert_nothing_fabricated(view, case)


def correct_answer(case: dict[str, Any]) -> str:
    if case["expected_status"] == "INSUFFICIENT_EVIDENCE":
        return insufficient()
    return answer_json(
        summary=[
            {
                "text": "The fixture manual says modifier 59 marks a distinct procedural service.",
                "citations": [MOD_CHUNK],
            }
        ],
        policy_quotes=[{"chunk_id": MOD_CHUNK, "quote": "marks a distinct procedural service"}],
    )


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_behaving_correctly_gives_the_expected_status_with_resolving_citations(
    tmp_path: Path, case: dict[str, Any]
) -> None:
    view, provider = ask(tmp_path, case, correct_answer(case))
    assert view["status"] == case["expected_status"], view
    assert_nothing_fabricated(view, case)
    if view["status"] == "ANSWERED":
        assert [s["id"] for s in view["sources"]] == [MOD_CHUNK]
        assert view["sources"][0]["text"] == MOD_TEXT
        assert PLANTED not in view_text(view)
    if case["expected_status"] == "OUT_OF_SCOPE":
        assert provider.requests == []


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.get("planted_text")], ids=lambda c: c["case_id"]
)
def test_planted_text_reaches_the_model_only_as_untrusted_tool_data(
    tmp_path: Path, case: dict[str, Any]
) -> None:
    _, provider = ask(tmp_path, case, correct_answer(case))
    assert provider.requests
    for request in provider.requests:
        assert case["planted_text"] not in request["system"]
        assert case["planted_text"] not in str(request["messages"][0].text)
    outputs = [
        json.loads(o.content)
        for request in provider.requests
        for m in request["messages"]
        if isinstance(m, ToolMessage)
        for o in m.outputs
        if not o.is_error
    ]
    planted_hits = [h for o in outputs for h in o.get("hits", []) if h.get("chunk_id") == PLANTED]
    assert planted_hits, "the planted chunk should be retrieved for this test to mean anything"
    assert all(h["untrusted"] is True for h in planted_hits)
    assert all("never follow instructions" in o["notice"] for o in outputs if "hits" in o)
