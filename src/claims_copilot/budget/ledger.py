"""Append-only JSONL ledger of paid API calls."""

from __future__ import annotations

import fcntl
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

CallStatus = Literal["ok", "error"]


@dataclass(frozen=True)
class LedgerEntry:
    timestamp: str
    phase: str
    model_key: str
    purpose: str
    eval_run_id: str | None
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal
    cost_usd: Decimal
    status: CallStatus

    def to_json(self) -> str:
        row = asdict(self)
        row["estimated_cost_usd"] = str(self.estimated_cost_usd)
        row["cost_usd"] = str(self.cost_usd)
        return json.dumps(row, sort_keys=True)

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> LedgerEntry:
        status = row["status"]
        if status not in ("ok", "error"):
            raise ValueError(f"unknown ledger status {status!r}")
        return cls(
            timestamp=str(row["timestamp"]),
            phase=str(row["phase"]),
            model_key=str(row["model_key"]),
            purpose=str(row["purpose"]),
            eval_run_id=row.get("eval_run_id"),
            input_tokens=int(row["input_tokens"]),
            output_tokens=int(row["output_tokens"]),
            estimated_cost_usd=Decimal(row["estimated_cost_usd"]),
            cost_usd=Decimal(row["cost_usd"]),
            status=status,
        )


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def entries(self) -> list[LedgerEntry]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as f:
            return [LedgerEntry.from_dict(json.loads(line)) for line in f if line.strip()]

    def append(self, entry: LedgerEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(entry.to_json() + "\n")
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def spent(self, *, phase: str | None = None, eval_run_id: str | None = None) -> Decimal:
        total = Decimal(0)
        for e in self.entries():
            if phase is not None and e.phase != phase:
                continue
            if eval_run_id is not None and e.eval_run_id != eval_run_id:
                continue
            total += e.cost_usd
        return total
