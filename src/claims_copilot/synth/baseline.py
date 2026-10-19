"""Clean baseline claims and the mutable working state the anomaly injectors edit.

The baseline is built to contain no anomaly of any of the five types, so the independent reference
checker (in the tests) must find nothing in it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal

from claims_copilot.synth.codes import (
    BUNDLE_PAIRS,
    CODES_BY_CATEGORY,
    NOISE_MODIFIERS,
    PROCEDURE_BY_CODE,
    PROCEDURE_CODES,
    SPECIALTIES,
    UNIT_LIMIT_BY_CODE,
    UNIT_LIMITS,
    load_diagnosis_subset,
)
from claims_copilot.synth.config import GeneratorConfig
from claims_copilot.synth.models import (
    AnomalyTruth,
    BundlePair,
    Claim,
    ClaimLine,
    DiagnosisCode,
    Member,
    ProcedureCode,
    Provider,
    UnitLimit,
)

AGE_BANDS = ("0-17", "18-34", "35-49", "50-64", "65+")
PLAN_TYPES = ("HMO", "PPO", "EPO")
REGIONS = ("R1", "R2", "R3", "R4", "R5")
LINE_COUNT_WEIGHTS = ((1, 2, 3, 4), (60, 25, 10, 5))
MAX_PLACEMENT_TRIES = 25


class GenerationError(RuntimeError):
    pass


def line_amount(code: str, units: int, rng: random.Random | None = None) -> Decimal:
    """Billed amount: typical charge x units, with a small seeded jitter when `rng` is given."""
    factor = rng.uniform(0.95, 1.05) if rng is not None else 1.0
    raw = float(PROCEDURE_BY_CODE[code].typical_charge) * units * factor
    return Decimal(f"{raw:.2f}")


def line_id(claim_id: str, line_no: int) -> str:
    return f"{claim_id}-{line_no:02d}"


@dataclass
class Working:
    """Mutable generation state. Frozen records are replaced, never edited in place."""

    config: GeneratorConfig
    members: tuple[Member, ...]
    providers: tuple[Provider, ...]
    procedure_codes: tuple[ProcedureCode, ...]
    diagnosis_codes: tuple[DiagnosisCode, ...]
    bundle_pairs: tuple[BundlePair, ...]
    unit_limits: tuple[UnitLimit, ...]
    claims: dict[str, Claim] = field(default_factory=dict)
    lines: dict[str, ClaimLine] = field(default_factory=dict)
    claim_line_ids: dict[str, list[str]] = field(default_factory=dict)
    truth: list[AnomalyTruth] = field(default_factory=list)
    next_claim_no: int = 1

    def new_claim_id(self) -> str:
        claim_id = f"C{self.next_claim_no:07d}"
        self.next_claim_no += 1
        return claim_id

    def add_claim(self, claim: Claim, lines: list[ClaimLine]) -> None:
        self.claims[claim.claim_id] = claim
        self.claim_line_ids[claim.claim_id] = [ln.line_id for ln in lines]
        for ln in lines:
            self.lines[ln.line_id] = ln

    def lines_of(self, claim_id: str) -> list[ClaimLine]:
        return [self.lines[i] for i in self.claim_line_ids[claim_id]]

    def replace_line(self, new: ClaimLine) -> None:
        self.lines[new.line_id] = new

    def append_line(self, new: ClaimLine) -> None:
        self.lines[new.line_id] = new
        self.claim_line_ids[new.claim_id].append(new.line_id)

    def add_truth(
        self,
        anomaly_type: str,
        *,
        is_decoy: bool,
        variant: str,
        claim_ids: tuple[str, ...],
        line_ids: tuple[str, ...],
        explanation: str,
        provider_id: str = "",
    ) -> AnomalyTruth:
        entry = AnomalyTruth(
            anomaly_id=f"A{len(self.truth) + 1:04d}",
            anomaly_type=anomaly_type,
            is_decoy=is_decoy,
            variant=variant,
            claim_ids=claim_ids,
            line_ids=line_ids,
            provider_id=provider_id,
            explanation=explanation,
        )
        self.truth.append(entry)
        return entry

    def provider_by_id(self) -> dict[str, Provider]:
        return {p.provider_id: p for p in self.providers}


def _specialty_counts(n_providers: int) -> dict[str, int]:
    counts = {name: int(n_providers * share) for name, (share, _, _, _) in SPECIALTIES.items()}
    counts["primary_care"] += n_providers - sum(counts.values())
    return counts


def _make_providers(cfg: GeneratorConfig, rng: random.Random) -> list[Provider]:
    providers: list[Provider] = []
    n_groups = max(2, cfg.n_providers // 8)
    for specialty, count in _specialty_counts(cfg.n_providers).items():
        for _ in range(count):
            number = len(providers) + 1
            providers.append(
                Provider(
                    provider_id=f"P{number:04d}",
                    specialty=specialty,
                    region=rng.choice(REGIONS),
                    group_id=f"G{rng.randint(1, n_groups):03d}",
                )
            )
    return providers


def _draw_units(code: str, rng: random.Random) -> int:
    limit = UNIT_LIMIT_BY_CODE[code]
    if limit == 1:
        return 1
    return rng.choices(range(1, limit + 1), weights=[limit - u + 1 for u in range(1, limit + 1)])[0]


def _draw_code(category: str, visit_l3_share: float, rng: random.Random) -> str:
    codes = CODES_BY_CATEGORY[category]
    if category != "visit":
        return rng.choice(codes)
    low = (1 - visit_l3_share) * 0.6
    return rng.choices(codes, weights=[low, (1 - visit_l3_share) - low, visit_l3_share])[0]


def has_bundle_conflict(codes: list[str], pairs: tuple[BundlePair, ...]) -> bool:
    present = set(codes)
    return any(p.comprehensive_code in present and p.component_code in present for p in pairs)


def _service_dates(cfg: GeneratorConfig, rng: random.Random) -> tuple[date, date]:
    span = (cfg.window_end - cfg.window_start).days
    start = cfg.window_start + timedelta(days=rng.randint(0, span))
    extra = rng.choice((1, 2, 3)) if rng.random() < 0.15 else 0
    return start, min(start + timedelta(days=extra), cfg.window_end)


def generate_baseline(cfg: GeneratorConfig) -> Working:
    rng = random.Random(cfg.seed)
    members = tuple(
        Member(
            member_id=f"M{i:06d}",
            age_band=rng.choice(AGE_BANDS),
            sex=rng.choice(("F", "M")),
            plan_type=rng.choice(PLAN_TYPES),
            region=rng.choice(REGIONS),
        )
        for i in range(1, cfg.n_members + 1)
    )
    providers = _make_providers(cfg, rng)
    visit_l3_share = {p.provider_id: rng.uniform(0.05, 0.18) for p in providers}
    weights = [rng.uniform(0.5, 1.5) for _ in providers]
    cum_weights = [sum(weights[: i + 1]) for i in range(len(weights))]
    diagnoses = load_diagnosis_subset()
    pool_by_chapters = {
        chapters: [d.code for d in diagnoses if not chapters or d.code[0] in chapters]
        for chapters in {spec[3] for spec in SPECIALTIES.values()}
    }
    work = Working(
        config=cfg,
        members=members,
        providers=tuple(providers),
        procedure_codes=PROCEDURE_CODES,
        diagnosis_codes=diagnoses,
        bundle_pairs=BUNDLE_PAIRS,
        unit_limits=UNIT_LIMITS,
    )
    taken: set[tuple[str, str, date]] = set()
    attempts = 0
    while len(work.claims) < cfg.n_claims:
        attempts += 1
        if attempts > cfg.n_claims * 20:
            raise GenerationError("could not place enough baseline claims")
        provider = rng.choices(providers, cum_weights=cum_weights)[0]
        member = rng.choice(members)
        start, end = _service_dates(cfg, rng)
        key = (member.member_id, provider.provider_id, start)
        if key in taken:
            continue
        taken.add(key)
        _, mix, place, chapters = SPECIALTIES[provider.specialty]
        n_lines = rng.choices(*LINE_COUNT_WEIGHTS)[0]
        chosen: list[str] = []
        for _ in range(n_lines):
            for _try in range(MAX_PLACEMENT_TRIES):
                category = rng.choices(list(mix), weights=list(mix.values()))[0]
                code = _draw_code(category, visit_l3_share[provider.provider_id], rng)
                if code not in chosen and not has_bundle_conflict([*chosen, code], BUNDLE_PAIRS):
                    chosen.append(code)
                    break
        if not chosen:
            taken.discard(key)
            continue
        pool = pool_by_chapters[chapters]
        dx = tuple(sorted(rng.sample(pool, rng.choice((1, 2, 3)))))
        claim_id = work.new_claim_id()
        span_days = (end - start).days
        lines = []
        for number, code in enumerate(chosen, start=1):
            units = _draw_units(code, rng)
            mods = (rng.choice(NOISE_MODIFIERS),) if rng.random() < 0.05 else ()
            lines.append(
                ClaimLine(
                    line_id=line_id(claim_id, number),
                    claim_id=claim_id,
                    line_no=number,
                    code=code,
                    modifiers=mods,
                    units=units,
                    billed_amount=line_amount(code, units, rng),
                    service_date=start + timedelta(days=rng.randint(0, span_days)),
                    dx_pointer=rng.randint(1, len(dx)),
                )
            )
        work.add_claim(
            Claim(
                claim_id=claim_id,
                member_id=member.member_id,
                provider_id=provider.provider_id,
                service_from=start,
                service_to=end,
                place_of_service=place,
                diagnosis_codes=dx,
                total_billed=Decimal("0.00"),
            ),
            lines,
        )
    return work


def finalize_totals(work: Working) -> None:
    """Set each claim's total_billed to the sum of its lines (after all edits)."""
    for claim_id, claim in list(work.claims.items()):
        total = sum((ln.billed_amount for ln in work.lines_of(claim_id)), Decimal("0.00"))
        work.claims[claim_id] = replace(claim, total_billed=total)
