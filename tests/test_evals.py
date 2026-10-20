"""The Phase 7 case schema, split, metric definitions, and the pre-registration file."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from claims_copilot.agent.answer import Status
from claims_copilot.evals.metrics import (
    FindingScore,
    MetricError,
    case_means,
    cohens_kappa,
    judge_acceptance,
    paired,
    rate_over_cases,
    sign_test_p,
    status_ok,
    unstable_cases,
    wilson_interval,
)
from claims_copilot.evals.prereg import PREREG_PATH, load_preregistration
from claims_copilot.evals.schema import CaseError, EvalCase, Layer, SafetyKind, Split
from claims_copilot.evals.split import assign_splits
from claims_copilot.project import REPO_ROOT
from claims_copilot.synth.anomalies import DUPLICATE, OUTLIER


def case(cid: str, layer: Layer = Layer.UNANSWERABLE, **kw: object) -> EvalCase:
    kw.setdefault("expected_statuses", (Status.INSUFFICIENT_EVIDENCE,))
    if layer is Layer.UNANSWERABLE:
        kw.setdefault("absent_terms", ("x",))
    return EvalCase(case_id=cid, layer=layer, question="What does the policy say?", **kw)  # type: ignore[arg-type]


# --- schema ---


def test_a_valid_case_round_trips_through_json() -> None:
    c = EvalCase(
        case_id="e2e-001",
        layer=Layer.E2E,
        question="Summarise the evidence for claim X0001.",
        expected_statuses=(Status.ANSWERED, Status.CONFLICTING_EVIDENCE),
        claim_id="X0001",
        expected_anomalies=(DUPLICATE,),
    )
    assert EvalCase.from_dict(json.loads(json.dumps(c.to_dict()))) == c


@pytest.mark.parametrize(
    "kwargs",
    [
        {"case_id": "Bad Id"},
        {"question": "  "},
        {"expected_statuses": ()},
        {"expected_statuses": (Status.INVALID_OUTPUT,)},
        {"layer": Layer.E2E},  # needs a claim id
        {"expected_anomalies": ("not_a_type",), "layer": Layer.E2E, "claim_id": "X0001"},
        {"expected_anomalies": (DUPLICATE,)},  # anomalies only for e2e
        {"layer": Layer.SAFETY},  # needs a safety kind
        {"safety_kind": SafetyKind.PLANTED_INJECTION},  # safety kind only for safety
        {
            "layer": Layer.E2E,
            "claim_id": "X0001",
            "expected_anomalies": (DUPLICATE,),
            "decoy_anomalies": (OUTLIER,),
        },
    ],
)
def test_malformed_cases_are_rejected(kwargs: dict[str, object]) -> None:
    base: dict[str, object] = {
        "case_id": "case-001",
        "layer": Layer.UNANSWERABLE,
        "question": "q?",
        "expected_statuses": (Status.INSUFFICIENT_EVIDENCE,),
    }
    base.update(kwargs)
    with pytest.raises(CaseError):
        EvalCase(**base)  # type: ignore[arg-type]


def test_from_dict_reports_malformed_records_without_echoing_content() -> None:
    with pytest.raises(CaseError) as err:
        EvalCase.from_dict({"case_id": "case-001", "layer": "nonsense"})
    assert "nonsense" not in str(err.value)


# --- split ---


def test_split_is_deterministic_stratified_and_order_independent() -> None:
    cases = [case(f"u-{i:02d}") for i in range(20)] + [
        case(f"s-{i:02d}", Layer.SAFETY, safety_kind=SafetyKind.OBFUSCATED_DECISION_ASK)
        for i in range(25)
    ]
    a = assign_splits(cases)
    b = assign_splits(list(reversed(cases)))
    assert a == b
    dev = [cid for cid, s in a.items() if s is Split.DEV]
    assert sum(1 for cid in dev if cid.startswith("u-")) == 7  # (20 + 1) // 3
    assert sum(1 for cid in dev if cid.startswith("s-")) == 8  # (25 + 1) // 3


def test_adding_a_case_in_another_layer_does_not_move_existing_cases() -> None:
    base = [case(f"u-{i:02d}") for i in range(20)]
    before = assign_splits(base)
    extra = [case("s-01", Layer.SAFETY, safety_kind=SafetyKind.PLANTED_INJECTION)]
    after = assign_splits(base + extra)
    assert all(after[cid] == before[cid] for cid in before)


def test_duplicate_ids_are_rejected() -> None:
    with pytest.raises(CaseError):
        assign_splits([case("u-01"), case("u-01")])


# --- metrics ---


def test_wilson_interval_matches_the_phase6_example() -> None:
    iv = wilson_interval(13, 16)
    assert iv.rate == pytest.approx(0.8125)
    assert iv.low == pytest.approx(0.570, abs=0.01)
    assert iv.high == pytest.approx(0.934, abs=0.01)


def test_wilson_interval_handles_the_extremes() -> None:
    assert wilson_interval(0, 10).low == 0.0
    assert wilson_interval(10, 10).high == 1.0
    with pytest.raises(MetricError):
        wilson_interval(1, 0)


def test_repeats_are_averaged_per_case_before_any_rate() -> None:
    means = case_means([("a", True), ("a", False), ("a", False), ("b", True), ("b", True)])
    assert means == {"a": pytest.approx(1 / 3), "b": 1.0}
    assert rate_over_cases(means) == pytest.approx((1 / 3 + 1) / 2)


def test_unstable_cases_lists_cases_whose_status_changed() -> None:
    runs = [("a", "ANSWERED"), ("a", "INVALID_OUTPUT"), ("b", "ANSWERED"), ("b", "ANSWERED")]
    assert unstable_cases(runs) == ["a"]


def test_sign_test_is_exact_and_two_sided() -> None:
    assert sign_test_p(0, 0) == 1.0
    assert sign_test_p(5, 5) == 1.0
    assert sign_test_p(8, 0) == pytest.approx(2 / 256)
    assert sign_test_p(0, 8) == sign_test_p(8, 0)
    assert sign_test_p(3, 1) == pytest.approx(0.625)


def test_paired_counts_gained_and_lost() -> None:
    a = {"1": True, "2": True, "3": False, "4": False}
    b = {"1": True, "2": False, "3": True, "4": False}
    p = paired(a, b)
    assert (p.gained, p.lost, p.both, p.neither) == (1, 1, 1, 1)
    with pytest.raises(MetricError):
        paired(a, {"1": True})


def test_kappa_known_values_and_degenerate_case() -> None:
    assert cohens_kappa([True, True, False, False], [True, True, False, False]) == 1.0
    assert cohens_kappa([True, False, True, False], [False, True, False, True]) == -1.0
    with pytest.raises(MetricError):
        cohens_kappa([True, True], [True, True])


def _labels(tp: int, tn: int, fp: int, fn: int) -> tuple[list[bool], list[bool]]:
    human = [True] * tp + [False] * tn + [False] * fp + [True] * fn
    judge = [True] * tp + [False] * tn + [True] * fp + [False] * fn
    return human, judge


def test_judge_is_accepted_only_when_all_three_conditions_hold() -> None:
    kw = {"kappa_min": 0.6, "false_supported_max": 2, "min_minority_class_statements": 15}
    h, j = _labels(tp=60, tn=30, fp=1, fn=3)
    assert judge_acceptance(h, j, **kw).accepted  # type: ignore[arg-type]
    h, j = _labels(tp=60, tn=30, fp=5, fn=0)  # kappa fine, too many false "supported"
    v = judge_acceptance(h, j, **kw)  # type: ignore[arg-type]
    assert not v.accepted and v.reason == "too many false 'supported'"
    h, j = _labels(tp=40, tn=20, fp=10, fn=10)  # kappa low
    assert judge_acceptance(h, j, **kw).reason == "kappa below the minimum"  # type: ignore[arg-type]
    h, j = _labels(tp=80, tn=5, fp=0, fn=0)  # too few of the minority class
    assert judge_acceptance(h, j, **kw).reason == "too few statements in the minority class"  # type: ignore[arg-type]


def test_finding_score_recall() -> None:
    s = FindingScore(frozenset({DUPLICATE, OUTLIER}), frozenset({DUPLICATE}))
    assert s.recall == 0.5 and s.missed == frozenset({OUTLIER})
    with pytest.raises(MetricError):
        _ = FindingScore(frozenset(), frozenset({DUPLICATE})).recall


def test_status_ok_accepts_any_listed_status() -> None:
    assert status_ok("ANSWERED", ["ANSWERED", "CONFLICTING_EVIDENCE"])
    assert not status_ok("INVALID_OUTPUT", ["ANSWERED"])


# --- the pre-registration file ---


def test_preregistration_loads_and_is_internally_consistent() -> None:
    p = load_preregistration()
    assert p.version == "phase7-prereg-v1" and p.repeats == 3
    assert p.phase_ceiling_usd == Decimal("4.00")
    assert p.safety_mix and sum(p.safety_mix.values()) == p.layer_sizes["safety"]
    assert sum(p.label_sample_mix.values()) == p.labelled_answers
    assert all(v == 0 for v in p.invariants.values())
    assert 0 < p.kappa_min < 1 and 0 < p.alpha < 1


def test_the_agent_layers_total_the_planned_95_new_cases() -> None:
    p = load_preregistration()
    assert sum(v for k, v in p.layer_sizes.items() if k != "retrieval_existing") == 95


def test_preregistration_document_states_the_same_thresholds() -> None:
    p = load_preregistration()
    doc = (REPO_ROOT / "docs" / "PHASE7_PREREGISTRATION.md").read_text(encoding="utf-8")
    for needle in (
        f"kappa of at least {p.kappa_min}",
        f"no more than {p.false_supported_max}",
        f"{p.min_minority_class_statements} statements",
        f"{p.repeats} repeats",
        f"${p.phase_ceiling_usd}",
        PREREG_PATH.name,
    ):
        assert needle in doc, needle


def test_rubrics_exist_and_are_versioned() -> None:
    for name in ("faithfulness_v1.md", "conflict_v1.md"):
        assert (REPO_ROOT / "eval" / "rubrics" / name).is_file()
