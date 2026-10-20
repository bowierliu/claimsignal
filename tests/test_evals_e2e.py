"""The e2e case file: stratified, reproducible from the seed, and free of truth-store access."""

from __future__ import annotations

import json
from collections import Counter

from claims_copilot.evals.casefile import read_cases
from claims_copilot.evals.e2e import (
    CASES_PATH,
    DATASET_INFO_PATH,
    E2E_SEED,
    build_cases,
    build_dataset,
    dataset_info,
    policy_related,
)
from claims_copilot.evals.prereg import load_preregistration
from claims_copilot.synth.anomalies import ANOMALY_TYPES


def test_the_committed_cases_regenerate_exactly_from_the_seed() -> None:
    dataset = build_dataset()
    assert read_cases(CASES_PATH) == build_cases(dataset)
    assert json.loads(DATASET_INFO_PATH.read_text()) == dataset_info(dataset)


def test_thirty_cases_stratified_across_five_types_with_decoys() -> None:
    cases = read_cases(CASES_PATH)
    assert len(cases) == load_preregistration().layer_sizes["e2e"] == 30
    seeded = Counter(a for c in cases for a in c.expected_anomalies)
    decoys = Counter(a for c in cases for a in c.decoy_anomalies)
    assert seeded == dict.fromkeys(ANOMALY_TYPES, 4)
    assert decoys == dict.fromkeys(ANOMALY_TYPES, 2)
    assert len({c.claim_id for c in cases}) == 30


def test_the_seed_is_fresh() -> None:
    assert E2E_SEED not in (20261019, 20261020)


def test_a_third_of_the_cases_ask_about_policy() -> None:
    assert sum(1 for c in read_cases(CASES_PATH) if policy_related(c)) == 10


def test_the_question_never_names_the_anomaly() -> None:
    for c in read_cases(CASES_PATH):
        text = c.question.lower()
        assert not any(w in text for w in ("duplicate", "unbundl", "outlier", "excess", "decoy"))
