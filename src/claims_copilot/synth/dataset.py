"""The in-memory dataset and its canonical hash.

`Dataset` is split in two on purpose: `payer_hash` covers what tools and the agent may see, and
`truth_hash` covers the ground truth, which lives in a separate store.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from claims_copilot.synth.config import GeneratorConfig
from claims_copilot.synth.models import (
    AnomalyTruth,
    BundlePair,
    Claim,
    ClaimLine,
    DiagnosisCode,
    Flag,
    Member,
    ProcedureCode,
    Provider,
    UnitLimit,
)


@dataclass(frozen=True)
class Dataset:
    config: GeneratorConfig
    members: tuple[Member, ...]
    providers: tuple[Provider, ...]
    procedure_codes: tuple[ProcedureCode, ...]
    diagnosis_codes: tuple[DiagnosisCode, ...]
    bundle_pairs: tuple[BundlePair, ...]
    unit_limits: tuple[UnitLimit, ...]
    claims: tuple[Claim, ...]
    claim_lines: tuple[ClaimLine, ...]
    flags: tuple[Flag, ...]
    truth: tuple[AnomalyTruth, ...]

    def payer_tables(self) -> dict[str, tuple[Any, ...]]:
        return {
            "members": self.members,
            "providers": self.providers,
            "procedure_codes": self.procedure_codes,
            "diagnosis_codes": self.diagnosis_codes,
            "bundle_pairs": self.bundle_pairs,
            "unit_limits": self.unit_limits,
            "claims": self.claims,
            "claim_lines": self.claim_lines,
            "flags": self.flags,
        }

    def counts(self) -> dict[str, int]:
        counts = {name: len(rows) for name, rows in self.payer_tables().items()}
        counts["anomaly_truth"] = len(self.truth)
        return counts


def _default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported type {type(value).__name__}")


def _digest(payload: object) -> str:
    text = json.dumps(payload, default=_default, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def payer_hash(dataset: Dataset) -> str:
    return _digest(
        {name: [asdict(r) for r in rows] for name, rows in dataset.payer_tables().items()}
    )


def truth_hash(dataset: Dataset) -> str:
    return _digest([asdict(t) for t in dataset.truth])


def golden_summary(dataset: Dataset) -> dict[str, Any]:
    """What a test compares a regenerated default dataset against."""
    cases: dict[str, dict[str, int]] = {}
    for t in dataset.truth:
        entry = cases.setdefault(t.anomaly_type, {"anomalies": 0, "decoys": 0})
        entry["decoys" if t.is_decoy else "anomalies"] += 1
    cfg = asdict(dataset.config)
    return {
        "config": {k: v.isoformat() if isinstance(v, date) else v for k, v in cfg.items()},
        "counts": dataset.counts(),
        "cases_by_type": dict(sorted(cases.items())),
        "payer_sha256": payer_hash(dataset),
        "truth_sha256": truth_hash(dataset),
    }
