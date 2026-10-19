"""Synthetic procedure codes, synthetic rule tables, and the ICD-10-CM diagnosis subset loader.

Procedure codes are obviously fake (`X0001` style) and carry no descriptors. The bundle and unit
rules are invented for this project; they are not NCCI or MUE values.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from claims_copilot.project import ICD_SUBSET_PATH
from claims_copilot.synth.models import BundlePair, DiagnosisCode, ProcedureCode, UnitLimit

PROC_SYSTEM = "SYNTH"
ICD_SYSTEM = "ICD10CM_FY2027"
EXCEPTION_MODIFIER = "M1"  # synthetic "distinct service" modifier that lifts a bundle rule
NOISE_MODIFIERS = ("M2", "M3")  # synthetic modifiers with no rule attached
PROC_CODE_PATTERN = re.compile(r"X\d{4}")
ICD_CODE_PATTERN = re.compile(r"[A-Z][0-9A-Z]{2,6}")  # 3-7 characters, as observed in the file

VISIT_FAMILY = "VISIT"
VISIT_HIGH = "X0003"


def _codes(first: int, count: int, category: str, base: str, step: str) -> list[ProcedureCode]:
    return [
        ProcedureCode(
            code=f"X{first + i:04d}",
            code_system=PROC_SYSTEM,
            category=category,
            family="",
            level=0,
            typical_charge=Decimal(base) + Decimal(step) * i,
        )
        for i in range(count)
    ]


def _build_procedure_codes() -> tuple[ProcedureCode, ...]:
    visits = [
        ProcedureCode(f"X{n:04d}", PROC_SYSTEM, "visit", VISIT_FAMILY, level, Decimal(charge))
        for n, level, charge in ((1, 1, "60.00"), (2, 2, "110.00"), (3, 3, "180.00"))
    ]
    return tuple(
        visits
        + _codes(10, 10, "procedure", "150.00", "70.00")
        + _codes(20, 8, "imaging", "200.00", "60.00")
        + _codes(30, 10, "lab", "15.00", "7.00")
        + _codes(40, 6, "therapy", "40.00", "10.00")
    )


PROCEDURE_CODES = _build_procedure_codes()
PROCEDURE_BY_CODE = {c.code: c for c in PROCEDURE_CODES}
CODES_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    cat: tuple(c.code for c in PROCEDURE_CODES if c.category == cat)
    for cat in ("visit", "procedure", "imaging", "lab", "therapy")
}

_PAIRS = (
    ("X0010", "X0011"),
    ("X0010", "X0012"),
    ("X0013", "X0014"),
    ("X0015", "X0016"),
    ("X0017", "X0018"),
    ("X0020", "X0021"),
    ("X0020", "X0022"),
    ("X0023", "X0024"),
    ("X0025", "X0026"),
    ("X0030", "X0031"),
    ("X0032", "X0033"),
    ("X0034", "X0035"),
    ("X0040", "X0041"),
    ("X0042", "X0043"),
)
BUNDLE_PAIRS = tuple(BundlePair(a, b, EXCEPTION_MODIFIER) for a, b in _PAIRS)

UNIT_LIMITS = tuple(
    UnitLimit(c.code, {"lab": 3, "therapy": 4}.get(c.category, 1)) for c in PROCEDURE_CODES
)
UNIT_LIMIT_BY_CODE = {u.code: u.max_units for u in UNIT_LIMITS}

# Specialty -> (share of providers, category weights for claim lines, place of service,
# ICD-10-CM chapter letters the specialty draws diagnoses from; "" means any).
SPECIALTIES: dict[str, tuple[float, dict[str, int], str, str]] = {
    "primary_care": (0.30, {"visit": 70, "lab": 20, "procedure": 10}, "PS1", ""),
    "cardiology": (0.125, {"visit": 40, "imaging": 30, "procedure": 30}, "PS1", "I"),
    "orthopedics": (0.125, {"visit": 30, "procedure": 50, "imaging": 20}, "PS1", "MS"),
    "imaging": (0.125, {"imaging": 100}, "PS2", ""),
    "therapy": (0.175, {"therapy": 100}, "PS3", "MSG"),
    "lab": (0.15, {"lab": 100}, "PS2", ""),
}
VISIT_SPECIALTIES = tuple(s for s, (_, mix, _, _) in SPECIALTIES.items() if "visit" in mix)


def load_diagnosis_subset(path: Path = ICD_SUBSET_PATH) -> tuple[DiagnosisCode, ...]:
    """Read the committed code-only subset (lines starting with `#` are provenance comments)."""
    codes: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not ICD_CODE_PATTERN.fullmatch(line):
            raise ValueError(f"{path.name}: not an ICD-10-CM code shape: {line!r}")
        codes.append(line)
    if len(codes) != len(set(codes)):
        raise ValueError(f"{path.name}: duplicate codes")
    return tuple(DiagnosisCode(code, ICD_SYSTEM) for code in codes)
