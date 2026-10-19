"""The investigator's queue: claims a synthetic screen flagged, true and false alarms alike.

A flag's screen code names the check that fired, not the verdict. Decoys fire the screen too (that
is what makes them decoys), and some clean claims are flagged at random. Flag ids are assigned in
claim-id order so an id never reveals which kind of flag it is.
"""

from __future__ import annotations

import random

from claims_copilot.synth.anomalies import (
    DATE_ANOMALY,
    DUPLICATE,
    EXCESS_UNITS,
    OUTLIER,
    UNBUNDLING,
)
from claims_copilot.synth.baseline import Working
from claims_copilot.synth.models import Flag

SCREENS: dict[str, tuple[str, str]] = {
    DUPLICATE: ("SCR01", "possible duplicate claim"),
    UNBUNDLING: ("SCR02", "bundled code pair on the same date"),
    EXCESS_UNITS: ("SCR03", "units above the per-line limit"),
    OUTLIER: ("SCR04", "provider billing intensity above peers"),
    DATE_ANOMALY: ("SCR05", "line date outside the claim window"),
}
OUTLIER_SAMPLE = 3  # claims flagged per provider-level case


def build_flags(work: Working) -> list[Flag]:
    rng = random.Random(f"{work.config.seed}:flags")
    screen_for_claim: dict[str, tuple[str, str]] = {}
    in_truth: set[str] = set()
    for entry in work.truth:
        in_truth.update(entry.claim_ids)
        if entry.anomaly_type == DUPLICATE:
            flagged = entry.claim_ids[-1:]
        elif entry.anomaly_type == OUTLIER:
            flagged = entry.claim_ids[:OUTLIER_SAMPLE]
        else:
            flagged = entry.claim_ids
        for cid in flagged:
            screen_for_claim[cid] = SCREENS[entry.anomaly_type]
    clean = sorted(cid for cid in work.claims if cid not in in_truth)
    screens = [SCREENS[t] for t in sorted(SCREENS)]
    for cid in rng.sample(clean, min(work.config.false_alarm_flags, len(clean))):
        screen_for_claim[cid] = rng.choice(screens)
    return [
        Flag(f"F{number:06d}", cid, code, text)
        for number, (cid, (code, text)) in enumerate(sorted(screen_for_claim.items()), start=1)
    ]
