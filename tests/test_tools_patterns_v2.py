from __future__ import annotations

from fractions import Fraction
from math import comb
from pathlib import Path

import pytest

from claims_copilot.tools import patterns_v2 as v2
from claims_copilot.tools.patterns import provider_intensity
from claims_copilot.tools.repository import Repository, VisitMix
from tool_fixtures import Db, L


def mix(pid: str, high: int, total: int = 60, spec: str = "cardio") -> VisitMix:
    return VisitMix(pid, spec, total, high)


def peers(n: int = 30, total: int = 60) -> list[VisitMix]:
    """n same-specialty peers with high shares spread from 10% to about 40%."""
    return [mix(f"P{i + 10:04d}", 6 + (i % 19), total) for i in range(n)]


def exact_tail(n: int, x: int, p: Fraction) -> Fraction:
    return sum((comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(x, n + 1)), Fraction(0))


def test_the_tail_probability_matches_exact_rational_arithmetic() -> None:
    for n, x, p in ((10, 8, Fraction(1, 2)), (60, 33, Fraction(3, 10)), (45, 9, Fraction(1, 5))):
        assert v2.binomial_upper_tail(n, x, float(p)) == pytest.approx(
            float(exact_tail(n, x, p)), rel=1e-9
        )


def test_the_tail_has_sane_edges() -> None:
    assert v2.binomial_upper_tail(20, 0, 0.3) == 1.0
    assert v2.binomial_upper_tail(20, 21, 0.3) == 0.0
    assert v2.binomial_upper_tail(20, 20, 0.5) == pytest.approx(0.5**20)
    # large n does not overflow
    assert 0.0 <= v2.binomial_upper_tail(2000, 1500, 0.3) < 1e-100


def test_more_volume_makes_the_same_share_stronger_evidence() -> None:
    small = v2.binomial_upper_tail(20, 10, 0.3)
    large = v2.binomial_upper_tail(200, 100, 0.3)
    assert large < small


def test_a_clearly_high_provider_is_flagged_with_the_numbers() -> None:
    a = v2.assess(mix("P0001", 45), peers())
    assert a.decision == "flag"
    assert a.abstention is None
    assert a.multiplicity == 31  # 30 peers + the subject
    assert a.alpha_adjusted == pytest.approx(0.05 / 31)
    assert a.p_value < a.alpha_adjusted
    assert a.gap_above_p75 >= v2.MIN_GAP_ABOVE_P75


def test_a_provider_inside_the_peer_range_is_not_flagged() -> None:
    a = v2.assess(mix("P0001", 18), peers())
    assert a.decision == "no_flag"
    assert a.abstention is None


def test_the_gap_rule_blocks_a_statistically_significant_but_small_difference() -> None:
    # A very high volume makes a small excess significant; the absolute gap rule still holds back.
    pool = [mix(f"P{i + 10:04d}", 120 + (i % 9) * 6, 400) for i in range(30)]
    subject = VisitMix("P0001", "cardio", 4000, 1500)  # 0.375 vs peer P75 about 0.34
    a = v2.assess(subject, pool)
    assert a.p_value < a.alpha_adjusted
    assert a.gap_above_p75 < v2.MIN_GAP_ABOVE_P75
    assert a.decision == "no_flag"


def test_low_volume_provider_abstains_with_a_reason() -> None:
    a = v2.assess(mix("P0001", 30, total=v2.MIN_VISIT_LINES - 1), peers())
    assert (a.decision, a.abstention) == ("abstain", "subject_below_min_volume")


def test_a_group_with_too_few_peers_abstains() -> None:
    a = v2.assess(mix("P0001", 45), peers(v2.MIN_PEERS - 1))
    assert (a.decision, a.abstention) == ("abstain", "too_few_peers")


def test_peers_below_the_volume_minimum_do_not_count() -> None:
    thin = [*peers(v2.MIN_PEERS - 1), mix("P0099", 3, total=v2.MIN_VISIT_LINES - 1)]
    a = v2.assess(mix("P0001", 45), thin)
    assert a.abstention == "too_few_peers"


def test_a_group_whose_median_share_is_already_high_abstains() -> None:
    high_group = [mix(f"P{i + 10:04d}", 36 + (i % 6), 60) for i in range(30)]  # about 0.6-0.7
    a = v2.assess(mix("P0001", 58), high_group)
    assert (a.decision, a.abstention) == ("abstain", "peer_median_at_or_above_limit")


def test_the_subject_is_never_part_of_its_own_peer_group() -> None:
    group = peers()
    subject = mix("P0010", 45)  # same id as the first peer
    a = v2.assess(subject, group)
    assert a.peer_count == len(group) - 1


def test_a_zero_median_is_floored_so_the_test_is_defined() -> None:
    zero = [mix(f"P{i + 10:04d}", 0, 60) for i in range(30)]
    a = v2.assess(mix("P0001", 40), zero)
    assert a.p0_used == v2.P0_FLOOR
    assert a.decision == "flag"


def test_the_multiplicity_correction_grows_with_the_group() -> None:
    small = v2.assess(mix("P0001", 40), peers(25))
    large = v2.assess(mix("P0001", 40), peers(60))
    assert large.alpha_adjusted < small.alpha_adjusted


def test_assessment_is_deterministic() -> None:
    assert v2.assess(mix("P0001", 40), peers()) == v2.assess(mix("P0001", 40), peers())


# --- the tool wrapper over a repository --------------------------------------------------------


def add_provider(db: Db, provider: str, high: int, total: int, spec: str = "cardio") -> None:
    for i in range(total):
        code = "X0003" if i < high else "X0001"
        db.claim(
            f"C{provider[1:]}{i:03d}",
            [L(code)],
            provider=provider,
            specialty=spec,
            member=f"M{i:06d}",
        )


def build(tmp_path: Path, subject_high: int, total: int = 60) -> Repository:
    db = Db(tmp_path / "p.sqlite")
    for i in range(25):
        add_provider(db, f"P{i + 10:04d}", 6 + (i % 14), 60)
    add_provider(db, "P0001", subject_high, total)
    return db.open()


def test_the_tool_wrapper_returns_a_finding_with_parameters_and_limits(tmp_path: Path) -> None:
    repo = build(tmp_path, 45)
    res = v2.provider_intensity_v2(repo, "P0001")
    assert [f.check for f in res.findings] == [v2.INTENSITY_V2_CHECK]
    metrics = dict(res.metrics)
    assert metrics["decision"] == "flag"
    assert metrics["multiplicity_m"] == "26"
    assert dict(res.parameters)["min_gap_above_p75"] == str(v2.MIN_GAP_ABOVE_P75)
    assert any("not a conclusion" in s for s in res.limits)
    assert any("Bonferroni" in s or "multiplicity" in s for s in res.limits)


def test_the_tool_wrapper_reports_an_abstention_reason(tmp_path: Path) -> None:
    repo = build(tmp_path, 20, total=30)
    res = v2.provider_intensity_v2(repo, "P0001")
    assert res.findings == ()
    assert dict(res.metrics)["decision"] == "abstain"
    assert dict(res.metrics)["abstention_reason"] == "subject_below_min_volume"


def test_v1_is_unchanged_by_v2_existing(tmp_path: Path) -> None:
    repo = build(tmp_path, 45)
    res = provider_intensity(repo, "P0001")
    assert res.tool == "provider_intensity"
    assert dict(res.parameters)["z_threshold"] == "3.5"
    assert dict(res.parameters)["min_peers"] == "10"
