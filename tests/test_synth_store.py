from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from claims_copilot.synth.config import GeneratorConfig
from claims_copilot.synth.dataset import Dataset, payer_hash, truth_hash
from claims_copilot.synth.generate import generate
from claims_copilot.synth.store import PAYER_FILE, TRUTH_FILE, load_dataset, write_dataset


@pytest.fixture(scope="module")
def written(tmp_path_factory: pytest.TempPathFactory) -> tuple[Dataset, Path]:
    ds = generate(GeneratorConfig.small())
    out = tmp_path_factory.mktemp("synth")
    write_dataset(ds, out)
    return ds, out


def test_round_trip_preserves_every_row_and_the_hashes(written: tuple[Dataset, Path]) -> None:
    ds, out = written
    back = load_dataset(out)
    assert back == ds
    assert payer_hash(back) == payer_hash(ds) and truth_hash(back) == truth_hash(ds)


def test_stored_hashes_match_the_recomputed_ones(written: tuple[Dataset, Path]) -> None:
    ds, out = written
    payer = sqlite3.connect(out / PAYER_FILE)
    truth = sqlite3.connect(out / TRUTH_FILE)
    assert payer.execute("SELECT value FROM meta WHERE key='payer_hash'").fetchone()[0] == (
        payer_hash(ds)
    )
    assert truth.execute("SELECT value FROM meta WHERE key='truth_hash'").fetchone()[0] == (
        truth_hash(ds)
    )


def test_tools_database_contains_no_ground_truth(written: tuple[Dataset, Path]) -> None:
    _, out = written
    con = sqlite3.connect(out / PAYER_FILE)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not {t for t in tables if "truth" in t or "anomaly" in t or "decoy" in t}
    columns = {r[1] for t in tables for r in con.execute(f"PRAGMA table_info({t})")}
    assert not {c for c in columns if "decoy" in c or "anomaly" in c or "variant" in c}


def test_foreign_keys_hold_in_the_payer_database(written: tuple[Dataset, Path]) -> None:
    _, out = written
    con = sqlite3.connect(out / PAYER_FILE)
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_regeneration_overwrites_cleanly(written: tuple[Dataset, Path], tmp_path: Path) -> None:
    ds, _ = written
    write_dataset(ds, tmp_path)
    write_dataset(ds, tmp_path)
    assert load_dataset(tmp_path) == ds
