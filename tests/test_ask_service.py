"""AskService (spec items 3, 4, 5, 8): prior turns are never citable, cost ceilings, busy, and
the view built from the validated answer. FakeProvider and fake embedder only."""

from __future__ import annotations

import threading
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import claims_copilot.agent.ask as ask_module
from agent_fixtures import MODEL_KEY, FakeProvider, answer_json, text_turn
from ask_fixtures import (
    DOSSIER,
    MOD_CHUNK,
    UNIT_FINDING,
    FakeEmbedder,
    answered,
    ask_chunks,
    ask_sources,
    dense_index,
    first_message,
    insufficient,
    ledger_text,
    make_ask_guard,
    make_service,
    planned,
    scripted,
    view_text,
)
from claims_copilot.agent.ask import AskBusyError
from claims_copilot.agent.ask_search import AskPolicySearch
from claims_copilot.agent.loop import Investigator, Limits
from claims_copilot.agent.scope import BLOCK_MESSAGE, check_request
from claims_copilot.agent.session import SessionStore
from claims_copilot.agent.types import ModelTurn
from claims_copilot.budget import CostGuard, LedgerEntry
from claims_copilot.retrieval.dense import MODEL_KEY as EMBED_KEY

NOT_A_DETERMINATION = "This is evidence for the investigator; it is not a determination."
INSUFFICIENT_MESSAGE = (
    "There is not enough evidence in the claims data or the cited public sources to answer this."
)
INVALID_MESSAGE = "The answer could not be validated, so it is not shown."
SEARCH = ("search_policy", {"q": "modifier 59"})
Q_CLAIM = "What did the checks find on claim C0000001?"
ISSUE_FRAGMENTS = (
    "unknown citation",
    "uncited statement",
    "verdict language",
    "quote not found",
    "quote cites unknown chunk",
    "needs at least",
    "needs 2 citations",
    "must have no",
)


def seed_spend(guard: CostGuard, run_label: str, amount: str) -> None:
    guard.ledger.append(
        LedgerEntry(
            timestamp="2026-01-01T00:00:00+00:00",
            phase="p5",
            model_key=MODEL_KEY,
            purpose="test seed",
            eval_run_id=run_label,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=Decimal(amount),
            cost_usd=Decimal(amount),
            status="ok",
        )
    )


# ---- spec 3: a prior-turn string cannot create a valid citation -------------------------------

TURN1 = "What does the manual say about modifier 59?"
TURN2 = "And what did that passage say again?"
PRIOR_ONLY_ID = "doc-zz:9-9:0001"


@pytest.mark.parametrize("cited", [MOD_CHUNK, "E1", PRIOR_ONLY_ID])
def test_a_prior_turn_id_is_not_citable_without_retrieving_it_again(
    tmp_path: Path, cited: str
) -> None:
    provider = planned(
        {
            TURN1: (
                [SEARCH],
                answered(
                    f"The manual describes modifier 59 (see also {PRIOR_ONLY_ID}).",
                    [
                        MOD_CHUNK,
                        "E1",
                    ],
                ),
            ),
            TURN2: ([], answered("The passage describes modifier 59.", [cited])),
        }
    )
    service = make_service(tmp_path, provider)
    v1 = service.ask(None, TURN1, None)
    assert v1["status"] == "ANSWERED", v1
    n1 = len(provider.requests)
    v2 = service.ask(v1["session"]["token"], TURN2, None)
    first = first_message(provider.requests[n1])
    assert PRIOR_ONLY_ID in first  # the id is in the prior-turn text the model saw
    assert v2["status"] == "INVALID_OUTPUT"
    assert v2["reason"] == "UNRESOLVED_CITATION"
    assert v2["shown_as_answer"] is False
    assert v2["statements"] == [] and v2["sources"] == []
    assert "The passage describes modifier 59." not in view_text(v2)


# ---- spec 4: cost ceilings --------------------------------------------------------------------


