"""Generator configuration. A (seed, config) pair fully determines the dataset."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

DEFAULT_SEED = 20261019
# Every diagnosis code in the committed subset is valid for services in the ICD-10-CM FY2027
# window, so claims are dated inside it. The dates are fictional.
WINDOW_START = date(2026, 10, 1)
WINDOW_END = date(2027, 9, 30)


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = DEFAULT_SEED
    n_members: int = 4000
    n_providers: int = 400
    n_claims: int = 40000
    window_start: date = WINDOW_START
    window_end: date = WINDOW_END
    anomalies_per_type: int = 30
    decoys_per_type: int = 30
    false_alarm_flags: int = 200
    min_visit_lines: int = 40  # a provider needs this many visit lines to be an outlier candidate

    @classmethod
    def small(cls, seed: int = DEFAULT_SEED) -> GeneratorConfig:
        """A fast configuration for tests (same logic, fewer rows)."""
        return cls(
            seed=seed,
            n_members=800,
            n_providers=120,
            n_claims=12000,
            anomalies_per_type=4,
            decoys_per_type=4,
            false_alarm_flags=20,
            min_visit_lines=30,
        )
