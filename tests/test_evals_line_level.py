"""Line-level evaluation: extension validation, line citation comparison, outcome classes."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from claims_copilot.evals import independent as ind
from claims_copilot.evals import line_level as ll
from claims_copilot.tools.icd import IcdCodeSet
from claims_copilot.tools.repository import Repository


@pytest.fixture(autouse=True)
def fake_icd(monkeypatch: pytest.MonkeyPatch) -> None:
    codes = IcdCodeSet(frozenset({"J029", "I10"}), date(2026, 10, 1), date(2027, 9, 30))
    monkeypatch.setattr(ind, "load_icd_codes", lambda: codes)


def line(n: int, code: str, units: int) -> dict[str, Any]:
    return {
        "line_no": n,
        "code": code,
        "units": units,
        "billed_amount": "10.00",
        "service_date": "2026-11-02",
        "modifiers": [],
        "dx_pointer": 1,
    }


def claim(cid: str, lines: list[dict[str, Any]], member: str, provider: str) -> dict[str, Any]:
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
        "total_billed": f"{10 * len(lines)}.00",
        "diagnoses": ["J02.9"],
        "lines": lines,
    }


def rules() -> dict[str, Any]:
    return {
        "procedure_codes": [f"X030{i}" for i in range(1, 7)],
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


def ref(cid: str, n: int) -> dict[str, Any]:
    return {"claim_id": cid, "line_no": n}


def lab(
    case_id: str,
    cid: str,
    typ: str,
    label: str,
    kind: str,
    refs: list[int],
    tempting: list[int],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "type": typ,
        "label": label,
        "claim_ids": [cid],
        "provider_id": None,
        "reason": "r",
        "case_kind": kind,
        "line_refs": [ref(cid, n) for n in refs],
        "tempting_line_refs": [ref(cid, n) for n in tempting],
    }


def good() -> ll.LineDelivery:
    claims = [
        # line 2 is over its limit (X0302 allows 2); line 3 sits exactly at its limit.
        claim("a1", [line(1, "X0301", 1), line(2, "X0302", 5), line(3, "X0303", 3)], "m1", "p1"),
        # author points at the wrong line (line 1); the tool will cite line 2.
        claim("a2", [line(1, "X0301", 1), line(2, "X0302", 9)], "m2", "p1"),
        # near miss: every line at its limit.
        claim("a3", [line(1, "X0302", 2), line(2, "X0303", 3)], "m3", "p2"),
        # clean claim.
        claim("a4", [line(1, "X0301", 1), line(2, "X0304", 1)], "m4", "p2"),
    ]
    labels = [
        lab("c1", "a1", "excess_units", "TRUE", "multi_line", [2], [3]),
        lab("c2", "a2", "excess_units", "TRUE", "standard", [1], []),
        lab("c3", "a3", "excess_units", "DECOY", "near_miss", [], [1, 2]),
        lab("c4", "a4", "clean", "CLEAN", "standard", [], []),
    ]
    return ll.LineDelivery(
        ind.Delivery(claims, rules(), [{k: r[k] for k in ll.BASE_KEYS} for r in labels]),
        {str(r["case_id"]): {k: r[k] for k in ll.EXT_KEYS} for r in labels},
        [],
    )


def test_valid_delivery_has_no_schema_problems() -> None:
    assert ll.validate(good()).schema_problems == []


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        (lambda d: d.ext["c1"].update(line_refs=[]), "non-empty for TRUE"),
        (lambda d: d.ext["c3"].update(line_refs=[ref("a3", 1)]), "non-empty for TRUE"),
        (lambda d: d.ext["c1"].update(line_refs=[ref("a1", 9)]), "not a line of the case"),
        (lambda d: d.ext["c1"].update(tempting_line_refs=[ref("a1", 2)]), "both a reference"),
        (lambda d: d.ext["c1"].update(case_kind="weird"), "case_kind"),
        (lambda d: d.ext["c1"].update(line_refs=[{"claim_id": "a1"}]), "lists of claim_id"),
        (lambda d: d.delivery.labels[0].update(type="duplicate_claim"), "not line-level"),
        (lambda d: d.delivery.claims[3].update(lines=d.delivery.claims[3]["lines"][:1]), "two"),
    ],
)
def test_extension_problems_are_reported_not_repaired(
    edit: Callable[[ll.LineDelivery], object], expected: str
) -> None:
    d = copy.deepcopy(good())
    edit(d)
    if expected == "two":  # keep the claim internally consistent so only the new rule fires
        d.delivery.claims[3]["total_billed"] = "10.00"
    problems = ll.validate(d).schema_problems
    assert any(expected in p for p in problems), problems


def test_requirement_gaps_are_listed_when_the_brief_quota_is_not_met() -> None:
    gaps = ll.validate(good()).requirement_gaps
    assert any("TRUE cases (brief asks for 12)" in g for g in gaps)


def test_loader_rejects_wrong_label_keys_and_splits_extension(tmp_path: Path) -> None:
    d = good()
    (tmp_path / "claims.jsonl").write_text("".join(json.dumps(c) + "\n" for c in d.delivery.claims))
    (tmp_path / "rules.json").write_text(json.dumps(d.delivery.rules))
    rows = [{**r, **d.ext[str(r["case_id"])]} for r in d.delivery.labels]
    (tmp_path / "labels.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    loaded = ll.load(tmp_path)
    assert loaded.problems == [] and set(loaded.ext) == {"c1", "c2", "c3", "c4"}
    assert set(loaded.delivery.labels[0]) == ll.BASE_KEYS
    rows[0].pop("line_refs")
    (tmp_path / "labels.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert any("wrong keys" in p for p in ll.load(tmp_path).problems)


def test_scoring_compares_cited_lines_with_the_authors_lines(tmp_path: Path) -> None:
    d = good()
    ids = ind.make_id_map(d.delivery)
    ind.build_stores(d.delivery, tmp_path, ids)
    report = ll.score(d, Repository.open(tmp_path / "payer.sqlite"), ids)
    rows = {r["case_id"]: r for r in report["per_case"]}
    assert rows["c1"]["cited_lines"] == [2] and rows["c1"]["outcome"] == "exact"
    assert rows["c2"]["cited_lines"] == [2] and rows["c2"]["outcome"] == "wrong_lines_only"
    assert rows["c3"]["outcome"] == "not_flagged" and rows["c3"]["cited_lines"] == []
    pooled = report["pooled"]
    assert pooled["true_cases"] == 2 and pooled["expected_lines"] == 2
    assert pooled["line_recall"]["k"] == 1 and pooled["line_precision"]["k"] == 1
    assert pooled["line_precision"]["n"] == 2
    assert pooled["exact_match_rate"]["k"] == 1
    assert pooled["over_cited_lines"] == 1
    assert report["clean_claims"]["claims_with_cited_lines"] == 0


@pytest.mark.parametrize(
    ("expected", "cited", "flagged", "outcome"),
    [
        ({("a", 1)}, {("a", 1)}, True, "exact"),
        ({("a", 1)}, set(), False, "missed_claim"),
        ({("a", 1)}, set(), True, "flagged_without_line_refs"),
        ({("a", 1)}, {("a", 2)}, True, "wrong_lines_only"),
        ({("a", 1)}, {("a", 1), ("a", 2)}, True, "over_cited"),
        ({("a", 1), ("a", 2)}, {("a", 1)}, True, "missed_some_lines"),
        ({("a", 1), ("a", 2)}, {("a", 1), ("a", 3)}, True, "missed_some_and_over_cited"),
    ],
)
def test_outcome_classes(
    expected: set[ll.Ref], cited: set[ll.Ref], flagged: bool, outcome: str
) -> None:
    assert ll.classify(expected, cited, flagged) == outcome
