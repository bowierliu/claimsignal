"""Build the full synthetic dataset: baseline, injected anomalies and decoys, flags."""

from __future__ import annotations

import random

from claims_copilot.synth.anomalies import inject_all
from claims_copilot.synth.baseline import Working, finalize_totals, generate_baseline
from claims_copilot.synth.config import GeneratorConfig
from claims_copilot.synth.dataset import Dataset
from claims_copilot.synth.flags import build_flags


def freeze(work: Working) -> Dataset:
    finalize_totals(work)
    return Dataset(
        config=work.config,
        members=work.members,
        providers=work.providers,
        procedure_codes=work.procedure_codes,
        diagnosis_codes=work.diagnosis_codes,
        bundle_pairs=work.bundle_pairs,
        unit_limits=work.unit_limits,
        claims=tuple(work.claims[k] for k in sorted(work.claims)),
        claim_lines=tuple(work.lines[k] for k in sorted(work.lines)),
        flags=tuple(build_flags(work)),
        truth=tuple(work.truth),
    )


def generate(config: GeneratorConfig | None = None) -> Dataset:
    cfg = config or GeneratorConfig()
    work = generate_baseline(cfg)
    inject_all(work, random.Random(f"{cfg.seed}:inject"))
    return freeze(work)
