"""Build the committed diagnosis-code subset from the verified raw ICD-10-CM file.

Run: `uv run python -m claims_copilot.synth.icd_subset`

Reads `data/raw/icd10cm-fy27-code-descriptions.zip`, refuses to run if its sha256 differs from the
manifest row, takes a seeded sample of codes per chapter letter, and writes codes only (no
descriptors) with a provenance header. The zip and its descriptors are never copied into git.
"""

from __future__ import annotations

import hashlib
import io
import random
import zipfile

from claims_copilot.project import ICD_SUBSET_PATH, MANIFEST_PATH, REPO_ROOT
from claims_copilot.sources.manifest import read_manifest
from claims_copilot.synth.codes import ICD_CODE_PATTERN

SOURCE_ID = "icd10cm-fy27-code-descriptions"
CODES_MEMBER = "icd10cm-codes-2027.txt"
SUBSET_SEED = 20261019
PER_LETTER = 20
# Chapter letters used for claims. U (reserved) and V-Y (external-cause codes) are left out.
LETTERS = "ABCDEFGHIJKLMNOPQRSTZ"


def parse_codes(archive_bytes: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        name = next(n for n in archive.namelist() if n.endswith(CODES_MEMBER))
        text = archive.read(name).decode("utf-8")
    codes = []
    for line in text.splitlines():
        code = line[:7].strip()
        if not ICD_CODE_PATTERN.fullmatch(code):
            raise ValueError(f"unexpected code shape in source file: {code!r}")
        codes.append(code)
    return codes


def choose_subset(
    codes: list[str], seed: int = SUBSET_SEED, per_letter: int = PER_LETTER
) -> list[str]:
    rng = random.Random(seed)
    chosen: list[str] = []
    for letter in LETTERS:
        # Codes whose second character is not a digit (18 "QA" codes in the FY27 file) are not
        # sampled: their meaning was not researched.
        pool = sorted(c for c in codes if c.startswith(letter) and c[1].isdigit())
        if len(pool) < per_letter:
            raise ValueError(f"only {len(pool)} codes start with {letter}")
        chosen.extend(sorted(rng.sample(pool, per_letter)))
    return chosen


def render(chosen: list[str], sha256: str) -> str:
    header = [
        "# ICD-10-CM FY2027 diagnosis code subset (codes only, no descriptors).",
        f"# source_id: {SOURCE_ID} (see SOURCES/manifest.jsonl)",
        f"# source sha256: {sha256}",
        f"# selection: seeded sample ({SUBSET_SEED}) of {PER_LETTER} codes per chapter letter "
        f"in {LETTERS}, second character a digit",
    ]
    return "\n".join(header + chosen) + "\n"


def main() -> int:
    row = next(r for r in read_manifest(MANIFEST_PATH) if r["source_id"] == SOURCE_ID)
    raw = (REPO_ROOT / row["local_path"]).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != row["sha256"]:
        print("refusing: raw file hash differs from the manifest row")
        return 1
    chosen = choose_subset(parse_codes(raw))
    ICD_SUBSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    ICD_SUBSET_PATH.write_text(render(chosen, actual), encoding="utf-8")
    print(f"wrote {len(chosen)} codes to {ICD_SUBSET_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
