"""The FY2027 ICD-10-CM billable code list, read from the verified local raw file.

The zip stays in `data/raw/` (gitignored). Loading refuses a file whose sha256 differs from the
manifest row, and never falls back to the 420-code sample: a validator that knew only the sample
would call every other real code invalid. If the file is absent the loader raises
`IcdSourceUnavailableError`, and callers record "not checked" instead of guessing.

Only codes are kept, never descriptors. Codes are matched without the decimal point, upper-case,
as the file writes them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from claims_copilot.project import MANIFEST_PATH, REPO_ROOT
from claims_copilot.sources.manifest import read_manifest
from claims_copilot.synth.config import WINDOW_END, WINDOW_START
from claims_copilot.synth.icd_subset import SOURCE_ID, parse_codes

CODE_SET_NAME = "ICD-10-CM FY2027 billable codes"


class IcdSourceUnavailableError(RuntimeError):
    """The raw ICD-10-CM file is missing or does not match its manifest hash."""


@dataclass(frozen=True)
class IcdCodeSet:
    codes: frozenset[str]
    valid_from: date
    valid_to: date
    name: str = CODE_SET_NAME
    sha256: str = ""

    def covers(self, day: date) -> bool:
        return self.valid_from <= day <= self.valid_to

    def contains(self, code: str) -> bool:
        return normalize_code(code) in self.codes


def normalize_code(code: str) -> str:
    return code.replace(".", "").strip().upper()


@lru_cache(maxsize=1)
def load_icd_codes() -> IcdCodeSet:
    row = next((r for r in read_manifest(MANIFEST_PATH) if r["source_id"] == SOURCE_ID), None)
    if row is None:
        raise IcdSourceUnavailableError("source is not in the manifest")
    path = REPO_ROOT / row["local_path"]
    if not path.is_file():
        raise IcdSourceUnavailableError("raw ICD-10-CM file is not present locally")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise IcdSourceUnavailableError("raw ICD-10-CM file does not match its manifest hash")
    return IcdCodeSet(
        codes=frozenset(parse_codes(raw)),
        valid_from=WINDOW_START,
        valid_to=WINDOW_END,
        sha256=row["sha256"],
    )
