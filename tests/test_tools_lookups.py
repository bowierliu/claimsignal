from __future__ import annotations

from pathlib import Path

import pytest

from claims_copilot.tools.errors import NotFoundError, ToolInputError
from claims_copilot.tools.lookups import (
    get_claim,
    get_flags,
    get_member_history,
    get_provider_profile,
)
from tool_fixtures import Db, L


@pytest.fixture
def repo(tmp_path: Path):  # type: ignore[no-untyped-def]
    db = Db(tmp_path / "payer.sqlite")
    db.claim("C0000001", [L("X0001", mods=("M2", "M3")), L("X0010")], start="2026-11-02")
    db.claim("C0000002", [L("X0002")], start="2026-11-09")
    db.claim("C0000003", [L("X0003")], member="M000002", provider="P0002", start="2026-11-12")
    db.flag("F000001", "C0000001", "SCR02")
    db.flag("F000002", "C0000003", "SCR04")
    db.flag("F000003", "C0000002", "SCR02")
    return db.open()


def test_get_claim_returns_lines_modifiers_and_flags(repo) -> None:  # type: ignore[no-untyped-def]
    rec = get_claim(repo, "C0000001")
    assert [ln.code for ln in rec.lines] == ["X0001", "X0010"]
    assert rec.lines[0].modifiers == ("M2", "M3")
    assert rec.claim.diagnosis_codes == ("E119",)
    assert [f.screen_code for f in rec.flags] == ["SCR02"]
    assert [(r.kind, r.id) for r in rec.refs()] == [
        ("claim", "C0000001"),
        ("line", "C0000001-01"),
        ("line", "C0000001-02"),
    ]


def test_get_claim_rejects_bad_and_unknown_ids(repo) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ToolInputError):
        get_claim(repo, "C1")
    with pytest.raises(NotFoundError):
        get_claim(repo, "C0000099")


def test_member_history_is_oldest_first_and_reports_truncation(repo) -> None:  # type: ignore[no-untyped-def]
    full = get_member_history(repo, "M000001")
    assert [c.claim_id for c in full.claims] == ["C0000001", "C0000002"]
    assert not full.truncated and full.total_claims == 2
    short = get_member_history(repo, "M000001", limit=1)
    assert [c.claim_id for c in short.claims] == ["C0000001"]
    assert short.truncated and short.total_claims == 2
    with pytest.raises(NotFoundError):
        get_member_history(repo, "M000099")


def test_provider_profile_counts(repo) -> None:  # type: ignore[no-untyped-def]
    prof = get_provider_profile(repo, "P0001")
    assert (prof.claim_count, prof.line_count) == (2, 3)
    assert str(prof.total_billed) == "200.00"
    assert prof.flagged_claim_count == 2
    assert prof.provider.specialty == "primary_care"


def test_flag_queue_filters_and_limits(repo) -> None:  # type: ignore[no-untyped-def]
    assert get_flags(repo).total == 3
    scr2 = get_flags(repo, "SCR02")
    assert [f.flag_id for f in scr2.flags] == ["F000001", "F000003"]
    capped = get_flags(repo, limit=1)
    assert len(capped.flags) == 1 and capped.truncated
    with pytest.raises(ToolInputError):
        get_flags(repo, "'; DROP TABLE flag")
