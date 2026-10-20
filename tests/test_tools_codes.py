from __future__ import annotations

from pathlib import Path

from claims_copilot.tools.codes import (
    BAD_POINTER,
    DUPLICATE_DX,
    NO_DX,
    OUT_OF_SET_YEAR,
    UNKNOWN_DX,
    validate_claim_codes,
)
from claims_copilot.tools.icd import IcdCodeSet, normalize_code
from tool_fixtures import D, Db, L, icd_fixture


def test_known_codes_pass(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0001")], dx=("E119", "I10"))
    repo = db.open()
    res = validate_claim_codes(repo, "C0000001", icd_fixture("E119", "I10"))
    assert res.findings == ()
    assert "2 of 2 diagnosis codes" in res.examined


def test_unknown_diagnosis_code_is_a_finding(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0001")], dx=("E119", "I10"))
    repo = db.open()
    res = validate_claim_codes(repo, "C0000001", icd_fixture("E119"))
    assert [f.check for f in res.findings] == [UNKNOWN_DX]
    assert dict(res.findings[0].detail)["code"] == "I10"


def test_without_a_code_list_diagnoses_are_not_checked_and_it_says_so(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0001")], dx=("ZZZZ",))
    repo = db.open()
    res = validate_claim_codes(repo, "C0000001", None)
    assert res.findings == ()
    assert any("not checked" in s for s in res.limits)
    assert "0 of 1 diagnosis codes" in res.examined


def test_service_dates_outside_the_code_set_year_are_reported(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0001")], dx=("E119",), start="2028-01-05")
    repo = db.open()
    res = validate_claim_codes(repo, "C0000001", icd_fixture("E119"))
    assert [f.check for f in res.findings] == [OUT_OF_SET_YEAR]
    assert "0 of 1" in res.examined


def test_missing_and_repeated_diagnoses(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0001")], dx=())
    db.claim("C0000002", [L("X0001")], dx=("E119", "E119"))
    repo = db.open()
    # with no diagnoses, the line's pointer is also out of range: both are true facts
    checks = [f.check for f in validate_claim_codes(repo, "C0000001", None).findings]
    assert sorted(checks) == sorted([NO_DX, BAD_POINTER])
    assert [f.check for f in validate_claim_codes(repo, "C0000002", None).findings] == [
        DUPLICATE_DX
    ]


def test_code_normalisation_and_set_window() -> None:
    codes = icd_fixture("E119")
    assert codes.contains("e11.9") and normalize_code(" e11.9 ") == "E119"
    assert codes.covers(D("2026-10-01")) and codes.covers(D("2027-09-30"))
    assert not codes.covers(D("2026-09-30")) and not codes.covers(D("2027-10-01"))
    assert isinstance(codes, IcdCodeSet)
