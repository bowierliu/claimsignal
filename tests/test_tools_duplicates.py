from __future__ import annotations

from pathlib import Path

from claims_copilot.tools.duplicates import (
    EXACT_CHECK,
    NEAR_DATE,
    NEAR_PROVIDER,
    find_duplicate_candidates,
)
from tool_fixtures import Db, L


def _db(tmp_path: Path) -> Db:
    return Db(tmp_path / "p.sqlite")


def test_exact_duplicate_is_found_from_either_side(tmp_path: Path) -> None:
    db = _db(tmp_path)
    lines = [L("X0010"), L("X0001", mods=("M2",))]
    db.claim("C0000001", lines)
    db.claim("C0000002", lines)
    repo = db.open()
    for me, other in (("C0000001", "C0000002"), ("C0000002", "C0000001")):
        res = find_duplicate_candidates(repo, me)
        assert [f.check for f in res.findings] == [EXACT_CHECK]
        assert ("claim", other) in [(r.kind, r.id) for r in res.findings[0].refs]


def test_line_order_does_not_matter(tmp_path: Path) -> None:
    db = _db(tmp_path)
    db.claim("C0000001", [L("X0010"), L("X0001")])
    db.claim("C0000002", [L("X0001"), L("X0010")])
    repo = db.open()
    assert len(find_duplicate_candidates(repo, "C0000001").findings) == 1


def test_different_units_or_modifiers_are_not_exact(tmp_path: Path) -> None:
    db = _db(tmp_path)
    db.claim("C0000001", [L("X0020", units=1)])
    db.claim("C0000002", [L("X0020", units=2)])
    db.claim("C0000003", [L("X0020", units=1, mods=("M2",))])
    repo = db.open()
    assert find_duplicate_candidates(repo, "C0000001").findings == ()


def test_same_services_by_another_provider_is_an_observation_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    db.claim("C0000001", [L("X0010")])
    db.claim("C0000002", [L("X0010")], provider="P0002")
    repo = db.open()
    res = find_duplicate_candidates(repo, "C0000001")
    assert res.findings == ()
    assert [o.check for o in res.observations] == [NEAR_PROVIDER]


def test_same_services_on_a_nearby_date_is_an_observation_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    db.claim("C0000001", [L("X0010")], start="2026-11-02")
    db.claim("C0000002", [L("X0010")], start="2026-11-20")
    db.claim("C0000003", [L("X0010")], start="2027-03-01")  # far away: not even near
    repo = db.open()
    res = find_duplicate_candidates(repo, "C0000001")
    assert res.findings == ()
    assert [o.check for o in res.observations] == [NEAR_DATE]
    assert dict(res.parameters)["near_match_days"] == "30"


def test_other_members_never_match(tmp_path: Path) -> None:
    db = _db(tmp_path)
    db.claim("C0000001", [L("X0010")])
    db.claim("C0000002", [L("X0010")], member="M000002")
    repo = db.open()
    res = find_duplicate_candidates(repo, "C0000001")
    assert res.findings == () and res.observations == ()


def test_a_claim_is_not_its_own_duplicate(tmp_path: Path) -> None:
    db = _db(tmp_path)
    db.claim("C0000001", [L("X0010")])
    repo = db.open()
    res = find_duplicate_candidates(repo, "C0000001")
    assert res.findings == () and "0 other claims" in res.examined
