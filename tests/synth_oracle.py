"""Independent reference checker for the five synthetic anomaly types.

Written separately from the generator on purpose: it sees only plain rows and the rule tables, and
re-derives what is wrong. If the generator's labels and this checker agree, the labels are at
least internally consistent (this proves consistency, not realism; see KNOWN_FAILURES.md).
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from claims_copilot.synth.models import (
    BundlePair,
    Claim,
    ClaimLine,
    ProcedureCode,
    Provider,
    UnitLimit,
)

OUTLIER_FLOOR = 0.45
OUTLIER_MEDIAN_MULTIPLE = 2.0  # was 3.0 until full-scale data showed it too strict (KF-014)


@dataclass(frozen=True)
class Findings:
    duplicates: frozenset[frozenset[str]]  # each item is a set of claim ids billed identically
    unbundled_lines: frozenset[str]  # component line ids billed with the comprehensive code
    excess_unit_lines: frozenset[str]
    out_of_window_lines: frozenset[str]
    outlier_providers: frozenset[str]


def find_anomalies(
    claims: Iterable[Claim],
    lines: Iterable[ClaimLine],
    pairs: Iterable[BundlePair],
    limits: Iterable[UnitLimit],
    providers: Iterable[Provider],
    codes: Iterable[ProcedureCode],
    min_visit_lines: int,
) -> Findings:
    claim_list = list(claims)
    line_list = list(lines)
    lines_by_claim: dict[str, list[ClaimLine]] = defaultdict(list)
    for ln in line_list:
        lines_by_claim[ln.claim_id].append(ln)

    # 1. duplicates: identical member, provider, window, and line content
    groups: dict[tuple[object, ...], set[str]] = defaultdict(set)
    for c in claim_list:
        content = tuple(
            sorted((ln.code, ln.modifiers, ln.units) for ln in lines_by_claim[c.claim_id])
        )
        groups[(c.member_id, c.provider_id, c.service_from, c.service_to, content)].add(c.claim_id)
    duplicates = frozenset(frozenset(g) for g in groups.values() if len(g) > 1)

    # 2. unbundling: component billed with its comprehensive code, same claim and date, no modifier
    unbundled: set[str] = set()
    for claim_lines in lines_by_claim.values():
        by_date: dict[object, list[ClaimLine]] = defaultdict(list)
        for ln in claim_lines:
            by_date[ln.service_date].append(ln)
        for same_day in by_date.values():
            present = {ln.code for ln in same_day}
            for pair in pairs:
                if pair.comprehensive_code not in present:
                    continue
                for ln in same_day:
                    if (
                        ln.code == pair.component_code
                        and pair.exception_modifier not in ln.modifiers
                    ):
                        unbundled.add(ln.line_id)

    # 3. excess units on a single line
    limit_by_code = {u.code: u.max_units for u in limits}
    excess = {ln.line_id for ln in line_list if ln.units > limit_by_code[ln.code]}

    # 4. line dated outside the claim's service window
    claim_by_id = {c.claim_id: c for c in claim_list}
    outside = {
        ln.line_id
        for ln in line_list
        if not claim_by_id[ln.claim_id].service_from
        <= ln.service_date
        <= claim_by_id[ln.claim_id].service_to
    }

    # 5. provider intensity outlier vs same-specialty peers
    family = {c.code: (c.family, c.level) for c in codes}
    provider_list = list(providers)
    specialty = {p.provider_id: p.specialty for p in provider_list}
    visits: dict[str, list[int]] = defaultdict(list)
    for ln in line_list:
        fam, level = family[ln.code]
        if fam == "VISIT":
            visits[claim_by_id[ln.claim_id].provider_id].append(level)
    share = {
        pid: levels.count(3) / len(levels)
        for pid, levels in visits.items()
        if len(levels) >= min_visit_lines
    }
    peers: dict[str, list[float]] = defaultdict(list)
    for pid, value in share.items():
        peers[specialty[pid]].append(value)
    outliers = {
        pid
        for pid, value in share.items()
        if value
        >= max(OUTLIER_FLOOR, OUTLIER_MEDIAN_MULTIPLE * statistics.median(peers[specialty[pid]]))
    }
    return Findings(
        duplicates=duplicates,
        unbundled_lines=frozenset(unbundled),
        excess_unit_lines=frozenset(excess),
        out_of_window_lines=frozenset(outside),
        outlier_providers=frozenset(outliers),
    )
