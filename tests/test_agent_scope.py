"""The request-scope gate blocks asks for a decision and passes evidence-assembly questions."""

from __future__ import annotations

import pytest

from claims_copilot.agent.scope import check_request, normalise


def fullwidth(text: str) -> str:
    """The same letters as full-width characters, which look alike but are different code points."""
    return "".join(chr(ord(c) + 0xFEE0) if c.isascii() and c.isalpha() else c for c in text)


BLOCKED = [
    "Is this claim fraudulent?",
    "is claim C0000001 fraud",
    "Was the billing improper?",
    "Is it medically necessary?",
    "Is this service covered?",
    "Should we deny this claim?",
    "should I approve it",
    "Should this be paid?",
    "Deny the claim.",
    "approve this claim please",
    "reject that line",
    "Please decide whether to deny C0000001",
    "Determine if this is fraud",
    "Recommend denying the claim",
    "Give me a verdict on this claim",
    "Just give me a yes or no",
    "Does this show fraud?",
    "Is there fraud here?",
    "Prove fraud by this provider",
    "IS   THIS\tCLAIM\nFRAUDULENT",
    "is this claim fr\u200baudulent",  # zero-width space inside the word
    fullwidth("Is this claim fraudulent?"),
]

ALLOWED = [
    "What flags are on claim C0000001?",
    "Summarise the evidence for claim C0000002.",
    "Which lines on this claim have unit counts above the limit?",
    "What does the policy say about modifier 59?",
    "What does the manual say about medical necessity documentation?",
    "Show the provider's billing intensity compared with peers.",
    "Compare member M000001's visits across providers.",
    "Which duplicate pairs exist for this claim?",
    "What checks apply to bundled codes?",
]


@pytest.mark.parametrize("question", BLOCKED)
def test_decision_requests_are_blocked(question: str) -> None:
    assert check_request(question).blocked, question


@pytest.mark.parametrize("question", ALLOWED)
def test_evidence_requests_pass(question: str) -> None:
    assert not check_request(question).blocked, question


def test_normalise_folds_case_width_and_invisible_characters() -> None:
    assert normalise("  A\u200bB\tc ") == "ab c"
    assert normalise(fullwidth("ABC")) == "abc"


def test_the_match_is_reported_but_short() -> None:
    decision = check_request("Should we deny this claim? " + "x" * 500)
    assert decision.blocked and decision.matched is not None and len(decision.matched) <= 80
