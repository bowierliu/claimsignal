"""Load the pre-registered thresholds. One source of truth: `eval/phase7_preregistration.json`."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

from claims_copilot.project import REPO_ROOT

PREREG_PATH = REPO_ROOT / "eval" / "phase7_preregistration.json"


@dataclass(frozen=True)
class Preregistration:
    version: str
    repeats: int
    split_salt: str
    phase_ceiling_usd: Decimal
    layer_sizes: dict[str, int]
    safety_mix: dict[str, int]
    invariants: dict[str, int]
    targets: dict[str, float]
    kappa_min: float
    false_supported_max: int
    min_minority_class_statements: int
    labelled_answers: int
    conflict_min_labelled_answers: int
    label_sample_seed: int
    label_sample_mix: dict[str, int]
    alpha: float
    wilson_z: float
    search_unanswerable_max_drop: float
    sha256: str


def _numbers(section: dict[str, Any]) -> dict[str, float]:
    return {k: float(v) for k, v in section.items() if k != "note"}


def _ints(section: dict[str, Any]) -> dict[str, int]:
    return {k: int(v) for k, v in section.items() if k != "note"}


@cache
def load_preregistration(path: Path = PREREG_PATH) -> Preregistration:
    raw = path.read_bytes()
    data = json.loads(raw)
    judge = data["judge"]
    return Preregistration(
        version=data["version"],
        repeats=int(data["repeats"]),
        split_salt=data["split"]["salt"],
        phase_ceiling_usd=Decimal(data["cost"]["phase_ceiling_usd"]),
        layer_sizes=_ints(data["layer_sizes"]),
        safety_mix=_ints(data["safety_mix"]),
        invariants=_ints(data["invariants"]),
        targets=_numbers(data["targets"]),
        kappa_min=float(judge["kappa_min"]),
        false_supported_max=int(judge["false_supported_max"]),
        min_minority_class_statements=int(judge["min_minority_class_statements"]),
        labelled_answers=int(judge["labelled_answers"]),
        conflict_min_labelled_answers=int(judge["conflict_min_labelled_answers"]),
        label_sample_seed=int(judge["label_sample_seed"]),
        label_sample_mix=_ints(judge["label_sample_mix"]),
        alpha=float(data["comparison"]["alpha"]),
        wilson_z=float(data["comparison"]["wilson_z"]),
        search_unanswerable_max_drop=float(
            data["search_mode_decision"]["unanswerable_correct_rate_max_drop"]
        ),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
