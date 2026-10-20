"""Rule tables behind a swappable interface.

The checks ask a `RulesProvider` for bundle pairs and unit limits. The only provider today reads
the invented synthetic tables in `payer.sqlite`. They are NOT NCCI procedure-to-procedure edits or
MUEs (KF-009, KF-012); real tables are keyed by real CPT codes and are licence-gated. A real
provider could be added later without touching the checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from claims_copilot.tools.repository import Repository

SYNTHETIC_RULESET = "synthetic-v1 (invented rules, not NCCI or MUE)"


@dataclass(frozen=True)
class BundleRule:
    comprehensive_code: str
    component_code: str
    exception_modifier: str

    @property
    def rule_id(self) -> str:
        return f"bundle_pair:{self.comprehensive_code}+{self.component_code}"


@dataclass(frozen=True)
class UnitRule:
    code: str
    max_units: int

    @property
    def rule_id(self) -> str:
        return f"unit_limit:{self.code}"


class RulesProvider(Protocol):
    name: str

    def bundle_rules(self) -> tuple[BundleRule, ...]: ...

    def unit_rules(self) -> dict[str, UnitRule]: ...


class SyntheticRules:
    """Reads the invented rule tables from the payer database."""

    name = SYNTHETIC_RULESET

    def __init__(self, repo: Repository) -> None:
        self._bundles = tuple(BundleRule(*row) for row in repo.bundle_pairs())
        self._units = {c: UnitRule(c, n) for c, n in repo.unit_limits().items()}

    def bundle_rules(self) -> tuple[BundleRule, ...]:
        return self._bundles

    def unit_rules(self) -> dict[str, UnitRule]:
        return self._units
