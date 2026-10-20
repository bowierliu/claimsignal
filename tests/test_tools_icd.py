from __future__ import annotations

import pytest

from claims_copilot.project import MANIFEST_PATH, REPO_ROOT
from claims_copilot.sources.manifest import read_manifest
from claims_copilot.synth.codes import load_diagnosis_subset
from claims_copilot.synth.icd_subset import SOURCE_ID
from claims_copilot.tools.icd import load_icd_codes

_ROW = next((r for r in read_manifest(MANIFEST_PATH) if r["source_id"] == SOURCE_ID), None)
_PRESENT = _ROW is not None and (REPO_ROOT / _ROW["local_path"]).is_file()


@pytest.mark.skipif(not _PRESENT, reason="raw ICD-10-CM file not present locally (data/raw)")
def test_full_fy2027_list_loads_with_hash_check_and_contains_the_committed_subset() -> None:
    codes = load_icd_codes()
    assert len(codes.codes) > 50_000
    assert codes.sha256 == _ROW["sha256"]  # type: ignore[index]
    subset = {c.code for c in load_diagnosis_subset()}
    assert subset <= codes.codes
    assert not codes.contains("ZZZZZZZ")