@pytest.mark.parametrize("spent", ["0.23", "0.22", "0.25", "0.30"])
def test_near_the_session_ceiling_a_question_makes_no_provider_call(
    tmp_path: Path, spent: str
) -> None:
    guard = make_ask_guard(tmp_path)
    store = SessionStore()
    session, _ = store.get_or_create(None)
    seed_spend(guard, session.run_label, spent)
    provider = scripted([DOSSIER], answered("Line 3 bills 5 units.", [UNIT_FINDING]))
    service = make_service(tmp_path, provider, guard=guard, store=store)
    view = service.ask(session.token, Q_CLAIM, "C0000001")
    assert (view["status"], view["reason"]) == ("INSUFFICIENT_EVIDENCE", "BUDGET_LIMIT")
    assert provider.requests == []
    assert guard.ledger.spent(eval_run_id=session.run_label) == Decimal(spent)
    assert view["statements"] == [] and view["sources"] == []


def test_near_the_ceiling_a_decision_question_is_still_out_of_scope(tmp_path: Path) -> None:
    guard = make_ask_guard(tmp_path)
    store = SessionStore()
    session, _ = store.get_or_create(None)
    seed_spend(guard, session.run_label, "0.23")
    provider = scripted([DOSSIER], answered("Line 3 bills 5 units.", [UNIT_FINDING]))
    service = make_service(tmp_path, provider, guard=guard, store=store)
    view = service.ask(session.token, "Is this claim fraudulent?", "C0000001")
    assert view["status"] == "OUT_OF_SCOPE"
    assert view["message"] == BLOCK_MESSAGE
    assert provider.requests == []


class LimitsSpy:
    def __init__(self) -> None:
        self.limits: list[Limits] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        spy = self

        class SpyInvestigator(Investigator):
            def __init__(self, *a: Any, **kw: Any) -> None:
                spy.limits.append(kw["limits"])
                super().__init__(*a, **kw)

        monkeypatch.setattr(ask_module, "Investigator", SpyInvestigator)


@pytest.mark.parametrize(
    ("ceiling", "spent", "configured"),
    [
        ("0.25", "0", "0.15"),
        ("0.25", "0", "1.00"),
        ("0.25", "0.15", "1.00"),
        ("0.25", "0.20", "1.00"),
        ("0.10", "0", "1.00"),
        ("1.00", "0", "1.00"),
    ],
)
def test_the_turn_budget_never_exceeds_the_turn_or_session_share(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ceiling: str, spent: str, configured: str
) -> None:
    spy = LimitsSpy()
    spy.install(monkeypatch)
    guard = make_ask_guard(tmp_path)
    store = SessionStore()
    session, _ = store.get_or_create(None)
    if Decimal(spent):
        seed_spend(guard, session.run_label, spent)
    provider = scripted([DOSSIER], answered("Line 3 bills 5 units.", [UNIT_FINDING]))
    service = make_service(
        tmp_path,
        provider,
        guard=guard,
        store=store,
        limits=Limits(max_usd=Decimal(configured)),
        session_ceiling=Decimal(ceiling),
    )
    service.ask(session.token, Q_CLAIM, "C0000001")
    assert len(spy.limits) == 1
    cap = min(Decimal("0.15"), Decimal(ceiling) - Decimal(spent) - Decimal("0.03"))
    assert spy.limits[0].max_usd <= cap


def test_the_default_session_ceiling_is_25_cents(tmp_path: Path) -> None:
    service = make_service(tmp_path, scripted([], insufficient()))
    status = service.status()
    assert Decimal(status["session_ceiling_usd"]) == Decimal("0.25")
    assert Decimal(status["turn_ceiling_usd"]) <= Decimal("0.15")
    view = service.ask(None, Q_CLAIM, "C0000001")
    assert Decimal(view["session"]["ceiling_usd"]) == Decimal("0.25")


