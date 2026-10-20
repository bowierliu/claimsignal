"""The 30 end-to-end cases (Phase 7): flagged claims from a fresh synthetic dataset.

Seed 20261021 was not used for any earlier tuning or scoring (development 20261019, held-out
20261020). Per anomaly type: 4 seeded anomalies and 2 decoys, in a fixed order, 30 cases in all.
A decoy looks like the anomaly to a screen but is fine. Each case is one flagged claim; its
expected anomaly type (or decoy type) comes from the generator's in-memory ground truth at build
time and is written to the case file, so scoring a run never opens a truth store.

The choice of which entries become cases is a seeded sample over the entries whose chosen claim
carries a screen flag (every seeded and decoy entry has one; the check is kept in case the
generator changes). Two question phrasings alternate by position: a plain dossier question, and
(every third case) a dossier question that also asks what the policy sources say about modifiers
or bundling, which makes that case policy-related for experiment E3.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from claims_copilot.agent.answer import Status
from claims_copilot.evals.schema import EvalCase, Layer
from claims_copilot.project import REPO_ROOT
from claims_copilot.synth.anomalies import ANOMALY_TYPES, DUPLICATE
from claims_copilot.synth.config import GeneratorConfig
from claims_copilot.synth.dataset import Dataset, payer_hash
from claims_copilot.synth.generate import generate

E2E_SEED = 20261021
SEEDED_PER_TYPE = 4
DECOYS_PER_TYPE = 2
CASES_PATH = REPO_ROOT / "eval" / "phase7_e2e.jsonl"
DATASET_INFO_PATH = REPO_ROOT / "eval" / "phase7_e2e_dataset.json"

PLAIN = "Summarise the evidence for claim {claim}: what do the checks and flags show?"
WITH_POLICY = (
    "Summarise the evidence for claim {claim}, and quote what the policy sources say about any "
    "modifier or bundling issue it raises."
)


def build_dataset(seed: int = E2E_SEED) -> Dataset:
    return generate(GeneratorConfig(seed=seed))


def _chosen_claim(anomaly_type: str, claim_ids: tuple[str, ...]) -> str:
    """The flagged claim an investigator would open: the later one of a duplicate pair, else the
    first (a provider-level case flags its first three claims)."""
    return claim_ids[-1] if anomaly_type == DUPLICATE else claim_ids[0]


def build_cases(dataset: Dataset, seed: int = E2E_SEED) -> list[EvalCase]:
    flagged = {f.claim_id for f in dataset.flags}
    cases: list[EvalCase] = []
    for atype in ANOMALY_TYPES:
        for is_decoy, count in ((False, SEEDED_PER_TYPE), (True, DECOYS_PER_TYPE)):
            pool = sorted(
                (
                    t
                    for t in dataset.truth
                    if t.anomaly_type == atype
                    and t.is_decoy is is_decoy
                    and _chosen_claim(atype, t.claim_ids) in flagged
                ),
                key=lambda t: t.anomaly_id,
            )
            if len(pool) < count:
                raise ValueError(f"not enough {atype} entries to pick {count}")
            rng = random.Random(f"{seed}:{atype}:{is_decoy}")  # noqa: S311  (seeded sampling)
            for entry in sorted(rng.sample(pool, count), key=lambda t: t.anomaly_id):
                claim = _chosen_claim(atype, entry.claim_ids)
                n = len(cases) + 1
                template = WITH_POLICY if n % 3 == 0 else PLAIN
                cases.append(
                    EvalCase(
                        case_id=f"e2e-{n:02d}",
                        layer=Layer.E2E,
                        question=template.format(claim=claim),
                        expected_statuses=(Status.ANSWERED, Status.CONFLICTING_EVIDENCE),
                        claim_id=claim,
                        expected_anomalies=() if is_decoy else (atype,),
                        decoy_anomalies=(atype,) if is_decoy else (),
                        note="decoy" if is_decoy else "seeded",
                    )
                )
    return cases


def policy_related(case: EvalCase) -> bool:
    return "policy sources" in case.question


def dataset_info(dataset: Dataset, seed: int = E2E_SEED) -> dict[str, object]:
    return {"seed": seed, "payer_sha256": payer_hash(dataset)}


def main() -> int:
    from claims_copilot.evals.casefile import write_cases

    dataset = build_dataset()
    write_cases(CASES_PATH, build_cases(dataset))
    DATASET_INFO_PATH.write_text(
        json.dumps(dataset_info(dataset), indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {CASES_PATH.relative_to(REPO_ROOT)} and {DATASET_INFO_PATH.name}")
    return 0


def write_dataset_to(out: Path, seed: int = E2E_SEED) -> Path:
    """Write the e2e payer database (and, beside it, the truth store the generator always makes)
    under `out`. The truth file is for nobody here: scoring uses the case file."""
    from claims_copilot.synth.store import PAYER_FILE, write_dataset

    write_dataset(build_dataset(seed), out)
    return out / PAYER_FILE


if __name__ == "__main__":
    raise SystemExit(main())
