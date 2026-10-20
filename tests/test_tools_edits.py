from __future__ import annotations

from pathlib import Path

from claims_copilot.tools.edits import (
    BUNDLE_CHECK,
    DATE_CHECK,
    UNIT_CHECK,
    WINDOW_CHECK,
    check_bundling,
    check_service_dates,
    check_unit_limits,
)
from tool_fixtures import Db, L, rules_for


def test_bundle_pair_without_modifier_is_a_finding(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0010"), L("X0011")])
    repo = db.open()
    res = check_bundling(repo, rules_for(repo), "C0000001")
    assert [f.check for f in res.findings] == [BUNDLE_CHECK]
    finding = res.findings[0]
    assert finding.ids("line") == ("C0000001-02", "C0000001-01")
    assert ("rule", "bundle_pair:X0010+X0011") in [(r.kind, r.id) for r in finding.refs]
    assert res.observations == ()


def test_exception_modifier_clears_the_rule_but_is_still_shown(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0010"), L("X0011", mods=("M1",))])
    repo = db.open()
    res = check_bundling(repo, rules_for(repo), "C0000001")
    assert res.findings == ()
    assert [o.check for o in res.observations] == ["bundle_pair_with_exception"]


def test_pair_on_different_dates_is_not_bundled(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0010"), L("X0011", day="2026-11-03")], end="2026-11-03")
    repo = db.open()
    assert check_bundling(repo, rules_for(repo), "C0000001").findings == ()


def test_pair_split_across_claims_is_not_checked(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0010")])
    db.claim("C0000002", [L("X0011")])
    repo = db.open()
    res = check_bundling(repo, rules_for(repo), "C0000002")
    assert res.findings == ()
    assert any("one claim and one service date" in s for s in res.limits)


def test_component_alone_or_unrelated_codes_trip_nothing(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0011"), L("X0001")])
    repo = db.open()
    assert check_bundling(repo, rules_for(repo), "C0000001").findings == ()


def test_units_above_limit_is_a_finding_and_at_limit_is_not(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0020", units=3)])
    db.claim("C0000002", [L("X0020", units=2)])
    db.claim("C0000003", [L("X0001", units=50)])  # no limit defined for this code
    repo = db.open()
    rules = rules_for(repo)
    over = check_unit_limits(repo, rules, "C0000001")
    assert [f.check for f in over.findings] == [UNIT_CHECK]
    assert dict(over.findings[0].detail)["over_by"] == "1"
    assert check_unit_limits(repo, rules, "C0000002").findings == ()
    unlimited = check_unit_limits(repo, rules, "C0000003")
    assert unlimited.findings == () and "0 have a unit limit" in unlimited.examined


def test_units_are_checked_per_line_not_summed(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0020", units=2), L("X0020", units=2)])
    repo = db.open()
    res = check_unit_limits(repo, rules_for(repo), "C0000001")
    assert res.findings == ()
    assert any("single line" in s for s in res.limits)


def test_dates_before_and_after_the_window_are_findings(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim(
        "C0000001",
        [L("X0001", day="2026-10-20"), L("X0002", day="2026-12-01"), L("X0003")],
        start="2026-11-02",
        end="2026-11-04",
    )
    repo = db.open()
    res = check_service_dates(repo, "C0000001")
    assert [f.check for f in res.findings] == [DATE_CHECK, DATE_CHECK]
    assert [dict(f.detail)["side"] for f in res.findings] == ["before", "after"]
    assert [dict(f.detail)["days_outside"] for f in res.findings] == ["13", "27"]


def test_window_boundaries_are_inclusive(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim(
        "C0000001",
        [L("X0001", day="2026-11-02"), L("X0002", day="2026-11-04")],
        start="2026-11-02",
        end="2026-11-04",
    )
    repo = db.open()
    assert check_service_dates(repo, "C0000001").findings == ()


def test_reversed_window_is_a_finding(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0001")], start="2026-11-05", end="2026-11-02")
    repo = db.open()
    res = check_service_dates(repo, "C0000001")
    assert WINDOW_CHECK in [f.check for f in res.findings]
