"""Metric definitions. Pure functions, no I/O, tested. The report may only use these.

Unit of analysis: the case. Repeats of one case are averaged first (`case_means`) so one flaky case
cannot look like several.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import comb


class MetricError(ValueError):
    """The inputs cannot define the metric (empty, mismatched, or degenerate)."""


@dataclass(frozen=True)
class Interval:
    rate: float
    low: float
    high: float
    successes: int
    n: int


def wilson_interval(successes: int, n: int, z: float = 1.96) -> Interval:
    """Wilson score interval for a rate. Defined for n >= 1."""
    if n < 1 or not 0 <= successes <= n:
        raise MetricError("need 0 <= successes <= n and n >= 1")
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half), successes, n)


def case_means(results: Iterable[tuple[str, bool]]) -> dict[str, float]:
    """Mean pass rate per case across its repeats."""
    seen: dict[str, list[bool]] = defaultdict(list)
    for case_id, ok in results:
        seen[case_id].append(ok)
    return {cid: sum(v) / len(v) for cid, v in seen.items()}


def rate_over_cases(means: Mapping[str, float]) -> float:
    """Mean of per-case means: every case counts once."""
    if not means:
        raise MetricError("no cases")
    return sum(means.values()) / len(means)


def unstable_cases(statuses: Iterable[tuple[str, str]]) -> list[str]:
    """Case ids whose repeats did not all give the same status (run-to-run variance, E2)."""
    seen: dict[str, set[str]] = defaultdict(set)
    for case_id, status in statuses:
        seen[case_id].add(status)
    return sorted(cid for cid, s in seen.items() if len(s) > 1)


@dataclass(frozen=True)
class Paired:
    gained: int
    lost: int
    both: int
    neither: int
    p_value: float


def sign_test_p(gained: int, lost: int) -> float:
    """Two-sided exact sign test; ties are excluded. 1.0 when there are no discordant cases."""
    n = gained + lost
    if n == 0:
        return 1.0
    k = min(gained, lost)
    tail = sum(comb(n, i) for i in range(k + 1)) / (1 << n)
    return min(1.0, 2 * tail)


def paired(a: Mapping[str, bool], b: Mapping[str, bool]) -> Paired:
    """Compare B against A on the same cases. `gained` = B right, A wrong."""
    if set(a) != set(b):
        raise MetricError("paired comparison needs the same case ids on both sides")
    gained = sum(1 for k in a if b[k] and not a[k])
    lost = sum(1 for k in a if a[k] and not b[k])
    both = sum(1 for k in a if a[k] and b[k])
    neither = len(a) - gained - lost - both
    return Paired(gained, lost, both, neither, sign_test_p(gained, lost))


def cohens_kappa(a: Sequence[bool], b: Sequence[bool]) -> float:
    """Cohen's kappa for two binary raters. Raises when it is undefined (all one class)."""
    if len(a) != len(b) or not a:
        raise MetricError("raters need equal, non-empty label lists")
    n = len(a)
    observed = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    pa, pb = sum(a) / n, sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    if expected == 1.0:
        raise MetricError("kappa is undefined when both raters use a single class")
    return (observed - expected) / (1 - expected)


@dataclass(frozen=True)
class JudgeVerdict:
    accepted: bool
    kappa: float | None
    false_supported: int
    minority_statements: int
    reason: str


def judge_acceptance(
    human_supported: Sequence[bool],
    judge_supported: Sequence[bool],
    *,
    kappa_min: float,
    false_supported_max: int,
    min_minority_class_statements: int,
) -> JudgeVerdict:
    """The pre-registered rule: all three conditions must hold, else the judge is uncalibrated.

    `false_supported` counts statements the judge called supported and the human did not.
    """
    if len(human_supported) != len(judge_supported) or not human_supported:
        raise MetricError("need paired, non-empty labels")
    yes = sum(human_supported)
    minority = min(yes, len(human_supported) - yes)
    false_supported = sum(
        1 for h, j in zip(human_supported, judge_supported, strict=True) if j and not h
    )
    if minority < min_minority_class_statements:
        return JudgeVerdict(
            False, None, false_supported, minority, "too few statements in the minority class"
        )
    kappa = cohens_kappa(human_supported, judge_supported)
    if kappa < kappa_min:
        return JudgeVerdict(False, kappa, false_supported, minority, "kappa below the minimum")
    if false_supported > false_supported_max:
        return JudgeVerdict(False, kappa, false_supported, minority, "too many false 'supported'")
    return JudgeVerdict(True, kappa, false_supported, minority, "accepted")


@dataclass(frozen=True)
class FindingScore:
    """End-to-end truth recall for one claim: seeded anomaly types reported vs expected."""

    expected: frozenset[str]
    reported: frozenset[str]

    @property
    def hit(self) -> frozenset[str]:
        return self.expected & self.reported

    @property
    def missed(self) -> frozenset[str]:
        return self.expected - self.reported

    @property
    def recall(self) -> float:
        if not self.expected:
            raise MetricError("recall is undefined with no expected anomalies")
        return len(self.hit) / len(self.expected)


def status_ok(status: str, expected: Iterable[str]) -> bool:
    """A case passes the status check when the shown status is one the case accepts."""
    return status in set(expected)
