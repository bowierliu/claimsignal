"""Print spend against caps: `uv run python -m claims_copilot.budget`."""

from claims_copilot.budget import default_guard


def main() -> None:
    guard = default_guard()
    caps, ledger = guard.caps, guard.ledger
    rows = [("total", caps.total_usd, ledger.spent())]
    rows += [(phase, cap, ledger.spent(phase=phase)) for phase, cap in caps.phases.items()]
    print(f"{'scope':<8} {'spent':>10} {'cap':>8} {'used':>6}")
    for scope, cap, spent in rows:
        used = f"{spent / cap:.0%}" if cap else "-"
        print(f"{scope:<8} {spent:>10.4f} {cap:>8.2f} {used:>6}")


if __name__ == "__main__":
    main()