def hybrid_search(guard: CostGuard) -> AskPolicySearch:
    table = {TURN1: (1.0, 0.0), "modifier 59": (1.0, 0.0)}
    return AskPolicySearch(
        ask_chunks(),
        ask_sources(),
        dense=dense_index({c.chunk_id: (1.0, 0.1) for c in ask_chunks()}),
        embedder=FakeEmbedder(table, default=(1.0, 0.0)),
        reranker=None,
        guard=guard,
    )


def test_all_session_spend_is_under_one_run_label_that_is_not_the_token(tmp_path: Path) -> None:
    guard = make_ask_guard(tmp_path)
    provider = scripted([SEARCH], answered("The manual describes modifier 59.", [MOD_CHUNK]))
    service = make_service(tmp_path, provider, guard=guard, search=hybrid_search(guard))
    v1 = service.ask(None, TURN1, None)
    token = v1["session"]["token"]
    v2 = service.ask(token, "And what about modifier 59 on the same day?", None)
    assert v2["session"]["token"] == token
    entries = guard.ledger.entries()
    assert {e.model_key for e in entries} == {MODEL_KEY, EMBED_KEY}
    labels = {e.eval_run_id for e in entries}
    assert len(labels) == 1
    (label,) = labels
    assert label is not None and label != token
    assert token not in ledger_text(guard)
    assert Decimal(v2["session"]["spent_usd"]) == guard.ledger.spent(eval_run_id=label)


# ---- spec 5: busy ------------------------------------------------------------------------------


def test_a_second_ask_in_a_busy_session_raises_and_calls_nothing(tmp_path: Path) -> None:
    store = SessionStore()
    session, _ = store.get_or_create(None)
    provider = scripted([], insufficient())
    service = make_service(tmp_path, provider, store=store)
    assert store.try_begin(session)
    with pytest.raises(AskBusyError):
        service.ask(session.token, Q_CLAIM, "C0000001")
    assert provider.requests == []
    store.end(session)
    assert service.ask(session.token, Q_CLAIM, "C0000001")["status"]


def test_a_second_ask_while_another_runs_on_the_server_raises(tmp_path: Path) -> None:
    started, release = threading.Event(), threading.Event()

    def script(n: int) -> ModelTurn:
        started.set()
        release.wait(10)
        return text_turn(insufficient())

    provider = FakeProvider(script)
    service = make_service(tmp_path, provider)
    errors: list[BaseException] = []

    def first() -> None:
        try:
            service.ask(None, Q_CLAIM, "C0000001")
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=first)
    worker.start()
    try:
        assert started.wait(10)
        with pytest.raises(AskBusyError):
            service.ask(None, "What do the sources say about units?", None)
    finally:
        release.set()
        worker.join(10)
    assert errors == []
    assert len(provider.requests) == 1


# ---- spec 8: the view -----------------------------------------------------------------------


def answered_view(tmp_path: Path) -> dict[str, Any]:
    provider = scripted(
        [DOSSIER, SEARCH],
        answer_json(
            summary=[
                {
                    "text": "Line 3 bills 5 units of X0020 against a limit of 2.",
                    "citations": [UNIT_FINDING],
                },
                {
                    "text": "The manual describes modifier 59 on the same day.",
                    "citations": [MOD_CHUNK, UNIT_FINDING],
                },
            ],
            policy_quotes=[{"chunk_id": MOD_CHUNK, "quote": "marks a distinct procedural service"}],
        ),
    )
    return make_service(tmp_path, provider).ask(None, Q_CLAIM, "C0000001")


def test_answered_view_numbers_sources_in_order_of_first_citation(tmp_path: Path) -> None:
    view = answered_view(tmp_path)
    assert view["status"] == "ANSWERED" and view["shown_as_answer"] is True
    assert [s["n"] for s in view["sources"]] == [1, 2]
    assert [s["id"] for s in view["sources"]] == [UNIT_FINDING, MOD_CHUNK]
    assert [st["refs"] for st in view["statements"]] == [[1], [2, 1]]
    assert view["statements"][0]["text"].startswith("Line 3 bills 5 units")


