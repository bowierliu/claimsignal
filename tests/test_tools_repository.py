from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from claims_copilot.synth.store import TRUTH_FILE
from claims_copilot.tools.errors import (
    NotFoundError,
    ToolInputError,
    check_id,
    check_limit,
)
from claims_copilot.tools.repository import Repository, RepositoryError
from tool_fixtures import Db, L


def test_refuses_the_ground_truth_file_by_name(tmp_path: Path) -> None:
    path = tmp_path / TRUTH_FILE
    sqlite3.connect(path).close()
    with pytest.raises(RepositoryError, match="ground-truth"):
        Repository.open(path)


def test_refuses_a_database_with_a_truth_like_table(tmp_path: Path) -> None:
    path = tmp_path / "renamed.sqlite"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE anomaly_truth (anomaly_id TEXT)")
    con.commit()
    with pytest.raises(RepositoryError, match="ground-truth-like"):
        Repository.open(path)


def test_refuses_a_database_with_a_truth_like_column(tmp_path: Path) -> None:
    path = tmp_path / "renamed.sqlite"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE claim (claim_id TEXT, is_decoy INTEGER)")
    con.commit()
    with pytest.raises(RepositoryError):
        Repository.open(path)


def test_missing_database_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(RepositoryError, match="not found"):
        Repository.open(tmp_path / "nope.sqlite")


def test_connection_cannot_write_or_attach(tmp_path: Path) -> None:
    db = Db(tmp_path / "payer.sqlite")
    db.claim("C0000001", [L("X0001")])
    repo = db.open()
    con = repo._con
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM claim")
    with pytest.raises(sqlite3.OperationalError):
        con.execute("INSERT INTO member VALUES ('M999999','a','b','c','d')")
    other = tmp_path / "other.sqlite"
    sqlite3.connect(other).close()
    with pytest.raises(sqlite3.OperationalError):
        con.execute(f"ATTACH DATABASE '{other}' AS other")
    assert repo.claim("C0000001").claim_id == "C0000001"


def test_ids_are_validated_and_errors_do_not_echo_long_input() -> None:
    assert check_id("claim", "C0000001") == "C0000001"
    for bad in ("c0000001", "C1", "C0000001; DROP TABLE claim", "", 5, None):
        with pytest.raises(ToolInputError):
            check_id("claim", bad)
    long_input = "C" + "9" * 500
    with pytest.raises(ToolInputError) as info:
        check_id("claim", long_input)
    assert len(str(info.value)) < 80
    with pytest.raises(ToolInputError):
        check_id("provider", "C0000001")


def test_limit_bounds() -> None:
    assert check_limit(5) == 5
    for bad in (0, -1, 201, True, "5"):
        with pytest.raises(ToolInputError):
            check_limit(bad)


def test_unknown_rows_raise_not_found(tmp_path: Path) -> None:
    db = Db(tmp_path / "payer.sqlite")
    db.claim("C0000001", [L("X0001")])
    repo = db.open()
    with pytest.raises(NotFoundError):
        repo.claim("C0000099")
    with pytest.raises(NotFoundError):
        repo.provider("P9999")
