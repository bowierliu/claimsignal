from __future__ import annotations

from pathlib import Path

from claims_copilot.tools.patterns import (
    INTENSITY_CHECK,
    MIN_PEERS,
    PeerBook,
    modified_z,
    provider_intensity,
    provider_peer_group,
)
from claims_copilot.tools.repository import Repository
from tool_fixtures import Db, L

VISITS = 40


def add_provider(
    db: Db, provider: str, high: int, total: int = VISITS, spec: str = "cardio"
) -> None:
    """A provider with `total` single-line visit claims, `high` of them at the top level."""
    for i in range(total):
        code = "X0003" if i < high else "X0001"
        db.claim(
            f"C{provider[1:]}{i:03d}",
            [L(code)],
            provider=provider,
            specialty=spec,
            member=f"M{i:06d}",
        )


def build(
    tmp_path: Path, subject_high: int, peers: int = 12, peer_highs: list[int] | None = None
) -> Repository:
    db = Db(tmp_path / "p.sqlite")
    highs = peer_highs or [3 + (i % 4) for i in range(peers)]  # 3..6 of 40: 7.5% to 15%
    for i, h in enumerate(highs):
        add_provider(db, f"P{i + 10:04d}", h)
    add_provider(db, "P0001", subject_high)
    return db.open()


def test_modified_z_matches_the_published_formula() -> None:
    assert round(modified_z(0.6, 0.1, 0.05), 3) == round(0.6745 * 0.5 / 0.05, 3)


def test_a_clearly_high_provider_is_a_finding_with_its_numbers(tmp_path: Path) -> None:
    repo = build(tmp_path, subject_high=24)
    res = provider_intensity(repo, "P0001")
    assert [f.check for f in res.findings] == [INTENSITY_CHECK]
    metrics = dict(res.metrics)
    assert metrics["provider_high_share"] == "0.600"
    assert metrics["peer_count"] == "12"
    assert metrics["peer_specialty"] == "cardio"
    assert float(metrics["score"]) > 3.5
    assert any("not a conclusion" in s for s in res.limits)


def test_a_moderately_high_provider_is_not_a_finding(tmp_path: Path) -> None:
    repo = build(tmp_path, subject_high=8)  # 20% against peers at 7.5% to 15%
    res = provider_intensity(repo, "P0001")
    assert res.findings == ()
    assert float(dict(res.metrics)["score"]) < 3.5


def test_the_subject_is_left_out_of_its_own_peer_group(tmp_path: Path) -> None:
    repo = build(tmp_path, subject_high=24)
    book = PeerBook.from_repo(repo)
    stats, peers = book.stats_for("P0001", "cardio")
    assert stats is not None and len(peers) == 12
    assert all(p.provider_id != "P0001" for p in peers)
    assert stats.median < 0.15  # the subject's 0.60 did not move it


def test_too_few_visit_lines_means_not_scored(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    for i in range(12):
        add_provider(db, f"P{i + 10:04d}", 4)
    add_provider(db, "P0001", 10, total=39)
    repo = db.open()
    res = provider_intensity(repo, "P0001")
    assert res.findings == () and res.metrics == ()
    assert any("Not scored" in s for s in res.limits)


def test_too_few_peers_means_not_scored(tmp_path: Path) -> None:
    repo = build(tmp_path, subject_high=30, peers=MIN_PEERS - 1)
    res = provider_intensity(repo, "P0001")
    assert res.findings == () and res.metrics == ()
    assert any("fewer than 10 peers" in s for s in res.limits)


def test_peers_in_other_specialties_are_not_used(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    for i in range(12):
        add_provider(db, f"P{i + 10:04d}", 4, spec="ortho")
    add_provider(db, "P0001", 30, spec="cardio")
    repo = db.open()
    assert any("fewer than 10 peers" in s for s in provider_intensity(repo, "P0001").limits)


def test_elevated_peers_are_counted_and_the_baseline_is_called_shaky(tmp_path: Path) -> None:
    highs = [3 + (i % 4) for i in range(8)] + [25, 26, 27, 28]  # 4 of 12 peers elevated
    repo = build(tmp_path, subject_high=24, peer_highs=highs)
    res = provider_intensity(repo, "P0001")
    metrics = dict(res.metrics)
    assert int(metrics["peer_elevated_count"]) >= 3
    assert any("themselves elevated" in s for s in res.limits)


def test_peer_group_report_lists_highest_peers_first(tmp_path: Path) -> None:
    repo = build(tmp_path, subject_high=24)
    rep = provider_peer_group(repo, "P0001", limit=3)
    assert rep.peer_count == 12 and len(rep.peers) == 3
    shares = [p.high_share for p in rep.peers]
    assert shares == sorted(shares, reverse=True)
    assert rep.stats is not None and rep.subject_share == 0.6
