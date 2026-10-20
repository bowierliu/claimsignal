"""The hand-built tool fixture (Phase 7, layer "tools_handbuilt" and experiment E5).

Twenty claim scenarios written out by hand, in a small payer database that is not made by the
Phase 2 generator, so the expected result of each is known by construction and does not depend on
how the generator shapes its anomalies (KF-011). Six of the twenty are provider-level cases built
on peer groups whose spread was chosen to look like a real group: about 10% of peers elevated in
one group and none in another, not the 33% to 40% that packing seeded outliers produced (KF-017).

Expected values are written here, before any run, from the definitions of the checks and, for the
visit-mix statistic, from the formula worked out by hand in the comments below. This module never
opens a truth store (there is none) and never calls a provider.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from claims_copilot.agent.answer import Status
from claims_copilot.evals.schema import EvalCase, Layer
from claims_copilot.synth.codes import BUNDLE_PAIRS, PROCEDURE_CODES, UNIT_LIMITS
from claims_copilot.tools.dossier import claim_dossier
from claims_copilot.tools.patterns import PeerBook
from claims_copilot.tools.repository import Repository
from claims_copilot.tools.rules import SyntheticRules

# Check names, as the tools emit them (stable machine names).
BUNDLE = "bundle_pair_without_exception"
UNITS = "units_above_line_limit"
LINE_DATE = "line_date_outside_claim_window"
WINDOW = "claim_window_reversed"
EXACT_DUP = "exact_duplicate"
POINTER = "diagnosis_pointer_out_of_range"
INTENSITY = "visit_mix_above_peer_range"
# Observations, not findings (shown for context, rule not tripped).
BUNDLE_WITH_EXCEPTION = "bundle_pair_with_exception"
NEAR_PROVIDER = "near_match_other_provider"
NEAR_DATE = "near_match_nearby_date"

HANDBUILT_DIR_NAME = "handbuilt"
HANDBUILT_FILE = "payer.sqlite"

VISIT_LOW, VISIT_MID, VISIT_HIGH = "X0001", "X0002", "X0003"

# Peer visit mixes, high-level lines out of 50 per provider. Written by hand, not drawn at random.
# The clean group has median 13.5/50 = 0.27 and MAD 0.05 (worked out by hand).
CLEAN_PEERS = (
    8, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12, 12, 13, 13, 13,
    14, 14, 14, 15, 15, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21,
)  # fmt: skip
# The "contaminated" group replaces the last three peers with three elevated ones (3 of 30 = 10%).
CONTAMINATED_PEERS = (*CLEAN_PEERS[:27], 30, 31, 32)
SMALL_GROUP_PEERS = (10, 12, 13, 14, 15, 18)  # 6 peers: under the 10-peer minimum
LINES_PER_PEER = 50


@dataclass(frozen=True)
class L:
    code: str
    units: int = 1
    mods: tuple[str, ...] = ()
    day: str | None = None
    dx_pointer: int = 1


@dataclass(frozen=True)
class Scenario:
    """One hand-built case. `expected_findings` is the exact set of finding check names the dossier
    must contain; `expected_observations` the observation names that must be present."""

    case_id: str
    claim_id: str
    description: str
    expected_findings: frozenset[str]
    expected_observations: frozenset[str] = frozenset()
    decoy: bool = False  # looks like a problem but is not one: expect no finding

    def to_eval_case(self) -> EvalCase:
        return EvalCase(
            case_id=self.case_id,
            layer=Layer.TOOLS_HANDBUILT,
            question=(
                f"Summarise the evidence for claim {self.claim_id}: what do the checks and flags "
                "show?"
            ),
            expected_statuses=(Status.ANSWERED, Status.CONFLICTING_EVIDENCE),
            claim_id=self.claim_id,
            note=self.description,
        )


class _Builder:
    def __init__(self, path: Path) -> None:
        from claims_copilot.synth.store import PAYER_SCHEMA

        if path.exists():
            path.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.con = sqlite3.connect(path)
        self.con.executescript(PAYER_SCHEMA)
        self.con.executemany(
            "INSERT INTO procedure_code VALUES (?,?,?,?,?,?)",
            [
                (c.code, c.code_system, c.category, c.family, c.level, str(c.typical_charge))
                for c in PROCEDURE_CODES
            ],
        )
        self.con.executemany(
            "INSERT INTO bundle_pair VALUES (?,?,?)",
            [(b.comprehensive_code, b.component_code, b.exception_modifier) for b in BUNDLE_PAIRS],
        )
        self.con.executemany(
            "INSERT INTO unit_limit VALUES (?,?)", [(u.code, u.max_units) for u in UNIT_LIMITS]
        )
        self.con.execute("INSERT INTO meta VALUES ('payer_hash', 'handbuilt-phase7-v1')")
        self._members: set[str] = set()
        self._providers: set[str] = set()
        self._flags = 0

    def member(self, member_id: str) -> None:
        if member_id not in self._members:
            self.con.execute(
                "INSERT INTO member VALUES (?,?,?,?,?)", (member_id, "45-64", "F", "PPO", "R1")
            )
            self._members.add(member_id)

    def provider(self, provider_id: str, specialty: str) -> None:
        if provider_id not in self._providers:
            self.con.execute(
                "INSERT INTO provider VALUES (?,?,?,?)", (provider_id, specialty, "R1", "G1")
            )
            self._providers.add(provider_id)

    def claim(
        self,
        claim_id: str,
        lines: Sequence[L],
        *,
        member: str,
        provider: str,
        specialty: str = "primary_care",
        start: str = "2026-11-02",
        end: str | None = None,
        dx: Sequence[str] = ("E119",),
    ) -> str:
        self.member(member)
        self.provider(provider, specialty)
        self.con.execute(
            "INSERT INTO claim VALUES (?,?,?,?,?,?,?)",
            (claim_id, member, provider, start, end or start, "PS1", "100.00"),
        )
        for seq, code in enumerate(dx, start=1):
            self.con.execute(
                "INSERT OR IGNORE INTO diagnosis_code VALUES (?, 'ICD10CM_FY2027')", (code,)
            )
            self.con.execute("INSERT INTO claim_diagnosis VALUES (?,?,?)", (claim_id, seq, code))
        for n, ln in enumerate(lines, start=1):
            line_id = f"{claim_id}-{n:02d}"
            self.con.execute(
                "INSERT INTO claim_line VALUES (?,?,?,?,?,?,?,?)",
                (line_id, claim_id, n, ln.code, ln.units, "10.00", ln.day or start, ln.dx_pointer),
            )
            for seq, mod in enumerate(ln.mods, start=1):
                self.con.execute("INSERT INTO line_modifier VALUES (?,?,?)", (line_id, seq, mod))
        return claim_id

    def flag(self, claim_id: str) -> None:
        """Every scenario claim carries one generic screen flag, as a flagged claim would."""
        self._flags += 1
        self.con.execute(
            "INSERT INTO flag VALUES (?,?,?,?)",
            (f"F{self._flags:06d}", claim_id, "SCR01", "Claim selected by a screening rule."),
        )

    def peer_group(self, specialty: str, first_provider: int, highs: Sequence[int]) -> None:
        """One provider per entry; each has 10 claims of 5 visit lines (50 lines in all)."""
        for i, high in enumerate(highs):
            pid = f"P{first_provider + i:04d}"
            self.visit_provider(pid, specialty, high, LINES_PER_PEER, f"{pid[1:]}")

    def visit_provider(
        self, provider_id: str, specialty: str, high: int, total: int, tag: str
    ) -> list[str]:
        """`total` visit lines, `high` of them at the highest level, 5 lines per claim."""
        codes = [VISIT_HIGH] * high + [VISIT_MID, VISIT_LOW] * total
        codes = codes[:total]
        claim_ids: list[str] = []
        for c in range(0, total, 5):
            claim_id = f"C{int(tag):04d}{c // 5:03d}"
            lines = [L(code) for code in codes[c : c + 5]]
            self.claim(
                claim_id,
                lines,
                member=f"M{int(tag):04d}{c // 5:02d}",
                provider=provider_id,
                specialty=specialty,
            )
            claim_ids.append(claim_id)
        return claim_ids


# Provider-level subjects. Worked out by hand against the groups above (visit-level share, then
# 0.6745 * (share - median) / MAD with the subject excluded from its own peers):
#   clean group (median 0.27, MAD 0.05): 35/50 = 0.70 -> 5.8 (flag);  18/50 = 0.36 -> 1.2 (no flag);
#   5/50 = 0.10 -> -2.3 (no flag). Adding the other subjects as peers moves median and MAD by less
#   than 0.01, far from the 3.5 cutoff on either side.
#   contaminated group (3 of 30 peers elevated, median 0.27, MAD 0.05): 36/50 = 0.72 -> 6.1 (flag).
#   sparse subject: 30 visit lines is under the 40-line minimum -> not scored.
#   small group: 6 peers is under the 10-peer minimum -> not scored.
def build_handbuilt(path: Path) -> list[Scenario]:
    """Write the database and return the 20 scenarios. Deterministic: the same call, same bytes."""
    b = _Builder(path)
    sc: list[Scenario] = []

    def add(
        n: int,
        claim_id: str,
        description: str,
        findings: Sequence[str] = (),
        observations: Sequence[str] = (),
        *,
        decoy: bool = False,
    ) -> None:
        b.flag(claim_id)
        sc.append(
            Scenario(
                f"hb-{n:02d}",
                claim_id,
                description,
                frozenset(findings),
                frozenset(observations),
                decoy,
            )
        )

    # Peer groups first (they are the background the provider-level scenarios are scored against).
    b.peer_group("primary_care", 1001, CLEAN_PEERS)  # P1001..P1030
    b.peer_group("internal_medicine", 1101, CONTAMINATED_PEERS)  # P1101..P1130
    b.peer_group("cardiology", 1201, SMALL_GROUP_PEERS)  # P1201..P1206

    n = 0

    def m(i: int) -> str:
        return f"M9{i:05d}"

    def c(i: int) -> str:
        return f"C9{i:06d}"

    # --- claim-level scenarios (14) ---
    n += 1
    b.claim(
        c(n),
        [L("X0010"), L("X0011")],
        member=m(n),
        provider="P9001",
    )
    add(n, c(n), "X0011 billed with its comprehensive code X0010, same date, no M1", [BUNDLE])

    n += 1
    b.claim(c(n), [L("X0010"), L("X0011", mods=("M1",))], member=m(n), provider="P9001")
    add(
        n,
        c(n),
        "same pair, but the component carries the exception modifier M1",
        observations=[BUNDLE_WITH_EXCEPTION],
        decoy=True,
    )

    n += 1
    b.claim(
        c(n),
        [L("X0010", day="2026-11-02"), L("X0011", day="2026-11-03")],
        member=m(n),
        provider="P9001",
        end="2026-11-03",
    )
    add(n, c(n), "same pair on different dates within the window: the rule is same-date only",
        decoy=True)  # fmt: skip

    n += 1
    b.claim(c(n), [L("X0030", units=5)], member=m(n), provider="P9001")
    add(n, c(n), "5 units of X0030 against a per-line limit of 3", [UNITS])

    n += 1
    b.claim(c(n), [L("X0030", units=3)], member=m(n), provider="P9001")
    add(n, c(n), "exactly 3 units of X0030, which is at the limit, not over", decoy=True)

    n += 1
    b.claim(c(n), [L("X0001", units=2)], member=m(n), provider="P9001")
    add(n, c(n), "2 units of a visit code whose per-line limit is 1", [UNITS])

    n += 1
    b.claim(
        c(n),
        [L("X0001"), L("X0030", day="2026-10-28")],
        member=m(n),
        provider="P9001",
    )
    add(n, c(n), "a line dated 5 days before the claim window", [LINE_DATE])

    n += 1
    b.claim(
        c(n),
        [L("X0001"), L("X0030", day="2026-11-09")],
        member=m(n),
        provider="P9001",
    )
    add(n, c(n), "a line dated 7 days after the claim window", [LINE_DATE])

    n += 1
    b.claim(c(n), [L("X0001")], member=m(n), provider="P9001", start="2026-11-05", end="2026-11-02")
    # The line is dated on the claim's start (11-05), which is after the claim's end (11-02), so the
    # line-date check also trips by its definition; no date can fall inside a reversed window.
    add(n, c(n), "service end date earlier than the start date", [WINDOW, LINE_DATE])

    n += 1
    b.claim(
        c(n),
        [L("X0001", day="2026-11-02"), L("X0030", day="2026-11-04")],
        member=m(n),
        provider="P9001",
        end="2026-11-04",
    )
    add(n, c(n), "lines on the first and last day of the window: both ends are inclusive",
        decoy=True)  # fmt: skip

    n += 1
    dup_a = c(n)
    b.claim(dup_a, [L("X0001"), L("X0030")], member=m(n), provider="P9002")
    # The twin claim is a separate claim row for the same member, provider, window and lines.
    twin = f"C9{n + 50:06d}"
    b.claim(twin, [L("X0001"), L("X0030")], member=m(n), provider="P9002")
    b.flag(twin)
    add(n, dup_a, "a second claim with the same member, provider, window and lines", [EXACT_DUP])

    n += 1
    b.claim(c(n), [L("X0001"), L("X0030")], member=m(n), provider="P9002")
    b.claim(f"C9{n + 50:06d}", [L("X0001"), L("X0030")], member=m(n), provider="P9003")
    add(
        n,
        c(n),
        "identical lines from a different provider on the same date: context only",
        observations=[NEAR_PROVIDER],
        decoy=True,
    )

    n += 1
    b.claim(c(n), [L("X0001"), L("X0030", units=2)], member=m(n), provider="P9002")
    b.claim(f"C9{n + 50:06d}", [L("X0001"), L("X0030", units=3)], member=m(n), provider="P9002")
    add(n, c(n), "same member, provider, date and codes, but different units: not a duplicate",
        decoy=True)  # fmt: skip

    n += 1
    b.claim(c(n), [L("X0001", dx_pointer=3)], member=m(n), provider="P9001")
    add(n, c(n), "a line points to diagnosis 3 on a claim with one diagnosis", [POINTER])

    # --- provider-level scenarios (6) ---
    def subject(i: int, provider: str, specialty: str, high: int, total: int) -> str:
        ids = b.visit_provider(provider, specialty, high, total, provider[1:])
        return ids[0]

    n += 1
    claim_id = subject(n, "P2001", "primary_care", 35, LINES_PER_PEER)
    add(n, claim_id, "a provider at 70% highest-level visits against a clean peer group of 30",
        [INTENSITY])  # fmt: skip

    n += 1
    claim_id = subject(n, "P2002", "primary_care", 18, LINES_PER_PEER)
    add(n, claim_id, "a provider at 36% highest-level visits: above the median, within range",
        decoy=True)  # fmt: skip

    n += 1
    claim_id = subject(n, "P2003", "primary_care", 5, LINES_PER_PEER)
    add(n, claim_id, "a provider at 10% highest-level visits: low, not elevated", decoy=True)

    n += 1
    claim_id = subject(n, "P2004", "internal_medicine", 36, LINES_PER_PEER)
    add(n, claim_id, "a provider at 72% against a peer group where 3 of 30 peers are elevated",
        [INTENSITY])  # fmt: skip

    n += 1
    claim_id = subject(n, "P2005", "primary_care", 24, 30)
    add(n, claim_id, "80% highest-level visits, but only 30 visit lines: under the 40-line minimum",
        decoy=True)  # fmt: skip

    n += 1
    claim_id = subject(n, "P2006", "cardiology", 40, LINES_PER_PEER)
    add(n, claim_id, "80% highest-level visits, but only 6 same-specialty peers: not scored",
        decoy=True)  # fmt: skip

    b.con.commit()
    b.con.close()
    if len(sc) != 20:
        raise AssertionError(f"expected 20 hand-built scenarios, built {len(sc)}")
    return sc


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    findings: frozenset[str]
    observations: frozenset[str]

    @property
    def exact(self) -> bool:
        return self.findings == self.scenario.expected_findings

    @property
    def missed(self) -> frozenset[str]:
        return self.scenario.expected_findings - self.findings

    @property
    def extra(self) -> frozenset[str]:
        return self.findings - self.scenario.expected_findings

    @property
    def observations_ok(self) -> bool:
        return self.scenario.expected_observations <= self.observations


@dataclass(frozen=True)
class HandbuiltScore:
    results: tuple[ScenarioResult, ...]

    @property
    def exact(self) -> int:
        return sum(1 for r in self.results if r.exact)

    @property
    def expected_total(self) -> int:
        return sum(len(r.scenario.expected_findings) for r in self.results)

    @property
    def found_total(self) -> int:
        return sum(len(r.scenario.expected_findings & r.findings) for r in self.results)

    @property
    def false_alarms(self) -> int:
        """Findings raised that the scenario did not expect (decoys and everything else)."""
        return sum(len(r.extra) for r in self.results)

    @property
    def decoys_raised(self) -> int:
        return sum(1 for r in self.results if r.scenario.decoy and r.findings)


def score_handbuilt(path: Path, scenarios: Sequence[Scenario]) -> HandbuiltScore:
    """Run the dossier over every scenario claim (diagnosis codes not checked: no code list)."""
    repo = Repository.open(path)
    try:
        rules = SyntheticRules(repo)
        book = PeerBook.from_repo(repo)
        out: list[ScenarioResult] = []
        for s in scenarios:
            dossier = claim_dossier(repo, rules, s.claim_id, icd=None, book=book)
            findings = frozenset(f.check for r in dossier.results for f in r.findings)
            observations = frozenset(f.check for r in dossier.results for f in r.observations)
            out.append(ScenarioResult(s, findings, observations))
    finally:
        repo.close()
    return HandbuiltScore(tuple(out))


def scorecard_markdown(score: HandbuiltScore) -> str:
    lines = [
        "# Phase 7 E5: tools against the hand-built scenarios",
        "",
        f"Scenarios {len(score.results)}; exact match {score.exact}/{len(score.results)}; "
        f"expected findings found {score.found_total}/{score.expected_total}; "
        f"false alarms {score.false_alarms}; decoys that raised a finding {score.decoys_raised}.",
        "",
        "| case | claim | decoy | expected | found | result |",
        "|---|---|---|---|---|---|",
    ]
    for r in score.results:
        ok = r.exact and r.observations_ok
        lines.append(
            f"| {r.scenario.case_id} | {r.scenario.claim_id} | {'yes' if r.scenario.decoy else ''} "
            f"| {', '.join(sorted(r.scenario.expected_findings)) or '-'} "
            f"| {', '.join(sorted(r.findings)) or '-'} | {'ok' if ok else 'MISMATCH'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    import json

    from claims_copilot.project import DATA_DIR, REPO_ROOT

    path = DATA_DIR / "eval" / HANDBUILT_DIR_NAME / HANDBUILT_FILE
    scenarios = build_handbuilt(path)
    score = score_handbuilt(path, scenarios)
    out = REPO_ROOT / "eval" / "scorecards"
    out.mkdir(parents=True, exist_ok=True)
    (out / "phase7_e5_handbuilt.md").write_text(scorecard_markdown(score), encoding="utf-8")
    payload = {
        "scenarios": len(score.results),
        "exact": score.exact,
        "expected_findings": score.expected_total,
        "found": score.found_total,
        "false_alarms": score.false_alarms,
        "decoys_raised": score.decoys_raised,
        "results": [
            {
                "case_id": r.scenario.case_id,
                "claim_id": r.scenario.claim_id,
                "decoy": r.scenario.decoy,
                "expected": sorted(r.scenario.expected_findings),
                "found": sorted(r.findings),
                "observations": sorted(r.observations),
            }
            for r in score.results
        ],
    }
    (out / "phase7_e5_handbuilt.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print((out / "phase7_e5_handbuilt.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
