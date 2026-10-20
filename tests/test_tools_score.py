from __future__ import annotations

import json
from pathlib import Path

import pytest

from claims_copilot.synth.config import GeneratorConfig
from claims_copilot.synth.generate import generate
from claims_copilot.synth.store import write_dataset
from claims_copilot.tools.score import (
    Scorecard,
    _jsonable,
    parameters,
    params_hash,
    render,
    score_dataset,
)


@pytest.fixture(scope="module")
def card(tmp_path_factory: pytest.TempPathFactory) -> Scorecard:
    out = tmp_path_factory.mktemp("score")
    ds = generate(GeneratorConfig.small())
    write_dataset(ds, out)
    return score_dataset(out, "small")


def test_accounting_adds_up(card: Scorecard) -> None:
    for t in card.types.values():
        assert t.true_positives + len(t.missed) == t.positives
        assert t.raised == t.true_positives + t.decoys_raised + t.clean_raised
        assert t.decoys_raised == len(t.decoys_raised_ids)
        assert t.clean_raised == len(t.clean_raised_ids)
    assert sum(card.group_sizes.values()) == card.claims_scored


def test_label_counts_match_the_small_configuration(card: Scorecard) -> None:
    cfg = GeneratorConfig.small()
    for name in ("unbundling", "excess_units", "date_anomaly", "intensity_outlier"):
        assert card.types[name].positives == cfg.anomalies_per_type
        assert card.types[name].decoys == cfg.decoys_per_type
    assert card.types["duplicate_claim"].positives == 2 * cfg.anomalies_per_type


def test_report_names_its_parameters_and_serialises(card: Scorecard) -> None:
    text = render(card)
    assert card.params_hash in text and "z_threshold" in text and "Decoys raised" in text
    data = _jsonable(card)
    assert json.loads(json.dumps(data))["types"]["unbundling"]["recall"] is not None


def test_parameter_hash_changes_when_a_parameter_changes() -> None:
    base = parameters()
    assert params_hash(base) == params_hash(dict(base))
    assert params_hash(base) != params_hash({**base, "z_threshold": "3.0"})


def test_the_scorecard_reads_truth_but_only_through_a_read_only_connection() -> None:
    src = (Path(__file__).resolve().parents[1] / "src/claims_copilot/tools/score.py").read_text()
    assert "mode=ro" in src
