"""Provider-intensity v2 (EXPERIMENTAL): a volume-aware exact-binomial test against peers.

v1 (`tools.patterns.provider_intensity`) is untouched and stays the product default. v2 is
additive and is not wired into the API, dossier or agent. It exists to be tested on fresh data
against the registered gate in `eval/provider_intensity_v2_preregistration.json`; every constant
below was fixed in that file before any evaluation data was generated.

Method, per subject provider:
1. Peers are the same-specialty providers with at least `MIN_VISIT_LINES` visit lines, subject
   excluded. The subject needs `MIN_VISIT_LINES` too.
2. Baseline share `p0` is the peers' median high-level share, kept inside [P0_FLOOR, P0_CAP] so
   the test is defined when the median is 0 or 1.
3. Evidence: the one-sided exact binomial upper tail P(X >= x), X ~ Binomial(n, p0), where n is the
   subject's visit lines and x its highest-level lines. More volume, more evidence.
4. Multiplicity: Bonferroni over every eligible provider in the specialty (peers plus the subject),
   so the per-provider level is `ALPHA_FAMILY / m`.
5. Practical size: the subject's share must also be at least `MIN_GAP_ABOVE_P75` above the peers'
   75th percentile, so a tiny but significant excess on a huge volume is not raised.
6. Flag only if both hold. Otherwise no flag, or an explicit abstention with a reason.

A flag is a reason to look at the claims, not a conclusion about the provider.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from math import exp, lgamma, log
from typing import Literal

from claims_copilot.tools.errors import check_id
from claims_copilot.tools.patterns import PeerBook
from claims_copilot.tools.records import Finding, Ref, ToolResult
from claims_copilot.tools.repository import Repository, VisitMix

INTENSITY_V2_CHECK = "visit_mix_above_peer_range_v2"
MIN_VISIT_LINES = 40  # same volume floor as v1, so abstentions are comparable
MIN_PEERS = 20  # eligible same-specialty peers needed (v1 needs 10)
ALPHA_FAMILY = 0.05  # family-wise level, divided by the group size (Bonferroni)
P0_FLOOR = 0.02
P0_CAP = 0.98
MIN_GAP_ABOVE_P75 = 0.10  # absolute share points above the peer 75th percentile
PEER_MEDIAN_ABSTAIN_AT = 0.50  # a group that mostly bills the top level has no usable baseline

Decision = Literal["flag", "no_flag", "abstain"]
Abstention = Literal[
    "subject_not_found",
    "subject_below_min_volume",
    "too_few_peers",
    "peer_median_at_or_above_limit",
]


def binomial_upper_tail(n: int, x: int, p: float) -> float:
    """P(X >= x) for X ~ Binomial(n, p), summed in log space so large n does not overflow."""
    if x <= 0:
        return 1.0
    if x > n:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    log_p, log_q = log(p), log(1.0 - p)
    base = lgamma(n + 1)
    terms = [
        base - lgamma(k + 1) - lgamma(n - k + 1) + k * log_p + (n - k) * log_q
        for k in range(x, n + 1)
    ]
    top = max(terms)
    return min(1.0, exp(top) * sum(exp(t - top) for t in terms))


@dataclass(frozen=True)
class Assessment:
    decision: Decision
    abstention: Abstention | None
    subject_lines: int
    subject_high_lines: int
    subject_share: float
    peer_count: int
    multiplicity: int
    peer_median: float
    p0_used: float
    peer_p75: float
    gap_above_p75: float
    p_value: float
    alpha_adjusted: float


def _abstain(reason: Abstention, subject: VisitMix | None, peer_count: int) -> Assessment:
    n = subject.visit_lines if subject else 0
    h = subject.high_lines if subject else 0
    return Assessment(
        "abstain",
        reason,
        n,
        h,
        subject.high_share if subject else 0.0,
        peer_count,
        0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
    )


def assess(subject: VisitMix | None, all_mixes: list[VisitMix]) -> Assessment:
    """Pure decision for one subject given every provider's visit mix (any specialty)."""
    if subject is None or subject.visit_lines == 0:
        return _abstain("subject_not_found", subject, 0)
    peers = [
        m
        for m in all_mixes
        if m.specialty == subject.specialty
        and m.provider_id != subject.provider_id
        and m.visit_lines >= MIN_VISIT_LINES
    ]
    if subject.visit_lines < MIN_VISIT_LINES:
        return _abstain("subject_below_min_volume", subject, len(peers))
    if len(peers) < MIN_PEERS:
        return _abstain("too_few_peers", subject, len(peers))
    shares = sorted(m.high_share for m in peers)
    median = statistics.median(shares)
    if median >= PEER_MEDIAN_ABSTAIN_AT:
        return _abstain("peer_median_at_or_above_limit", subject, len(peers))
    p75 = statistics.quantiles(shares, n=4, method="inclusive")[2]
    p0 = min(max(median, P0_FLOOR), P0_CAP)
    m_tests = len(peers) + 1
    alpha_adj = ALPHA_FAMILY / m_tests
    p_value = binomial_upper_tail(subject.visit_lines, subject.high_lines, p0)
    gap = subject.high_share - p75
    flagged = p_value <= alpha_adj and gap >= MIN_GAP_ABOVE_P75
    return Assessment(
        "flag" if flagged else "no_flag",
        None,
        subject.visit_lines,
        subject.high_lines,
        subject.high_share,
        len(peers),
        m_tests,
        median,
        p0,
        p75,
        gap,
        p_value,
        alpha_adj,
    )


