"""Frozen record types for the synthetic payer dataset.

Everything here is synthetic. Procedure codes are obviously fake (`X0001` style). Diagnosis codes
are real ICD-10-CM codes (public source recorded in the manifest), stored as codes only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Member:
    member_id: str
    age_band: str
    sex: str
    plan_type: str
    region: str


@dataclass(frozen=True)
class Provider:
    provider_id: str
    specialty: str
    region: str
    group_id: str


@dataclass(frozen=True)
class ProcedureCode:
    code: str
    code_system: str
    category: str
    family: str  # "VISIT" for graded visit codes, otherwise ""
    level: int  # 1..3 inside the VISIT family, otherwise 0
    typical_charge: Decimal


@dataclass(frozen=True)
class DiagnosisCode:
    code: str
    code_system: str


@dataclass(frozen=True)
class BundlePair:
    """`component_code` is not separately billable with `comprehensive_code` on the same claim and
    date unless the component line carries `exception_modifier`. Synthetic rule, not NCCI."""

    comprehensive_code: str
    component_code: str
    exception_modifier: str


@dataclass(frozen=True)
class UnitLimit:
    """Maximum units on a single claim line. Synthetic rule, not MUE."""

    code: str
    max_units: int


@dataclass(frozen=True)
class Claim:
    claim_id: str
    member_id: str
    provider_id: str
    service_from: date
    service_to: date
    place_of_service: str
    diagnosis_codes: tuple[str, ...]
    total_billed: Decimal


@dataclass(frozen=True)
class ClaimLine:
    line_id: str
    claim_id: str
    line_no: int
    code: str
    modifiers: tuple[str, ...]
    units: int
    billed_amount: Decimal
    service_date: date
    dx_pointer: int  # 1-based index into the claim's diagnosis_codes


@dataclass(frozen=True)
class Flag:
    flag_id: str
    claim_id: str
    screen_code: str
    screen_text: str


@dataclass(frozen=True)
class AnomalyTruth:
    """Ground truth. Lives in a separate store that tools and the agent never open."""

    anomaly_id: str
    anomaly_type: str
    is_decoy: bool
    variant: str
    claim_ids: tuple[str, ...]
    line_ids: tuple[str, ...]
    provider_id: str  # "" when the anomaly is not provider-level
    explanation: str
