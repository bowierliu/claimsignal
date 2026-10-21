"""An append-only, hash-chained audit log: who did what, to which record, and when.

Each entry holds the SHA-256 of the previous entry, so editing, deleting, or reordering an earlier
entry breaks the chain from that point and `verify` reports the first bad sequence number. This is
tamper-EVIDENT, not tamper-proof: someone who can rewrite the whole file can rebuild the chain, so a
real deployment also writes to storage the application cannot modify (see docs/SECURITY.md).

An entry records the actor, the action, the subject (for example a claim id), and scalar details
with no payload (the same policy as `trace.clean_attrs`): never the question text, a model answer, a
request body, or a credential. There is no update or delete function by design.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from claims_copilot.obs.redact import redact
from claims_copilot.obs.trace import clean_attrs
from claims_copilot.project import REPO_ROOT

AUDIT_PATH = REPO_ROOT / "data" / "audit" / "audit.jsonl"
GENESIS = "0" * 64


def _digest(entry: dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Verification:
    ok: bool
    entries: int
    first_bad_seq: int | None = None
    reason: str = ""


class AuditLog:
    def __init__(self, path: Path = AUDIT_PATH, *, now: Callable[[], str] | None = None) -> None:
        self._path = path
        self._now = now or (lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def append(
        self, actor: str, action: str, subject: str | None = None, **details: Any
    ) -> dict[str, Any]:
        """Add one entry; the whole read-chain-write happens under an exclusive file lock."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                last = _last_entry(f.read())
                entry: dict[str, Any] = {
                    "seq": (last["seq"] + 1) if last else 1,
                    "ts": self._now(),
                    "actor": redact(actor)[:80],
                    "action": redact(action)[:80],
                    "subject": None if subject is None else redact(subject)[:80],
                    "details": clean_attrs(details),
                    "prev_hash": last["hash"] if last else GENESIS,
                }
                entry["hash"] = _digest(entry)
                f.write(json.dumps(entry, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        return entry

    def read(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        return [json.loads(x) for x in self._path.read_text(encoding="utf-8").splitlines() if x]

    def verify(self) -> Verification:
        previous, count = GENESIS, 0
        for raw in (
            self._path.read_text(encoding="utf-8").splitlines() if self._path.exists() else []
        ):
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                return Verification(False, count, count + 1, "unreadable line")
            count += 1
            if entry.get("seq") != count:
                return Verification(False, count, count, "sequence gap or reorder")
            if entry.get("prev_hash") != previous:
                return Verification(False, count, count, "previous hash does not match")
            if entry.get("hash") != _digest(entry):
                return Verification(False, count, count, "entry was changed")
            previous = entry["hash"]
        return Verification(True, count)


def _last_entry(text: str) -> dict[str, Any] | None:
    lines = [x for x in text.splitlines() if x]
    if not lines:
        return None
    with contextlib.suppress(json.JSONDecodeError):
        loaded = json.loads(lines[-1])
        if isinstance(loaded, dict):
            return loaded
    raise ValueError("the audit log's last line is unreadable; refusing to append")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="claims_copilot.obs.audit", description="Verify the log.")
    parser.add_argument("--path", type=Path, default=AUDIT_PATH)
    result = AuditLog(parser.parse_args(argv).path).verify()
    print(f"entries: {result.entries}; chain ok: {result.ok}", end="")
    print("" if result.ok else f"; first bad entry: {result.first_bad_seq} ({result.reason})")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
