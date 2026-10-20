"""A tiny hand-built payer database for tool tests.

Rules here are written out by hand so tool tests do not depend on the generator:
X0010 is comprehensive and X0011 its component (exception modifier M1); X0020 allows 2 units.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from claims_copilot.synth.codes import PROCEDURE_CODES
from claims_copilot.synth.store import PAYER_SCHEMA
from claims_copilot.tools.icd import IcdCodeSet
from claims_copilot.tools.repository import Repository
from claims_copilot.tools.rules import SyntheticRules

D = date.fromisoformat


@dataclass(frozen=True)
class L:
    """One line to add: code, units, modifiers, service date (default: the claim's start)."""

    code: str
    units: int = 1
    mods: tuple[str, ...] = ()
    day: str | None = None


class Db:
    def __init__(self, path: Path) -> None:
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
        self.con.execute("INSERT INTO bundle_pair VALUES ('X0010','X0011','M1')")
        self.con.execute("INSERT INTO unit_limit VALUES ('X0020', 2)")
        for code in ("E119", "I10", "Z000"):
            self.con.execute("INSERT INTO diagnosis_code VALUES (?, 'ICD10CM_FY2027')", (code,))
        self._members: set[str] = set()
        self._providers: set[str] = set()
        self._lines = 0

    def provider(self, provider_id: str, specialty: str = "primary_care") -> None:
        if provider_id not in self._providers:
            self.con.execute(
                "INSERT INTO provider VALUES (?,?,?,?)", (provider_id, specialty, "R1", "G1")
            )
            self._providers.add(provider_id)

    def member(self, member_id: str) -> None:
        if member_id not in self._members:
            self.con.execute(
                "INSERT INTO member VALUES (?,?,?,?,?)", (member_id, "45-64", "F", "PPO", "R1")
            )
            self._members.add(member_id)

    def claim(
        self,
        claim_id: str,
        lines: Sequence[L],
        member: str = "M000001",
        provider: str = "P0001",
        start: str = "2026-11-02",
        end: str | None = None,
        dx: Sequence[str] = ("E119",),
        specialty: str = "primary_care",
    ) -> str:
        self.member(member)
        self.provider(provider, specialty)
        end = end or start
        self.con.execute(
            "INSERT INTO claim VALUES (?,?,?,?,?,?,?)",
            (claim_id, member, provider, start, end, "PS1", "100.00"),
        )
        for seq, code in enumerate(dx, start=1):
            self.con.execute(
                "INSERT OR IGNORE INTO diagnosis_code VALUES (?, 'ICD10CM_FY2027')", (code,)
            )
            self.con.execute("INSERT INTO claim_diagnosis VALUES (?,?,?)", (claim_id, seq, code))
        for n, ln in enumerate(lines, start=1):
            self._lines += 1
            line_id = f"{claim_id}-{n:02d}"
            self.con.execute(
                "INSERT INTO claim_line VALUES (?,?,?,?,?,?,?,?)",
                (line_id, claim_id, n, ln.code, ln.units, "10.00", ln.day or start, 1),
            )
            for seq, mod in enumerate(ln.mods, start=1):
                self.con.execute("INSERT INTO line_modifier VALUES (?,?,?)", (line_id, seq, mod))
        return claim_id

    def flag(self, flag_id: str, claim_id: str, screen: str = "SCR01") -> None:
        self.con.execute(
            "INSERT INTO flag VALUES (?,?,?,?)", (flag_id, claim_id, screen, "screen text")
        )

    def open(self) -> Repository:
        self.con.commit()
        return Repository.open(self.path)


def rules_for(repo: Repository) -> SyntheticRules:
    return SyntheticRules(repo)


def icd_fixture(*codes: str) -> IcdCodeSet:
    return IcdCodeSet(
        codes=frozenset(codes), valid_from=D("2026-10-01"), valid_to=D("2027-09-30"), name="fixture"
    )
