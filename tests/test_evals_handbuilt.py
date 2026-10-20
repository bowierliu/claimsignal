"""The hand-built tool fixture: shape, determinism, and that its expected values are written
independently of the tools (the tools are then scored against them, not the other way round)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from claims_copilot.evals.handbuilt import (
    BUNDLE,
    CLEAN_PEERS,
    CONTAMINATED_PEERS,
    INTENSITY,
    Scenario,
    build_handbuilt,
    score_handbuilt,
)
from claims_copilot.evals.schema import Layer


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[Scenario]]:
    path = tmp_path_factory.mktemp("hb") / "payer.sqlite"
    return path, build_handbuilt(path)


def test_twenty_scenarios_with_unique_ids_and_claims(built: tuple[Path, list[Scenario]]) -> None:
    _, scenarios = built
    assert len(scenarios) == 20
    assert len({s.case_id for s in scenarios}) == 20
    assert len({s.claim_id for s in scenarios}) == 20


def test_scenarios_convert_to_valid_eval_cases(built: tuple[Path, list[Scenario]]) -> None:
    _, scenarios = built
    for s in scenarios:
        case = s.to_eval_case()
        assert case.layer is Layer.TOOLS_HANDBUILT and case.claim_id == s.claim_id


def test_the_build_is_deterministic(tmp_path: Path) -> None:
    a, b = tmp_path / "a.sqlite", tmp_path / "b.sqlite"
    build_handbuilt(a)
    build_handbuilt(b)
    assert hashlib.sha256(a.read_bytes()).hexdigest() == hashlib.sha256(b.read_bytes()).hexdigest()


def test_the_peer_groups_are_realistic_not_packed() -> None:
    assert len(CLEAN_PEERS) == len(CONTAMINATED_PEERS) == 30
    elevated = [h for h in CONTAMINATED_PEERS if h / 50 >= 0.6]
    assert len(elevated) == 3  # 10%, not the 33% to 40% of the generated data (KF-017)
    assert not [h for h in CLEAN_PEERS if h / 50 >= 0.6]


def test_expected_results_are_declared_by_hand(built: tuple[Path, list[Scenario]]) -> None:
    _, scenarios = built
    by_id = {s.case_id: s for s in scenarios}
    assert by_id["hb-01"].expected_findings == {BUNDLE}
    assert by_id["hb-15"].expected_findings == {INTENSITY}
    assert sum(1 for s in scenarios if s.decoy) == 10


def test_the_tools_score_against_the_hand_built_expectations(
    built: tuple[Path, list[Scenario]],
) -> None:
    """Recorded, not tuned: if this fails, the failure goes to KNOWN_FAILURES.md; neither the
    scenarios nor the expectations are edited to make it pass."""
    path, scenarios = built
    score = score_handbuilt(path, scenarios)
    misses = [
        (r.scenario.case_id, sorted(r.missed), sorted(r.extra))
        for r in score.results
        if not r.exact or not r.observations_ok
    ]
    assert misses == []
