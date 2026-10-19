"""SQLite persistence for the synthetic dataset.

Two files, on purpose:

- `payer.sqlite` holds everything a tool or the agent may see (members, providers, claims, lines,
  flags, code tables, rule tables).
- `truth.sqlite` holds the seeded ground truth. Only evaluations open it.

Money is stored as exact decimal text and dates as ISO text. Row order is insertion order, so a
dataset read back hashes identically to the one written.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from claims_copilot.synth.config import GeneratorConfig
from claims_copilot.synth.dataset import Dataset, payer_hash, truth_hash
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

PAYER_FILE = "payer.sqlite"
TRUTH_FILE = "truth.sqlite"

PAYER_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE member (
  member_id TEXT PRIMARY KEY, age_band TEXT NOT NULL, sex TEXT NOT NULL,
  plan_type TEXT NOT NULL, region TEXT NOT NULL);
CREATE TABLE provider (
  provider_id TEXT PRIMARY KEY, specialty TEXT NOT NULL, region TEXT NOT NULL,
  group_id TEXT NOT NULL);
CREATE TABLE procedure_code (
  code TEXT PRIMARY KEY, code_system TEXT NOT NULL, category TEXT NOT NULL,
  family TEXT NOT NULL, level INTEGER NOT NULL, typical_charge TEXT NOT NULL);
CREATE TABLE diagnosis_code (code TEXT PRIMARY KEY, code_system TEXT NOT NULL);
CREATE TABLE bundle_pair (
  comprehensive_code TEXT NOT NULL REFERENCES procedure_code(code),
  component_code TEXT NOT NULL REFERENCES procedure_code(code),
  exception_modifier TEXT NOT NULL,
  PRIMARY KEY (comprehensive_code, component_code));
CREATE TABLE unit_limit (
  code TEXT PRIMARY KEY REFERENCES procedure_code(code), max_units INTEGER NOT NULL);
CREATE TABLE claim (
  claim_id TEXT PRIMARY KEY,
  member_id TEXT NOT NULL REFERENCES member(member_id),
  provider_id TEXT NOT NULL REFERENCES provider(provider_id),
  service_from TEXT NOT NULL, service_to TEXT NOT NULL, place_of_service TEXT NOT NULL,
  total_billed TEXT NOT NULL);
CREATE TABLE claim_diagnosis (
  claim_id TEXT NOT NULL REFERENCES claim(claim_id), seq INTEGER NOT NULL,
  code TEXT NOT NULL REFERENCES diagnosis_code(code), PRIMARY KEY (claim_id, seq));
CREATE TABLE claim_line (
  line_id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claim(claim_id),
  line_no INTEGER NOT NULL, code TEXT NOT NULL REFERENCES procedure_code(code),
  units INTEGER NOT NULL, billed_amount TEXT NOT NULL, service_date TEXT NOT NULL,
  dx_pointer INTEGER NOT NULL);
CREATE TABLE line_modifier (
  line_id TEXT NOT NULL REFERENCES claim_line(line_id), seq INTEGER NOT NULL,
  modifier TEXT NOT NULL, PRIMARY KEY (line_id, seq));
CREATE TABLE flag (
  flag_id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claim(claim_id),
  screen_code TEXT NOT NULL, screen_text TEXT NOT NULL);
CREATE INDEX idx_claim_member ON claim(member_id);
CREATE INDEX idx_claim_provider ON claim(provider_id);
CREATE INDEX idx_claim_from ON claim(service_from);
CREATE INDEX idx_line_claim ON claim_line(claim_id);
CREATE INDEX idx_line_code ON claim_line(code);
CREATE INDEX idx_flag_claim ON flag(claim_id);
"""

TRUTH_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE anomaly_truth (
  anomaly_id TEXT PRIMARY KEY, anomaly_type TEXT NOT NULL, is_decoy INTEGER NOT NULL,
  variant TEXT NOT NULL, provider_id TEXT NOT NULL, explanation TEXT NOT NULL);
CREATE TABLE truth_claim (
  anomaly_id TEXT NOT NULL REFERENCES anomaly_truth(anomaly_id), seq INTEGER NOT NULL,
  claim_id TEXT NOT NULL, PRIMARY KEY (anomaly_id, seq));