def test_answered_view_policy_source_carries_provenance_and_validated_quotes(
    tmp_path: Path,
) -> None:
    policy = answered_view(tmp_path)["sources"][1]
    assert policy["kind"] == "policy" and policy["id"] == MOD_CHUNK
    assert policy["title"] == "Fixture manual"
    assert policy["url"] == "https://example.invalid/doc-a.pdf"
    assert policy["sha256"] == "a" * 64
    assert (policy["page_start"], policy["page_end"]) == (3, 4)
    assert policy["section"] == "Section 1"
    assert policy["quotes"] == ["marks a distinct procedural service"]


def test_answered_view_claim_source_carries_examined_limits_and_a_link(tmp_path: Path) -> None:
    claim = answered_view(tmp_path)["sources"][0]
    assert claim["kind"] != "policy"
    assert isinstance(claim["examined"], str) and claim["examined"]
    assert isinstance(claim["limits"], list) and all(isinstance(x, str) for x in claim["limits"])
    assert claim["link"] == {"view": "claim", "id": "C0000001", "check": "check_unit_limits"}


def test_answered_view_limits_end_with_the_not_a_determination_line(tmp_path: Path) -> None:
    view = answered_view(tmp_path)
    assert view["limits"][-1] == NOT_A_DETERMINATION
    claim_limits = view["sources"][0]["limits"]
    assert all(limit in view["limits"] for limit in claim_limits)


def test_insufficient_view_has_the_fixed_message_runtime_searches_and_no_evidence(
    tmp_path: Path,
) -> None:
    provider = scripted(
        [("search_policy", {"q": "helicopter"})],
        insufficient(searched=["MODEL-WROTE-THIS-SEARCH-LINE"]),
    )
    view = make_service(tmp_path, provider).ask(
        None, "What do the sources say about helicopter transport?", None
    )
    assert view["status"] == "INSUFFICIENT_EVIDENCE"
    assert view["message"] == INSUFFICIENT_MESSAGE
    assert view["searched"] and any("search_policy" in s for s in view["searched"])
    assert "MODEL-WROTE-THIS-SEARCH-LINE" not in view_text(view)
    assert view["suggestions"]
    assert view["statements"] == [] and view["sources"] == []
    assert view["limits"][-1] == NOT_A_DETERMINATION


def test_an_answer_citing_only_an_empty_search_is_shown_as_insufficient(tmp_path: Path) -> None:
    provider = scripted(
        [("search_policy", {"q": "helicopter"})],
        answered("The sources say helicopters need nothing special.", ["E1"]),
    )
    view = make_service(tmp_path, provider).ask(
        None, "What do the sources say about helicopter transport?", None
    )
    assert (view["status"], view["reason"]) == ("INSUFFICIENT_EVIDENCE", "NO_RELEVANT_SOURCE")
    assert view["statements"] == [] and view["sources"] == []
    assert "helicopters need nothing special" not in view_text(view)


def test_out_of_scope_view_has_the_block_message_and_evidence_suggestions(tmp_path: Path) -> None:
    provider = scripted([], insufficient())
    view = make_service(tmp_path, provider).ask(None, "Should we deny this claim?", "C0000001")
    assert view["status"] == "OUT_OF_SCOPE"
    assert view["message"] == BLOCK_MESSAGE
    assert view["suggestions"]
    assert all(not check_request(s).blocked for s in view["suggestions"])
    assert view["statements"] == [] and view["sources"] == []
    assert provider.requests == []


def test_out_of_scope_view_limits_also_end_with_the_not_a_determination_line(
    tmp_path: Path,
) -> None:
    view = make_service(tmp_path, scripted([], insufficient())).ask(
        None, "Should we deny this claim?", "C0000001"
    )
    assert view["limits"] and view["limits"][-1] == NOT_A_DETERMINATION


