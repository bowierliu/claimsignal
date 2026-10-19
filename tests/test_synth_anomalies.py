from __future__ import annotations

from collections import Counter
from dataclasses import fields

import pytest

from claims_copilot.synth.anomalies import (
    ANOMALY_TYPES,
    DATE_ANOMALY,
    DUPLICATE,
    EXCESS_UNITS,
    OUTLIER,
    UNBUNDLING,
)
from claims_copilot.synth.baseline import GenerationError
from claims_copilot.synth.codes import PROC_CODE_PATTERN
from claims_copilot.synth.config import GeneratorConfig
from claims_copilot.synth.dataset import Dataset, payer_hash, truth_hash
from claims_copilot.synth.generate import generate
from claims_copilot.synth.models import AnomalyTruth, Member
from synth_oracle import Findings, find_anomalies


@pytest.fixture(scope="module")
def dataset() -> Dataset:
    return generate(GeneratorConfig.small())


def run_oracle(ds: Dataset) -> Findings:
    return find_anomalies(
        ds.claims,
        ds.claim_lines,
        ds.bundle_pairs,
        ds.unit_limits,
        ds.providers,
        ds.procedure_codes,
        ds.config.min_visit_lines,
    )


def test_each_type_has_the_configured_number_of_anomalies_and_decoys(dataset: Dataset) -> None:
    cfg = dataset.config
    counts = Counter((t.anomaly_type, t.is_decoy) for t in dataset.truth)
    for kind in ANOMALY_TYPES:
        assert counts[(kind, False)] == cfg.anomalies_per_type, kind
        assert counts[(kind, True)] == cfg.decoys_per_type, kind


def test_independent_checker_recovers_every_anomaly_and_flags_no_decoy(dataset: Dataset) -> None:
    """Exact set equality: 100% recall and zero extras (no decoys, no clean claims)."""
    found = run_oracle(dataset)
    real = [t for t in dataset.truth if not t.is_decoy]

    def of(kind: str) -> list[AnomalyTruth]:
        return [t for t in real if t.anomaly_type == kind]

    assert found.duplicates == {frozenset(t.claim_ids) for t in of(DUPLICATE)}
    assert found.unbundled_lines == {t.line_ids[1] for t in of(UNBUNDLING)}
    assert found.excess_unit_lines == {t.line_ids[0] for t in of(EXCESS_UNITS)}
    assert found.out_of_window_lines == {t.line_ids[0] for t in of(DATE_ANOMALY)}
    assert found.outlier_providers == {t.provider_id for t in of(OUTLIER)}


def test_dataset_is_reproducible_and_seed_sensitive() -> None:
    cfg = GeneratorConfig.small()
    a, b = generate(cfg), generate(cfg)
    assert payer_hash(a) == payer_hash(b) and truth_hash(a) == truth_hash(b)
    c = generate(GeneratorConfig.small(seed=7))
    assert payer_hash(c) != payer_hash(a)


def test_truth_references_exist_and_no_claim_is_in_two_cases(dataset: Dataset) -> None:
    claim_ids = {c.claim_id for c in dataset.claims}
    line_ids = {ln.line_id for ln in dataset.claim_lines}
    seen: Counter[str] = Counter()
    for t in dataset.truth:
        assert set(t.claim_ids) <= claim_ids and set(t.line_ids) <= line_ids
        assert t.explanation.strip()
        seen.update(t.claim_ids)
    assert all(n == 1 for n in seen.values())
    assert len({t.anomaly_id for t in dataset.truth}) == len(dataset.truth)


def test_flags_cover_every_case_and_include_false_alarms(dataset: Dataset) -> None:
    flagged = {f.claim_id for f in dataset.flags}
    assert len(flagged) == len(dataset.flags)
    for t in dataset.truth:
        expected = t.claim_ids[-1] if t.anomaly_type == DUPLICATE else t.claim_ids[0]
        assert expected in flagged, t.anomaly_id
    case_claims = {cid for t in dataset.truth for cid in t.claim_ids}
    false_alarms = flagged - case_claims
    assert len(false_alarms) == dataset.config.false_alarm_flags
    ids = [f.flag_id for f in dataset.flags]
    assert ids == sorted(ids)
    assert [f.claim_id for f in dataset.flags] == sorted(f.claim_id for f in dataset.flags)


def test_data_stays_synthetic_in_shape(dataset: Dataset) -> None:
    assert all(PROC_CODE_PATTERN.fullmatch(ln.code) for ln in dataset.claim_lines)
    assert {f.name for f in fields(Member)} == {
        "member_id",
        "age_band",
        "sex",
        "plan_type",
        "region",
    }
    dx = {d.code for d in dataset.diagnosis_codes}
    assert all(set(c.diagnosis_codes) <= dx for c in dataset.claims)
    totals: Counter[str] = Counter()
    for ln in dataset.claim_lines:
        totals[ln.claim_id] += ln.billed_amount  # type: ignore[assignment]
    assert all(c.total_billed == totals[c.claim_id] for c in dataset.claims)


def test_too_few_candidates_fails_loudly() -> None:
    tiny = GeneratorConfig(
        n_members=50, n_providers=12, n_claims=200, anomalies_per_type=30, decoys_per_type=30
    )
    with pytest.raises(GenerationError):
        generate(tiny)