CREATE TABLE truth_line (
  anomaly_id TEXT NOT NULL REFERENCES anomaly_truth(anomaly_id), seq INTEGER NOT NULL,
  line_id TEXT NOT NULL, PRIMARY KEY (anomaly_id, seq));
"""


def _config_json(cfg: GeneratorConfig) -> str:
    raw = asdict(cfg)
    return json.dumps({k: v.isoformat() if isinstance(v, date) else v for k, v in raw.items()})


def _config_from_json(text: str) -> GeneratorConfig:
    raw = json.loads(text)
    for key in ("window_start", "window_end"):
        raw[key] = date.fromisoformat(raw[key])
    return GeneratorConfig(**raw)


def _insert(con: sqlite3.Connection, sql: str, rows: Sequence[Sequence[object]]) -> None:
    con.executemany(sql, rows)


def _create(path: Path, schema: str) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)  # regenerating our own output file
    con = sqlite3.connect(path)
    con.executescript(schema)
    return con


def write_dataset(ds: Dataset, out_dir: Path) -> tuple[Path, Path]:
    payer_path, truth_path = out_dir / PAYER_FILE, out_dir / TRUTH_FILE
    p_hash = payer_hash(ds)
    con = _create(payer_path, PAYER_SCHEMA)
    with con:
        _insert(
            con,
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("config", _config_json(ds.config)),
                ("payer_hash", p_hash),
            ],
        )
        _insert(
            con,
            "INSERT INTO member VALUES (?,?,?,?,?)",
            [(m.member_id, m.age_band, m.sex, m.plan_type, m.region) for m in ds.members],
        )
        _insert(
            con,
            "INSERT INTO provider VALUES (?,?,?,?)",
            [(p.provider_id, p.specialty, p.region, p.group_id) for p in ds.providers],
        )
        _insert(
            con,
            "INSERT INTO procedure_code VALUES (?,?,?,?,?,?)",
            [
                (c.code, c.code_system, c.category, c.family, c.level, str(c.typical_charge))
                for c in ds.procedure_codes
            ],
        )
        _insert(
            con,
            "INSERT INTO diagnosis_code VALUES (?,?)",
            [(d.code, d.code_system) for d in ds.diagnosis_codes],
        )
        _insert(
            con,
            "INSERT INTO bundle_pair VALUES (?,?,?)",
            [
                (b.comprehensive_code, b.component_code, b.exception_modifier)
                for b in ds.bundle_pairs
            ],
        )
        _insert(
            con,
            "INSERT INTO unit_limit VALUES (?,?)",
            [(u.code, u.max_units) for u in ds.unit_limits],
        )
        _insert(
            con,
            "INSERT INTO claim VALUES (?,?,?,?,?,?,?)",
            [
                (
                    c.claim_id,
                    c.member_id,
                    c.provider_id,
                    c.service_from.isoformat(),
                    c.service_to.isoformat(),
                    c.place_of_service,
                    str(c.total_billed),
                )
                for c in ds.claims
            ],
        )
        _insert(
            con,
            "INSERT INTO claim_diagnosis VALUES (?,?,?)",
            [
                (c.claim_id, seq, code)
                for c in ds.claims
                for seq, code in enumerate(c.diagnosis_codes, start=1)
            ],
        )
        _insert(
            con,
            "INSERT INTO claim_line VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    ln.line_id,
                    ln.claim_id,
                    ln.line_no,
                    ln.code,
                    ln.units,
                    str(ln.billed_amount),
                    ln.service_date.isoformat(),
                    ln.dx_pointer,
                )
                for ln in ds.claim_lines
            ],
        )
        _insert(
            con,
            "INSERT INTO line_modifier VALUES (?,?,?)",
            [
                (ln.line_id, seq, mod)
                for ln in ds.claim_lines
                for seq, mod in enumerate(ln.modifiers, start=1)
            ],
        )
        _insert(
            con,
            "INSERT INTO flag VALUES (?,?,?,?)",
            [(f.flag_id, f.claim_id, f.screen_code, f.screen_text) for f in ds.flags],
        )
    con.close()

    con = _create(truth_path, TRUTH_SCHEMA)
    with con:
        _insert(
            con,
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("truth_hash", truth_hash(ds)),
                ("payer_hash", p_hash),
            ],
        )
        _insert(
            con,
            "INSERT INTO anomaly_truth VALUES (?,?,?,?,?,?)",
            [
                (
                    t.anomaly_id,
                    t.anomaly_type,
                    int(t.is_decoy),
                    t.variant,
                    t.provider_id,
                    t.explanation,
                )
                for t in ds.truth
            ],
        )
        _insert(
            con,
            "INSERT INTO truth_claim VALUES (?,?,?)",
            [
                (t.anomaly_id, seq, cid)
                for t in ds.truth
                for seq, cid in enumerate(t.claim_ids, start=1)
            ],
        )
        _insert(
            con,
            "INSERT INTO truth_line VALUES (?,?,?)",
            [
                (t.anomaly_id, seq, lid)
                for t in ds.truth
                for seq, lid in enumerate(t.line_ids, start=1)
            ],
        )
    con.close()
    return payer_path, truth_path


def _grouped(con: sqlite3.Connection, sql: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for key, value in con.execute(sql):
        grouped.setdefault(key, []).append(value)
    return grouped


def load_dataset(out_dir: Path) -> Dataset:
    con = sqlite3.connect(out_dir / PAYER_FILE)
    config = _config_from_json(
        con.execute("SELECT value FROM meta WHERE key='config'").fetchone()[0]
    )
    dx = _grouped(con, "SELECT claim_id, code FROM claim_diagnosis ORDER BY claim_id, seq")
    mods = _grouped(con, "SELECT line_id, modifier FROM line_modifier ORDER BY line_id, seq")
    members = tuple(Member(*r) for r in con.execute("SELECT * FROM member ORDER BY rowid"))
    providers = tuple(Provider(*r) for r in con.execute("SELECT * FROM provider ORDER BY rowid"))
    procedure_codes = tuple(
        ProcedureCode(r[0], r[1], r[2], r[3], r[4], Decimal(r[5]))
        for r in con.execute("SELECT * FROM procedure_code ORDER BY rowid")
    )
    diagnosis_codes = tuple(
        DiagnosisCode(*r) for r in con.execute("SELECT * FROM diagnosis_code ORDER BY rowid")
    )
    bundle_pairs = tuple(
        BundlePair(*r) for r in con.execute("SELECT * FROM bundle_pair ORDER BY rowid")
    )
    unit_limits = tuple(
        UnitLimit(*r) for r in con.execute("SELECT * FROM unit_limit ORDER BY rowid")
    )
    claims = tuple(
        Claim(
            r[0],
            r[1],
            r[2],
            date.fromisoformat(r[3]),
            date.fromisoformat(r[4]),
            r[5],
            tuple(dx.get(r[0], [])),
            Decimal(r[6]),
        )
        for r in con.execute("SELECT * FROM claim ORDER BY rowid")
    )
    claim_lines = tuple(
        ClaimLine(
            r[0],
            r[1],
            r[2],
            r[3],
            tuple(mods.get(r[0], [])),
            r[4],
            Decimal(r[5]),
            date.fromisoformat(r[6]),
            r[7],
        )
        for r in con.execute(
            "SELECT line_id, claim_id, line_no, code, units, billed_amount, service_date, "
            "dx_pointer FROM claim_line ORDER BY rowid"
        )
    )
    flags = tuple(Flag(*r) for r in con.execute("SELECT * FROM flag ORDER BY rowid"))
    con.close()

    truth: tuple[AnomalyTruth, ...] = ()
    truth_path = out_dir / TRUTH_FILE
    if truth_path.exists():
        tcon = sqlite3.connect(truth_path)
        t_claims = _grouped(
            tcon, "SELECT anomaly_id, claim_id FROM truth_claim ORDER BY anomaly_id, seq"
        )
        t_lines = _grouped(
            tcon, "SELECT anomaly_id, line_id FROM truth_line ORDER BY anomaly_id, seq"
        )
        truth = tuple(
            AnomalyTruth(
                r[0],
                r[1],
                bool(r[2]),
                r[3],
                tuple(t_claims.get(r[0], [])),
                tuple(t_lines.get(r[0], [])),
                r[4],
                r[5],
            )
            for r in tcon.execute(
                "SELECT anomaly_id, anomaly_type, is_decoy, variant, provider_id, explanation "
                "FROM anomaly_truth ORDER BY rowid"
            )
        )
        tcon.close()
    return Dataset(
        config,
        members,
        providers,
        procedure_codes,
        diagnosis_codes,
        bundle_pairs,
        unit_limits,
        claims,
        claim_lines,
        flags,
        truth,
    )
