from __future__ import annotations

import re
from collections import Counter

from claims_copilot.synth.baseline import Working, finalize_totals, generate_baseline
from claims_copilot.synth.codes import (
    ICD_CODE_PATTERN,
    PROC_CODE_PATTERN,
    PROCEDURE_CODES,
    load_diagnosis_subset,
)
from claims_copilot.synth.config import GeneratorConfig
from synth_oracle import Findings, find_anomalies


def check(work: Working) -> Findings:
    return find_anomalies(
        work.claims.values(),
        work.lines.values(),
        work.bundle_pairs,
        work.unit_limits,
        work.providers,
        work.procedure_codes,
        work.config.min_visit_lines,
    )


def test_procedure_codes_are_obviously_fake_and_have_no_descriptor_fields() -> None:
    assert len(PROCEDURE_CODES) == len({c.code for c in PROCEDURE_CODES})
    assert all(PROC_CODE_PATTERN.fullmatch(c.code) for c in PROCEDURE_CODES)
    assert not any(re.fullmatch(r"\d{5}", c.code) for c in PROCEDURE_CODES)
    field_names = set(PROCEDURE_CODES[0].__dataclass_fields__)
    assert not {"description", "descriptor", "title", "long_description"} & field_names


def test_diagnosis_subset_is_codes_only_with_valid_shape() -> None:
    codes = load_diagnosis_subset()
    assert len(codes) == 420
    assert all(ICD_CODE_PATTERN.fullmatch(c.code) for c in codes)
    assert {c.code_system for c in codes} == {"ICD10CM_FY2027"}


def test_baseline_is_deterministic_for_a_seed() -> None:
    cfg = GeneratorConfig.small()
    a, b = generate_baseline(cfg), generate_baseline(cfg)
    assert a.claims == b.claims and a.lines == b.lines
    other = generate_baseline(GeneratorConfig.small(seed=1))
    assert other.claims != a.claims


def test_baseline_has_referential_integrity_and_window_dates() -> None:
    work = generate_baseline(GeneratorConfig.small())
    finalize_totals(work)
    cfg = work.config
    member_ids = {m.member_id for m in work.members}
    provider_ids = {p.provider_id for p in work.providers}
    dx = {d.code for d in work.diagnosis_codes}
    assert len(work.claims) == cfg.n_claims
    for claim in work.claims.values():
        assert claim.member_id in member_ids and claim.provider_id in provider_ids
        assert set(claim.diagnosis_codes) <= dx
        assert cfg.window_start <= claim.service_from <= claim.service_to <= cfg.window_end
        claim_lines = work.lines_of(claim.claim_id)
        assert claim_lines
        assert claim.total_billed == sum(ln.billed_amount for ln in claim_lines)
        for ln in claim_lines:
            assert claim.service_from <= ln.service_date <= claim.service_to
            assert 1 <= ln.dx_pointer <= len(claim.diagnosis_codes)


def test_baseline_has_no_anomalies_of_any_type_by_the_independent_checker() -> None:
    findings = check(generate_baseline(GeneratorConfig.small()))
    assert findings == Findings(frozenset(), frozenset(), frozenset(), frozenset(), frozenset())


def test_baseline_mixes_multi_day_claims_and_modifiers_so_they_are_not_signals() -> None:
    work = generate_baseline(GeneratorConfig.small())
    assert sum(1 for c in work.claims.values() if c.service_to > c.service_from) > 100
    modifiers = Counter(m for ln in work.lines.values() for m in ln.modifiers)
    assert set(modifiers) == {"M2", "M3"}
