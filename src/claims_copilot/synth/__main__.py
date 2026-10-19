"""Generate the synthetic dataset.

Run: `uv run python -m claims_copilot.synth [--small] [--seed N] [--out DIR]`
Writes `payer.sqlite` (for tools) and `truth.sqlite` (evaluations only) under data/synth/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from claims_copilot.project import REPO_ROOT, SYNTH_GOLDEN_PATH, SYNTH_OUT_DIR
from claims_copilot.synth.config import DEFAULT_SEED, GeneratorConfig
from claims_copilot.synth.dataset import golden_summary, payer_hash, truth_hash
from claims_copilot.synth.generate import generate
from claims_copilot.synth.store import write_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the synthetic payer dataset.")
    parser.add_argument("--small", action="store_true", help="fast test-sized dataset")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=SYNTH_OUT_DIR)
    parser.add_argument(
        "--write-golden",
        action="store_true",
        help="record the default dataset summary in eval/synthetic_dataset.json (owner-visible)",
    )
    args = parser.parse_args()
    config = GeneratorConfig.small(args.seed) if args.small else GeneratorConfig(seed=args.seed)
    dataset = generate(config)
    payer, truth = write_dataset(dataset, args.out)
    for name, count in dataset.counts().items():
        print(f"{name:<16} {count:>8}")
    print(f"payer sha256  {payer_hash(dataset)}")
    print(f"truth sha256  {truth_hash(dataset)}")
    for path in (payer, truth):
        shown = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        print(f"wrote {shown} ({path.stat().st_size:,} bytes)")
    if args.write_golden:
        if args.small or args.seed != DEFAULT_SEED:
            print("refusing: the golden summary is for the default configuration only")
            return 1
        SYNTH_GOLDEN_PATH.write_text(json.dumps(golden_summary(dataset), indent=2) + "\n")
        print(f"wrote {SYNTH_GOLDEN_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
