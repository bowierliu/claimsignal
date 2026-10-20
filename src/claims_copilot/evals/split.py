"""Deterministic dev/test split, stratified by layer, fixed by the pre-registration."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from claims_copilot.evals.prereg import load_preregistration
from claims_copilot.evals.schema import EvalCase, Layer, Split, check_unique


def split_key(salt: str, case_id: str) -> str:
    return hashlib.sha256(f"{salt}:{case_id}".encode()).hexdigest()


def assign_splits(cases: list[EvalCase], *, salt: str | None = None) -> dict[str, Split]:
    """Within each layer, the first (n + 1) // 3 ids by hash are dev; the rest are test.

    The result depends only on the set of case ids and the salt, so adding an unrelated layer, or
    reordering a file, never moves a case.
    """
    check_unique(cases)
    use_salt = salt if salt is not None else load_preregistration().split_salt
    by_layer: dict[Layer, list[str]] = defaultdict(list)
    for case in cases:
        by_layer[case.layer].append(case.case_id)
    out: dict[str, Split] = {}
    for ids in by_layer.values():
        ordered = sorted(ids, key=lambda cid: split_key(use_salt, cid))
        n_dev = (len(ordered) + 1) // 3
        for i, cid in enumerate(ordered):
            out[cid] = Split.DEV if i < n_dev else Split.TEST
    return out
