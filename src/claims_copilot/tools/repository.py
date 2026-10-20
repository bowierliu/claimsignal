"""The only door from tools to data: a read-only view of `payer.sqlite`.

Guards, each tested:
- the file must not be the ground-truth store, and must contain no truth-like table or column;
- the connection is opened read-only, with `query_only` on and ATTACH disabled, so a tool cannot
  write or reach another database file;
- every statement here is fixed text with bound parameters, never built from input.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from claims_copilot.project import SYNTH_OUT_DIR
from claims_copilot.synth.store import PAYER_FILE, TRUTH_FILE
from claims_copilot.tools.errors import NotFoundError

FORBIDDEN_WORDS = ("truth", "anomaly", "decoy", "variant")
DEFAULT_PAYER_PATH = SYNTH_OUT_DIR / PAYER_FILE


class RepositoryError(RuntimeError):
    """The database failed a guard check. The message names the check, not file contents."""


@dataclass(frozen=True)
class ClaimRow:
    claim_id: str
    member_id: str
    provider_id: str
    service_from: date
    service_to: date
    place_of_service: str
    total_billed: Decimal
    diagnosis_codes: tuple[str, ...]


@dataclass(frozen=True)
class LineRow:
    line_id: str
    claim_id: str
    line_no: int
    code: str
    modifiers: tuple[str, ...]
    units: int
    billed_amount: Decimal
    service_date: date
    dx_pointer: int


@dataclass(frozen=True)
class FlagRow:
    flag_id: str
    claim_id: str
    screen_code: str
    screen_text: str


@dataclass(frozen=True)
class ProcedureRow:
    code: str
    category: str
    family: str
    level: int


@dataclass(frozen=True)
class ProviderRow:
    provider_id: str
    specialty: str
    region: str
    group_id: str


@dataclass(frozen=True)
class VisitMix:
    """Visit-family line counts for one provider: all visit lines and the highest-level ones."""

    provider_id: str
    specialty: str
    visit_lines: int
    high_lines: int

    @property
    def high_share(self) -> float:
        return self.high_lines / self.visit_lines if self.visit_lines else 0.0


class Repository:
    def __init__(self, con: sqlite3.Connection, path: Path) -> None:
        self._con = con
        self.path = path

    @classmethod
    def open(cls, path: Path = DEFAULT_PAYER_PATH) -> Repository:
        if path.name == TRUTH_FILE:
            raise RepositoryError("refusing to open the ground-truth store")
        if not path.is_file():
            raise RepositoryError(f"payer database not found: {path.name}")
        con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        con.execute("PRAGMA query_only = ON")
        con.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        repo = cls(con, path)
        repo._check_no_truth()
        return repo

    def close(self) -> None:
        self._con.close()

    def _check_no_truth(self) -> None:
        tables = [r[0] for r in self._con.execute("SELECT name FROM sqlite_master")]
        columns = [
            row[0]
            for t in tables
            for row in self._con.execute("SELECT name FROM pragma_table_info(?)", (t,))
        ]
        for name in tables + columns:
            if any(word in name.lower() for word in FORBIDDEN_WORDS):
                raise RepositoryError("database contains a ground-truth-like table or column")

    # ---- claims and lines -------------------------------------------------------------

    def claim(self, claim_id: str) -> ClaimRow:
        row = self._con.execute(
            "SELECT claim_id, member_id, provider_id, service_from, service_to,"
            " place_of_service, total_billed FROM claim WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("no such claim")
        dx = self._con.execute(
            "SELECT code FROM claim_diagnosis WHERE claim_id = ? ORDER BY seq", (claim_id,)
        ).fetchall()
        return _claim_row(row, tuple(r[0] for r in dx))

    def claims_for(self, column: str, value: str, limit: int | None = None) -> list[ClaimRow]:
        """Claims for a member or provider, oldest first. `column` is a fixed choice."""
        sql = {
            "member": "SELECT claim_id, member_id, provider_id, service_from, service_to,"
            " place_of_service, total_billed FROM claim WHERE member_id = ?"
            " ORDER BY service_from, claim_id",
            "provider": "SELECT claim_id, member_id, provider_id, service_from, service_to,"
            " place_of_service, total_billed FROM claim WHERE provider_id = ?"
            " ORDER BY service_from, claim_id",
        }[column]
        rows = self._con.execute(sql, (value,)).fetchall()
        if limit is not None:
            rows = rows[:limit]
        return [_claim_row(r, self._diagnoses(r[0])) for r in rows]

    def _diagnoses(self, claim_id: str) -> tuple[str, ...]:
        dx = self._con.execute(
            "SELECT code FROM claim_diagnosis WHERE claim_id = ? ORDER BY seq", (claim_id,)
        ).fetchall()
        return tuple(r[0] for r in dx)

    def lines(self, claim_id: str) -> list[LineRow]:
        rows = self._con.execute(
            "SELECT line_id, claim_id, line_no, code, units, billed_amount, service_date,"
            " dx_pointer FROM claim_line WHERE claim_id = ? ORDER BY line_no",
            (claim_id,),
        ).fetchall()
        mods = self._modifiers(claim_id)
        return [
            LineRow(
                line_id=r[0],
                claim_id=r[1],
                line_no=r[2],
                code=r[3],
                modifiers=mods.get(r[0], ()),
                units=r[4],
                billed_amount=Decimal(r[5]),
                service_date=date.fromisoformat(r[6]),
                dx_pointer=r[7],
            )
            for r in rows
        ]

    def member_lines(self, member_id: str) -> dict[str, list[LineRow]]:
        """All lines for all of a member's claims, grouped by claim id (one query each)."""
        mods: dict[str, list[str]] = {}
        for line_id, modifier in self._con.execute(
            "SELECT m.line_id, m.modifier FROM line_modifier m"
            " JOIN claim_line l ON l.line_id = m.line_id"
            " JOIN claim c ON c.claim_id = l.claim_id WHERE c.member_id = ?"
            " ORDER BY m.line_id, m.seq",
            (member_id,),
        ):
            mods.setdefault(line_id, []).append(modifier)
        out: dict[str, list[LineRow]] = {}
        for r in self._con.execute(
            "SELECT l.line_id, l.claim_id, l.line_no, l.code, l.units, l.billed_amount,"
            " l.service_date, l.dx_pointer FROM claim_line l"
            " JOIN claim c ON c.claim_id = l.claim_id WHERE c.member_id = ?"
            " ORDER BY l.claim_id, l.line_no",
            (member_id,),
        ):
            out.setdefault(r[1], []).append(
                LineRow(
                    line_id=r[0],
                    claim_id=r[1],
                    line_no=r[2],
                    code=r[3],
                    modifiers=tuple(mods.get(r[0], ())),
                    units=r[4],
                    billed_amount=Decimal(r[5]),
                    service_date=date.fromisoformat(r[6]),
                    dx_pointer=r[7],
                )
            )
        return out

    def _modifiers(self, claim_id: str) -> dict[str, tuple[str, ...]]:
        out: dict[str, list[str]] = {}
        for line_id, modifier in self._con.execute(
            "SELECT m.line_id, m.modifier FROM line_modifier m"
            " JOIN claim_line l ON l.line_id = m.line_id WHERE l.claim_id = ?"
            " ORDER BY m.line_id, m.seq",
            (claim_id,),
        ):
            out.setdefault(line_id, []).append(modifier)
        return {k: tuple(v) for k, v in out.items()}

    def flags_for_claim(self, claim_id: str) -> list[FlagRow]:
        rows = self._con.execute(
            "SELECT flag_id, claim_id, screen_code, screen_text FROM flag"
            " WHERE claim_id = ? ORDER BY flag_id",
            (claim_id,),
        ).fetchall()
        return [FlagRow(*r) for r in rows]

    def flag_queue(
        self, screen_code: str | None, limit: int, after: str | None = None
    ) -> list[FlagRow]:
        """Flags in id order, optionally only those after flag id `after` (cursor paging)."""
        rows = self._con.execute(
            "SELECT flag_id, claim_id, screen_code, screen_text FROM flag"
            " WHERE (? IS NULL OR screen_code = ?) AND (? IS NULL OR flag_id > ?)"
            " ORDER BY flag_id LIMIT ?",
            (screen_code, screen_code, after, after, limit),
        ).fetchall()
        return [FlagRow(*r) for r in rows]

    def count_flags(self, screen_code: str | None) -> int:
        return int(
            self._con.execute(
                "SELECT COUNT(*) FROM flag WHERE (? IS NULL OR screen_code = ?)",
                (screen_code, screen_code),
            ).fetchone()[0]
        )

    def meta(self, key: str) -> str | None:
        """One value from the `meta` table (for example the dataset hash), or None."""
        row = self._con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def count_claims(self) -> int:
        return int(self._con.execute("SELECT COUNT(*) FROM claim").fetchone()[0])

    def claim_ids(self) -> list[str]:
        return [r[0] for r in self._con.execute("SELECT claim_id FROM claim ORDER BY claim_id")]

    # ---- members, providers, codes ----------------------------------------------------

    def member_exists(self, member_id: str) -> bool:
        return (
            self._con.execute("SELECT 1 FROM member WHERE member_id = ?", (member_id,)).fetchone()
            is not None
        )

    def provider(self, provider_id: str) -> ProviderRow:
        row = self._con.execute(
            "SELECT provider_id, specialty, region, group_id FROM provider WHERE provider_id = ?",
            (provider_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("no such provider")
        return ProviderRow(*row)

    def provider_ids(self) -> list[str]:
        return [r[0] for r in self._con.execute("SELECT provider_id FROM provider ORDER BY 1")]

    def provider_totals(self, provider_id: str) -> tuple[int, int, Decimal]:
        """(claim count, line count, total billed) for one provider."""
        amounts = [
            Decimal(r[0])
            for r in self._con.execute(
                "SELECT total_billed FROM claim WHERE provider_id = ?", (provider_id,)
            )
        ]
        lines = self._con.execute(
            "SELECT COUNT(*) FROM claim_line l JOIN claim c ON c.claim_id = l.claim_id"
            " WHERE c.provider_id = ?",
            (provider_id,),
        ).fetchone()[0]
        return len(amounts), int(lines), sum(amounts, Decimal("0"))

    def procedure_codes(self) -> dict[str, ProcedureRow]:
        return {
            r[0]: ProcedureRow(*r)
            for r in self._con.execute(
                "SELECT code, category, family, level FROM procedure_code ORDER BY code"
            )
        }

    def bundle_pairs(self) -> list[tuple[str, str, str]]:
        return [
            (r[0], r[1], r[2])
            for r in self._con.execute(
                "SELECT comprehensive_code, component_code, exception_modifier FROM bundle_pair"
                " ORDER BY comprehensive_code, component_code"
            )
        ]

    def unit_limits(self) -> dict[str, int]:
        return {
            r[0]: int(r[1])
            for r in self._con.execute("SELECT code, max_units FROM unit_limit ORDER BY code")
        }

    def visit_mix(self) -> list[VisitMix]:
        """Per provider: visit-family lines, and lines at the highest visit level."""
        rows = self._con.execute(
            "SELECT p.provider_id, p.specialty, COUNT(*),"
            " SUM(CASE WHEN pc.level = (SELECT MAX(level) FROM procedure_code"
            "   WHERE family = pc.family) THEN 1 ELSE 0 END)"
            " FROM claim_line l JOIN claim c ON c.claim_id = l.claim_id"
            " JOIN provider p ON p.provider_id = c.provider_id"
            " JOIN procedure_code pc ON pc.code = l.code"
            " WHERE pc.family = 'VISIT' GROUP BY p.provider_id, p.specialty"
            " ORDER BY p.provider_id"
        ).fetchall()
        return [VisitMix(r[0], r[1], int(r[2]), int(r[3])) for r in rows]


def _claim_row(row: tuple[str, ...], diagnoses: tuple[str, ...]) -> ClaimRow:
    return ClaimRow(
        claim_id=row[0],
        member_id=row[1],
        provider_id=row[2],
        service_from=date.fromisoformat(row[3]),
        service_to=date.fromisoformat(row[4]),
        place_of_service=row[5],
        total_billed=Decimal(row[6]),
        diagnosis_codes=diagnoses,
    )
