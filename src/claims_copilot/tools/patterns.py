"""Billing-pattern statistics: a provider's visit-level mix against same-specialty peers.

Statistic: the share of a provider's visit-family lines billed at the highest visit level.
Comparison: the modified z-score (Iglewicz and Hoaglin), 0.6745 * (x - median) / MAD, against the
provider's same-specialty peers, with the subject left out of its own peer group. Median and MAD
(median absolute deviation) are used because a few elevated peers should not move the baseline.
That protection has a limit (KF-014): when many peers are themselves elevated, the median rises
and MAD widens. So every result reports the peer-group size, its median and MAD, and how many
peers are elevated, and a provider or group that is too small is not scored at all.

The 3.5 cutoff is the usual published one for this statistic. It was fixed from the definition,
not from the synthetic labels. A high score is a reason to look, not a conclusion.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from claims_copilot.tools.errors import check_id, check_limit
from claims_copilot.tools.records import Finding, Ref, ToolResult
from claims_copilot.tools.repository import Repository, VisitMix

INTENSITY_CHECK = "visit_mix_above_peer_range"
MIN_VISIT_LINES = 40  # visit lines a provider needs before it is scored or used as a peer
MIN_PEERS = 10  # peers needed before a score is given
Z_THRESHOLD = 3.5
MAD_FLOOR = 0.02  # stops a near-zero MAD from inflating scores; units are share (0 to 1)
MAD_SCALE = 0.6745
PEER_LIST_DEFAULT = 10
CONTAMINATION_NOTE_AT = 0.2  # share of elevated peers above which the baseline is called shaky


@dataclass(frozen=True)
class PeerStats:
    size: int
    median: float
    mad: float
    mad_used: float  # MAD after the floor
    elevated: int  # peers whose own score is at or above the threshold

    @property
    def elevated_fraction(self) -> float:
        return self.elevated / self.size if self.size else 0.0


@dataclass(frozen=True)
class PeerRow:
    provider_id: str
    visit_lines: int
    high_share: float
    score: float


@dataclass(frozen=True)
class PeerGroupReport:
    provider_id: str
    specialty: str
    subject_visit_lines: int
    subject_share: float
    stats: PeerStats | None  # None when the group is too small to describe
    peers: tuple[PeerRow, ...]  # highest share first, at most the requested number
    peer_count: int
    limits: tuple[str, ...]


def modified_z(value: float, median: float, mad_used: float) -> float:
    return MAD_SCALE * (value - median) / mad_used


def _stats(shares: list[float]) -> PeerStats:
    median = statistics.median(shares)
    mad = statistics.median(abs(s - median) for s in shares)
    used = max(mad, MAD_FLOOR)
    elevated = sum(1 for s in shares if modified_z(s, median, used) >= Z_THRESHOLD)
    return PeerStats(len(shares), median, mad, used, elevated)


class PeerBook:
    """Visit mix for every provider, built once so many providers can be scored cheaply."""

    def __init__(self, mixes: list[VisitMix], min_visit_lines: int = MIN_VISIT_LINES) -> None:
        self.min_visit_lines = min_visit_lines
        self.by_provider = {m.provider_id: m for m in mixes}
        self._eligible: dict[str, list[VisitMix]] = {}
        for m in mixes:
            if m.visit_lines >= min_visit_lines:
                self._eligible.setdefault(m.specialty, []).append(m)

    @classmethod
    def from_repo(cls, repo: Repository, min_visit_lines: int = MIN_VISIT_LINES) -> PeerBook:
        return cls(repo.visit_mix(), min_visit_lines)

    def peers_of(self, provider_id: str, specialty: str) -> list[VisitMix]:
        return [m for m in self._eligible.get(specialty, []) if m.provider_id != provider_id]

    def stats_for(
        self, provider_id: str, specialty: str
    ) -> tuple[PeerStats | None, list[VisitMix]]:
        peers = self.peers_of(provider_id, specialty)
        if len(peers) < MIN_PEERS:
            return None, peers
        return _stats([p.high_share for p in peers]), peers


def provider_intensity(
    repo: Repository,
    provider_id: str,
    book: PeerBook | None = None,
    z_threshold: float = Z_THRESHOLD,
) -> ToolResult:
    pid = check_id("provider", provider_id)
    provider = repo.provider(pid)
    book = book or PeerBook.from_repo(repo)
    mix = book.by_provider.get(pid)
    params = (
        ("statistic", "share of visit lines at the highest visit level"),
        ("score", "modified z against same-specialty peers, subject excluded"),
        ("z_threshold", str(z_threshold)),
        ("min_visit_lines", str(book.min_visit_lines)),
        ("min_peers", str(MIN_PEERS)),
        ("mad_floor", str(MAD_FLOOR)),
    )
    if mix is None or mix.visit_lines < book.min_visit_lines:
        n = mix.visit_lines if mix else 0
        reason = f"fewer than {book.min_visit_lines} visit lines"
        return ToolResult(
            tool="provider_intensity",
            subject=pid,
            examined=f"{n} visit lines billed by this provider",
            findings=(),
            parameters=params,
            limits=(f"Not scored: {reason}.",),
            status_reason=reason,
        )
    stats, peers = book.stats_for(pid, provider.specialty)
    if stats is None:
        reason = f"fewer than {MIN_PEERS} peers in {provider.specialty}"
        return ToolResult(
            tool="provider_intensity",
            subject=pid,
            examined=f"{mix.visit_lines} visit lines; {len(peers)} eligible peers",
            findings=(),
            parameters=params,
            limits=(f"Not scored: {reason}.",),
            status_reason=reason,
        )
    score = modified_z(mix.high_share, stats.median, stats.mad_used)
    metrics = (
        ("provider_high_share", f"{mix.high_share:.3f}"),
        ("provider_visit_lines", str(mix.visit_lines)),
        ("peer_specialty", provider.specialty),
        ("peer_count", str(stats.size)),
        ("peer_median_share", f"{stats.median:.3f}"),
        ("peer_mad", f"{stats.mad:.3f}"),
        ("peer_elevated_count", str(stats.elevated)),
        ("score", f"{score:.2f}"),
    )
    limits = ["A score is a reason to look at the claims, not a conclusion about the provider."]
    if stats.elevated_fraction >= CONTAMINATION_NOTE_AT:
        limits.append(
            f"{stats.elevated} of {stats.size} peers are themselves elevated, so the peer median "
            f"is raised and scores are understated."
        )
    findings: tuple[Finding, ...] = ()
    if score >= z_threshold:
        findings = (
            Finding(
                INTENSITY_CHECK,
                f"Provider {pid} bills {mix.high_share:.0%} of {mix.visit_lines} visit lines at "
                f"the highest visit level; same-specialty peers' median is {stats.median:.0%} "
                f"(score {score:.1f}, cutoff {z_threshold}).",
                (Ref("provider", pid),),
                metrics,
            ),
        )
    return ToolResult(
        tool="provider_intensity",
        subject=pid,
        examined=(
            f"{mix.visit_lines} visit lines for the provider; {stats.size} {provider.specialty} "
            f"peers with at least {book.min_visit_lines} visit lines"
        ),
        findings=findings,
        metrics=metrics,
        parameters=params,
        limits=tuple(limits),
    )


def provider_peer_group(
    repo: Repository,
    provider_id: str,
    book: PeerBook | None = None,
    limit: int = PEER_LIST_DEFAULT,
) -> PeerGroupReport:
    pid = check_id("provider", provider_id)
    n = check_limit(limit)
    provider = repo.provider(pid)
    book = book or PeerBook.from_repo(repo)
    mix = book.by_provider.get(pid)
    stats, peers = book.stats_for(pid, provider.specialty)
    rows: list[PeerRow] = []
    for p in peers:
        score = modified_z(p.high_share, stats.median, stats.mad_used) if stats else 0.0
        rows.append(PeerRow(p.provider_id, p.visit_lines, p.high_share, score))
    rows.sort(key=lambda r: (-r.high_share, r.provider_id))
    limits: tuple[str, ...] = ()
    if stats is None:
        limits = (f"Fewer than {MIN_PEERS} eligible peers; group statistics are not given.",)
    return PeerGroupReport(
        provider_id=pid,
        specialty=provider.specialty,
        subject_visit_lines=mix.visit_lines if mix else 0,
        subject_share=mix.high_share if mix else 0.0,
        stats=stats,
        peers=tuple(rows[:n]),
        peer_count=len(peers),
        limits=limits,
    )
