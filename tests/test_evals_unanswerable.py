"""The unanswerable questions: the file matches the code and the topics are absent."""

from __future__ import annotations

import json

import pytest

from claims_copilot.evals.casefile import read_cases
from claims_copilot.evals.prereg import load_preregistration
from claims_copilot.evals.schema import Layer
from claims_copilot.evals.unanswerable import CASES_PATH, unanswerable_cases
from claims_copilot.project import CHUNKS_DIR


def test_the_committed_file_matches_the_code() -> None:
    assert read_cases(CASES_PATH) == unanswerable_cases()


def test_there_are_twenty_with_unique_ids_and_six_near_misses() -> None:
    cases = unanswerable_cases()
    assert len(cases) == load_preregistration().layer_sizes["unanswerable"] == 20
    assert all(c.layer is Layer.UNANSWERABLE for c in cases)
    assert sum(1 for c in cases if c.note.startswith("near miss")) == 6


def test_every_question_mentions_its_topic() -> None:
    for c in unanswerable_cases():
        assert any(t.split()[0] in c.question.lower() for t in c.absent_terms), c.case_id


def test_no_absent_term_occurs_anywhere_in_the_corpus() -> None:
    path = CHUNKS_DIR / "chunks.jsonl"
    if not path.is_file():
        pytest.skip("chunked corpus not present locally")
    corpus = [json.loads(line)["text"].lower() for line in path.read_text("utf-8").splitlines()]
    found = {
        (c.case_id, t)
        for c in unanswerable_cases()
        for t in c.absent_terms
        if any(t in text for text in corpus)
    }
    assert found == set()
