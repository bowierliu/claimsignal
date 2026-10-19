"""Full-scale checks on the default configuration (a few seconds, no network)."""

from __future__ import annotations

import json
from collections import Counter

import pytest

from claims_copilot.project import SYNTH_GOLDEN_PATH
from claims_copilot.synth.anomalies import (
    ANOMALY_TYPES,
    DATE_ANOMALY,
    DUPLICATE,
    EXCESS_UNITS,
    OUTLIER,
    UNBUNDLING,
)
from claims_copilot.synth.config import GeneratorConfig
from claims_copilot.synth.dataset import Dataset, golden_summary
from claims_copilot.synth.generate import generate
from synth_oracle import find_anomalies

MIN_PER_TYPE = 30


@pytest.fixture(scope="module")
def full() -> Dataset:
    return generate(GeneratorConfig())


def test_default_dataset_matches_the_recorded_golden_summary(full: Dataset) -> None:
    """Fails if generation drifts (code, Python version, or rule changes); regenerate on purpose."""
    recorded = json.loads(SYNTH_GOLDEN_PATH.read_text())
    assert golden_summary(full) == recorded


def test_at_least_thirty_instances_and_decoys_per_type(full: Dataset) -> None:
    counts = Counter((t.anomaly_type, t.is_decoy) for t in full.truth)
    for kind in ANOMALY_TYPES:
        assert counts[(kind, False)] >= MIN_PER_TYPE, kind
        assert counts[(kind, True)] >= MIN_PER_TYPE, kind


def test_checker_recovers_all_and_flags_no_decoy_at_full_scale(full: Dataset) -> None:
    found = find_anomalies(
        full.claims,
        full.claim_lines,
        full.bundle_pairs,
        full.unit_limits,
        full.providers,
        full.procedure_codes,
        full.config.min_visit_lines,
    )
    real = [t for t in full.truth if not t.is_decoy]
    by = {k: [t for t in real if t.anomaly_type == k] for k in ANOMALY_TYPES}
    assert found.duplicates == {frozenset(t.claim_ids) for t in by[DUPLICATE]}
    assert found.unbundled_lines == {t.line_ids[1] for t in by[UNBUNDLING]}
    assert found.excess_unit_lines == {t.line_ids[0] for t in by[EXCESS_UNITS]}
    assert found.out_of_window_lines == {t.line_ids[0] for t in by[DATE_ANOMALY]}
    assert found.outlier_providers == {t.provider_id for t in by[OUTLIER]}
