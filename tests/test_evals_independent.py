"""The independent-author delivery loader: validation, id mapping, and label separation."""

from __future__ import annotations

import copy
import sqlite3
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from claims_copilot.evals import independent as ind
from claims_copilot.tools.icd import IcdCodeSet
from claims_copilot.tools.repository import Repository


@pytest.fixture(autouse=True)
def fake_icd(monkeypatch: pytest.MonkeyPatch) -> None:
    codes = IcdCodeSet(frozenset({"J029", "I10"}), date(2026, 10, 1), date(2027, 9, 30))
    monkeypatch.setattr(ind, "load_icd_codes", lambda: codes)


def claim(
    cid: str, member: str = "m-a", provider: str = "p-a", code: str = "X0301"
) -> dict[str, Any]:
    return {
        "claim_id": cid,
        "member": {
            "member_id": member,
            "age_band": "40-49",
            "sex": "F",
            "plan_type": "PPO",
            "region": "R1",
        },
        "provider": {"provider_id": provider, "specialty": "S1", "region": "R1", "group_id": "G1"},
        "service_from": "2026-11-02",
        "service_to": "2026-11-02",
        "place_of_service": "PS1",
        "total_billed": "10.00",
        "diagnoses": ["J02.9"],
        "lines": [
            {
                "line_no": 1,
                "code": code,
                "units": 1,
                "billed_amount": "10.00",
                "service_date": "2026-11-02",
                "modifiers": [],
                "dx_pointer": 1,
            }
        ],
    }


def rules() -> dict[str, Any]:
    return {
        "procedure_codes": ["X0301", "X0302", "X0303", "X0304", "X0305", "X0306"],
        "visit_codes": ["X0001", "X0002", "X0003"],
        "bundle_pairs": [
            {
                "comprehensive_code": f"X030{i}",
                "component_code": f"X030{i + 1}",
                "exception_modifier": "M1",
            }
            for i in range(1, 6)
        ],
        "unit_limits": [{"code": f"X030{i}", "max_units": i} for i in range(1, 6)],
    }


def label(
    case_id: str, ids: list[str], kind: str = "excess_units", value: str = "TRUE"
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "type": kind,
        "label": value,
        "claim_ids": ids,
        "provider_id": None,
        "reason": "r",
    }


def good() -> ind.Delivery:
    claims = [claim("a1"), claim("a2", "m-b", "p-b")]
    labels = [label("c1", ["a1"]), label("c2", ["a2"], "clean", "CLEAN")]
    return ind.Delivery(claims, rules(), labels)


def test_a_consistent_delivery_has_no_problems() -> None:
    assert ind.validate(good()) == []


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        (lambda d: d.claims[1].update(claim_id="a1"), "duplicate claim id"),
        (lambda d: d.claims[0].update(total_billed="11.00"), "total_billed"),
        (lambda d: d.claims[0]["lines"][0].update(code="X9999"), "not declared"),
        (lambda d: d.claims[0].update(diagnoses=["Z99.9"]), "ICD-10-CM"),
        (lambda d: d.claims[0].update(place_of_service="PS9"), "place_of_service"),
        (lambda d: d.claims[0]["lines"][0].update(service_date="2028-01-01"), "FY2027"),
        (lambda d: d.labels[0].update(claim_ids=["nope"]), "not in claims.jsonl"),
        (lambda d: d.labels[1].update(claim_ids=["a1"]), "several cases"),
        (lambda d: d.labels[0].update(label="MAYBE"), "label"),
    ],
)
def test_each_kind_of_invalid_input_is_reported_not_repaired(
    edit: Callable[[ind.Delivery], object], expected: str
) -> None:
    d = copy.deepcopy(good())
    edit(d)
    problems = ind.validate(d)
    assert any(expected in p for p in problems), problems


def test_ids_are_renamed_mechanically_and_labels_stay_out_of_the_payer_store(
    tmp_path: Path,
) -> None:
    d = good()
    ids = ind.make_id_map(d)
    assert ids.claim == {"a1": "C0000001", "a2": "C0000002"}
    assert ids.member == {"m-a": "M000001", "m-b": "M000002"}
    assert ids.provider == {"p-a": "P0001", "p-b": "P0002"}
    ind.build_stores(d, tmp_path, ids)
    repo = Repository.open(tmp_path / "payer.sqlite")  # refuses truth-like tables and columns
    assert repo.claim_ids() == ["C0000001", "C0000002"]
    con = sqlite3.connect(tmp_path / "payer.sqlite")
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not tables & {"anomaly_truth", "truth_claim", "truth_line"}
    labels = sqlite3.connect(tmp_path / "truth.sqlite")
    assert labels.execute("SELECT claim_id FROM truth_claim").fetchall() == [("C0000001",)]
    assert ids.reverse()["C0000001"] == "a1"


def test_missing_files_are_reported(tmp_path: Path) -> None:
    d = ind.load_delivery(tmp_path)
    assert d.problems == [
        "missing file: claims.jsonl",
        "missing file: rules.json",
        "missing file: labels.jsonl",
    ]