def provider_intensity_v2(
    repo: Repository, provider_id: str, book: PeerBook | None = None
) -> ToolResult:
    pid = check_id("provider", provider_id)
    repo.provider(pid)  # raises if the provider does not exist, like v1
    mixes = list(book.by_provider.values()) if book else repo.visit_mix()
    subject = next((m for m in mixes if m.provider_id == pid), None)
    a = assess(subject, mixes)
    params = (
        ("version", "v2 (experimental; v1 remains the default)"),
        ("statistic", "one-sided exact binomial upper tail vs peer-median high-level share"),
        ("min_visit_lines", str(MIN_VISIT_LINES)),
        ("min_peers", str(MIN_PEERS)),
        ("alpha_family", str(ALPHA_FAMILY)),
        ("multiplicity", "Bonferroni over eligible providers in the specialty"),
        ("min_gap_above_p75", str(MIN_GAP_ABOVE_P75)),
        ("p0_floor", str(P0_FLOOR)),
        ("p0_cap", str(P0_CAP)),
        ("peer_median_abstain_at", str(PEER_MEDIAN_ABSTAIN_AT)),
    )
    limits = [
        "A flag is a reason to look at the claims, not a conclusion about the provider.",
        "Experimental: exact-binomial evidence assumes visits are independent; "
        "Bonferroni multiplicity is conservative; the baseline is the peer median share.",
    ]
    if a.decision == "abstain":
        reason = a.abstention or "subject_not_found"
        limits.append(f"Abstained: {reason}.")
        return ToolResult(
            tool="provider_intensity_v2",
            subject=pid,
            examined=f"{a.subject_lines} visit lines; {a.peer_count} eligible peers",
            findings=(),
            metrics=(("decision", "abstain"), ("abstention_reason", reason)),
            parameters=params,
            limits=tuple(limits),
        )
    metrics = (
        ("decision", a.decision),
        ("provider_high_share", f"{a.subject_share:.3f}"),
        ("provider_visit_lines", str(a.subject_lines)),
        ("provider_high_lines", str(a.subject_high_lines)),
        ("peer_count", str(a.peer_count)),
        ("multiplicity_m", str(a.multiplicity)),
        ("peer_median_share", f"{a.peer_median:.3f}"),
        ("p0_used", f"{a.p0_used:.3f}"),
        ("peer_p75_share", f"{a.peer_p75:.3f}"),
        ("gap_above_p75", f"{a.gap_above_p75:.3f}"),
        ("p_value", f"{a.p_value:.3e}"),
        ("alpha_adjusted", f"{a.alpha_adjusted:.3e}"),
    )
    findings: tuple[Finding, ...] = ()
    if a.decision == "flag":
        findings = (
            Finding(
                INTENSITY_V2_CHECK,
                f"Provider {pid} bills {a.subject_share:.0%} of {a.subject_lines} visit lines at "
                f"the highest visit level; same-specialty peers' median is {a.peer_median:.0%} "
                f"and their 75th percentile {a.peer_p75:.0%} (exact tail probability "
                f"{a.p_value:.1e} against a corrected level of {a.alpha_adjusted:.1e}).",
                (Ref("provider", pid),),
                metrics,
            ),
        )
    return ToolResult(
        tool="provider_intensity_v2",
        subject=pid,
        examined=(
            f"{a.subject_lines} visit lines for the provider; {a.peer_count} peers with at least "
            f"{MIN_VISIT_LINES} visit lines"
        ),
        findings=findings,
        metrics=metrics,
        parameters=params,
        limits=tuple(limits),
    )