@pytest.mark.parametrize(
    ("statement", "citations", "quotes", "reason"),
    [
        ("SECRET-MODEL-SENTENCE about line 3.", ["E99"], [], "UNRESOLVED_CITATION"),
        (
            "SECRET-MODEL-SENTENCE: the provider committed fraud.",
            [UNIT_FINDING],
            [],
            "VERDICT_LANGUAGE",
        ),
        (
            "SECRET-MODEL-SENTENCE on modifier 59.",
            [MOD_CHUNK],
            [{"chunk_id": MOD_CHUNK, "quote": "SECRET-MODEL-QUOTE not in the passage"}],
            "QUOTE_NOT_FOUND",
        ),
        ("SECRET-MODEL-SENTENCE without a citation.", [], [], "UNRESOLVED_CITATION"),
    ],
)
def test_invalid_view_shows_the_fixed_message_and_no_model_text_or_issue_strings(
    tmp_path: Path,
    statement: str,
    citations: list[str],
    quotes: list[dict[str, str]],
    reason: str,
) -> None:
    provider = scripted(
        [DOSSIER, SEARCH],
        answer_json(
            summary=[{"text": statement, "citations": citations}],
            policy_quotes=quotes,
            searched=["SECRET-MODEL-SEARCHED"],
        ),
    )
    view = make_service(tmp_path, provider).ask(None, Q_CLAIM, "C0000001")
    assert view["status"] == "INVALID_OUTPUT" and view["reason"] == reason
    assert view["shown_as_answer"] is False
    assert view["message"] == INVALID_MESSAGE
    assert view["statements"] == [] and view["sources"] == []
    text = view_text(view)
    assert "SECRET-MODEL" not in text
    assert "E99" not in text
    for fragment in ISSUE_FRAGMENTS:
        assert fragment not in text.lower()
    assert view["limits"][-1] == NOT_A_DETERMINATION


def test_the_session_ceiling_view_is_insufficient_and_ends_with_the_limits_line(
    tmp_path: Path,
) -> None:
    guard = make_ask_guard(tmp_path)
    store = SessionStore()
    session, _ = store.get_or_create(None)
    seed_spend(guard, session.run_label, "0.24")
    view = make_service(tmp_path, scripted([], insufficient()), guard=guard, store=store).ask(
        session.token, Q_CLAIM, "C0000001"
    )
    assert view["status"] == "INSUFFICIENT_EVIDENCE" and view["reason"] == "BUDGET_LIMIT"
    assert view["limits"][-1] == NOT_A_DETERMINATION
    assert view["statements"] == [] and view["sources"] == []


def test_a_conflicting_view_numbers_sources_and_ends_with_the_limits_line(tmp_path: Path) -> None:
    provider = scripted(
        [DOSSIER, SEARCH],
        answer_json(
            status="CONFLICTING_EVIDENCE",
            reason="SOURCES_DISAGREE",
            summary=[
                {"text": "The check counts 5 units on line 3.", "citations": [UNIT_FINDING]},
                {"text": "The manual describes modifier 59.", "citations": [MOD_CHUNK]},
            ],
        ),
    )
    view = make_service(tmp_path, provider).ask(None, Q_CLAIM, "C0000001")
    assert view["status"] == "CONFLICTING_EVIDENCE"
    assert [s["id"] for s in view["sources"]] == [UNIT_FINDING, MOD_CHUNK]
    assert view["limits"][-1] == NOT_A_DETERMINATION


def test_a_view_is_built_only_from_tool_payloads_for_sources(tmp_path: Path) -> None:
    """Every source id in an ANSWERED view is something this turn's tools returned."""
    view = answered_view(tmp_path)
    tool_ids = {UNIT_FINDING, MOD_CHUNK}
    assert {s["id"] for s in view["sources"]} <= tool_ids
    assert view["run"]["model_turns"] == 2
    assert view["run"]["tool_calls"] == 2
