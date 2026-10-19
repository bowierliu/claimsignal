"""Seeded anomaly injectors and their decoys. Each injector records ground truth.

Order matters and is fixed: provider-level outliers first (they touch many lines), then the
claim-level types. A claim is touched by at most one injector, and providers used for outlier
anomalies or decoys are kept out of the claim-level injectors, so the checks stay independent.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import timedelta

from claims_copilot.synth.baseline import GenerationError, Working, line_amount, line_id
from claims_copilot.synth.codes import (
    EXCEPTION_MODIFIER,
    PROCEDURE_BY_CODE,
    UNIT_LIMIT_BY_CODE,
    VISIT_FAMILY,
    VISIT_HIGH,
)
from claims_copilot.synth.models import ClaimLine

DUPLICATE = "duplicate_claim"
UNBUNDLING = "unbundling"
EXCESS_UNITS = "excess_units"
OUTLIER = "intensity_outlier"
DATE_ANOMALY = "date_anomaly"
ANOMALY_TYPES = (DUPLICATE, UNBUNDLING, EXCESS_UNITS, OUTLIER, DATE_ANOMALY)

OUTLIER_SHARE = (0.55, 0.75)
DECOY_SHARE = (0.25, 0.32)


@dataclass
class State:
    used_claims: set[str] = field(default_factory=set)
    excluded_providers: set[str] = field(default_factory=set)


def _eligible_claims(work: Working, state: State) -> list[str]:
    """Sorted ids of claims no injector has touched and whose provider is not an outlier case."""
    return sorted(
        cid
        for cid, claim in work.claims.items()
        if cid not in state.used_claims and claim.provider_id not in state.excluded_providers
    )


def _pick(pool: list[str], n: int, rng: random.Random, what: str) -> list[str]:
    if len(pool) < n:
        raise GenerationError(f"need {n} candidates for {what}, found {len(pool)}")
    return rng.sample(pool, n)


def inject_outliers(work: Working, rng: random.Random, state: State) -> None:
    cfg = work.config
    visit_lines: dict[str, list[ClaimLine]] = defaultdict(list)
    for lid in sorted(work.lines):
        ln = work.lines[lid]
        if PROCEDURE_BY_CODE[ln.code].family == VISIT_FAMILY:
            visit_lines[work.claims[ln.claim_id].provider_id].append(ln)
    eligible = sorted(p for p, lns in visit_lines.items() if len(lns) >= cfg.min_visit_lines)
    n_total = cfg.anomalies_per_type + cfg.decoys_per_type
    chosen = _pick(eligible, n_total, rng, OUTLIER)
    for index, provider_id in enumerate(chosen):
        is_decoy = index >= cfg.anomalies_per_type
        low, high = DECOY_SHARE if is_decoy else OUTLIER_SHARE
        share = rng.uniform(low, high)
        lines = visit_lines[provider_id]
        current = sum(1 for ln in lines if ln.code == VISIT_HIGH)
        need = max(0, round(share * len(lines)) - current)
        movable = [ln for ln in lines if ln.code != VISIT_HIGH]
        changed: list[ClaimLine] = []
        for ln in rng.sample(movable, need):
            new = replace(ln, code=VISIT_HIGH, billed_amount=line_amount(VISIT_HIGH, ln.units, rng))
            work.replace_line(new)
            changed.append(new)
        state.excluded_providers.add(provider_id)
        final_share = (current + len(changed)) / len(lines)
        work.add_truth(
            OUTLIER,
            is_decoy=is_decoy,
            variant="high_but_within_peer_spread" if is_decoy else "share_far_above_peers",
            claim_ids=tuple(sorted({ln.claim_id for ln in changed})),
            line_ids=tuple(sorted(ln.line_id for ln in changed)),
            provider_id=provider_id,
            explanation=(
                f"{len(lines)} visit lines; share of the highest-intensity visit code set to "
                f"{final_share:.2f} (peer baseline about 0.12)."
            ),
        )


def inject_date_anomalies(work: Working, rng: random.Random, state: State) -> None:
    cfg = work.config
    anomalous = _pick(_eligible_claims(work, state), cfg.anomalies_per_type, rng, DATE_ANOMALY)
    state.used_claims.update(anomalous)
    for cid in anomalous:
        claim = work.claims[cid]
        ln = rng.choice(work.lines_of(cid))
        offset = timedelta(days=rng.randint(7, 90))
        later = rng.random() < 0.5
        moved = claim.service_to + offset if later else claim.service_from - offset
        work.replace_line(replace(ln, service_date=moved))
        work.add_truth(
            DATE_ANOMALY,
            is_decoy=False,
            variant="after_window" if later else "before_window",
            claim_ids=(cid,),
            line_ids=(ln.line_id,),
            explanation=(
                f"Line dated {moved.isoformat()}, outside the claim window "
                f"{claim.service_from.isoformat()} to {claim.service_to.isoformat()}."
            ),
        )
    multi_day = [
        cid
        for cid in _eligible_claims(work, state)
        if work.claims[cid].service_to > work.claims[cid].service_from
    ]
    decoys = _pick(multi_day, cfg.decoys_per_type, rng, "date_anomaly decoys")
    state.used_claims.update(decoys)
    for cid in decoys:
        claim = work.claims[cid]
        ln = rng.choice(work.lines_of(cid))
        on_end = rng.random() < 0.5
        edge = claim.service_to if on_end else claim.service_from
        work.replace_line(replace(ln, service_date=edge))
        work.add_truth(
            DATE_ANOMALY,
            is_decoy=True,
            variant="on_window_boundary",
            claim_ids=(cid,),
            line_ids=(ln.line_id,),
            explanation=f"Line dated {edge.isoformat()}, exactly on the claim window boundary.",
        )


def inject_excess_units(work: Working, rng: random.Random, state: State) -> None:
    cfg = work.config
    anomalous = _pick(_eligible_claims(work, state), cfg.anomalies_per_type, rng, EXCESS_UNITS)
    state.used_claims.update(anomalous)
    for cid in anomalous:
        ln = rng.choice(work.lines_of(cid))
        limit = UNIT_LIMIT_BY_CODE[ln.code]
        units = limit + rng.randint(1, 3)
        work.replace_line(replace(ln, units=units, billed_amount=line_amount(ln.code, units, rng)))
        work.add_truth(
            EXCESS_UNITS,
            is_decoy=False,
            variant="over_limit",
            claim_ids=(cid,),
            line_ids=(ln.line_id,),
            explanation=f"{units} units on a line whose limit is {limit}.",
        )
    candidates: list[tuple[str, ClaimLine]] = []
    for cid in _eligible_claims(work, state):
        for ln in work.lines_of(cid):
            limit = UNIT_LIMIT_BY_CODE[ln.code]
            if limit >= 2 and ln.units < limit:
                candidates.append((cid, ln))
                break
    picks = _pick([cid for cid, _ in candidates], cfg.decoys_per_type, rng, "excess_units decoys")
    by_claim = dict(candidates)
    state.used_claims.update(picks)
    for cid in picks:
        ln = by_claim[cid]
        limit = UNIT_LIMIT_BY_CODE[ln.code]
        work.replace_line(replace(ln, units=limit, billed_amount=line_amount(ln.code, limit, rng)))
        work.add_truth(
            EXCESS_UNITS,
            is_decoy=True,
            variant="exactly_at_limit",
            claim_ids=(cid,),
            line_ids=(ln.line_id,),
            explanation=f"{limit} units on a line whose limit is {limit} (allowed).",
        )


def inject_unbundling(work: Working, rng: random.Random, state: State) -> None:
    cfg = work.config
    options: dict[str, list[tuple[ClaimLine, str]]] = defaultdict(list)
    for cid in _eligible_claims(work, state):
        lines = work.lines_of(cid)
        codes = {ln.code for ln in lines}
        for ln in lines:
            for pair in work.bundle_pairs:
                if pair.comprehensive_code != ln.code or pair.component_code in codes:
                    continue
                # Adding the component must not create any second bundle conflict.
                after = codes | {pair.component_code}
                clashes = sum(
                    1
                    for p in work.bundle_pairs
                    if p.comprehensive_code in after and p.component_code in after
                )
                if clashes == 1:
                    options[cid].append((ln, pair.component_code))
    claim_ids = _pick(
        sorted(options), cfg.anomalies_per_type + cfg.decoys_per_type, rng, UNBUNDLING
    )
    for index, cid in enumerate(claim_ids):
        is_decoy = index >= cfg.anomalies_per_type
        anchor, component = rng.choice(options[cid])
        state.used_claims.add(cid)
        number = len(work.claim_line_ids[cid]) + 1
        new_line = ClaimLine(
            line_id=line_id(cid, number),
            claim_id=cid,
            line_no=number,
            code=component,
            modifiers=(EXCEPTION_MODIFIER,) if is_decoy else (),
            units=1,
            billed_amount=line_amount(component, 1, rng),
            service_date=anchor.service_date,
            dx_pointer=anchor.dx_pointer,
        )
        work.append_line(new_line)
        work.add_truth(
            UNBUNDLING,
            is_decoy=is_decoy,
            variant="valid_exception_modifier" if is_decoy else "no_modifier",
            claim_ids=(cid,),
            line_ids=(anchor.line_id, new_line.line_id),
            explanation=(
                f"{component} billed with {anchor.code} on {anchor.service_date.isoformat()}"
                + (f" with exception modifier {EXCEPTION_MODIFIER} (allowed)." if is_decoy else ".")
            ),
        )


def inject_duplicates(work: Working, rng: random.Random, state: State) -> None:
    cfg = work.config
    n_total = cfg.anomalies_per_type + cfg.decoys_per_type
    originals = _pick(_eligible_claims(work, state), n_total, rng, DUPLICATE)
    peers = sorted(
        p.provider_id for p in work.providers if p.provider_id not in state.excluded_providers
    )
    for index, cid in enumerate(originals):
        is_decoy = index >= cfg.anomalies_per_type
        claim = work.claims[cid]
        shift = timedelta(0)
        provider_id = claim.provider_id
        variant = "same_member_provider_date_codes"
        if is_decoy and index % 2 == 0:
            shift = timedelta(days=rng.randint(7, 30))
            if claim.service_to + shift > work.config.window_end:
                shift = -shift
            variant = "repeat_service_on_a_later_date"
        elif is_decoy:
            provider_id = rng.choice([p for p in peers if p != claim.provider_id])
            variant = "same_services_by_a_different_provider"
        new_id = work.new_claim_id()
        copy_lines = [
            replace(
                ln,
                line_id=line_id(new_id, ln.line_no),
                claim_id=new_id,
                service_date=ln.service_date + shift,
            )
            for ln in work.lines_of(cid)
        ]
        work.add_claim(
            replace(
                claim,
                claim_id=new_id,
                provider_id=provider_id,
                service_from=claim.service_from + shift,
                service_to=claim.service_to + shift,
            ),
            copy_lines,
        )
        state.used_claims.update((cid, new_id))
        work.add_truth(
            DUPLICATE,
            is_decoy=is_decoy,
            variant=variant,
            claim_ids=(cid, new_id),
            line_ids=tuple(ln.line_id for ln in copy_lines),
            explanation=(
                f"Claim {new_id} repeats {cid}: "
                + (
                    "allowed, " + variant.replace("_", " ") + "."
                    if is_decoy
                    else "same member, provider, dates, codes, modifiers and units."
                )
            ),
        )


def inject_all(work: Working, rng: random.Random) -> State:
    state = State()
    inject_outliers(work, rng, state)
    inject_date_anomalies(work, rng, state)
    inject_excess_units(work, rng, state)
    inject_unbundling(work, rng, state)
    inject_duplicates(work, rng, state)
    return state
