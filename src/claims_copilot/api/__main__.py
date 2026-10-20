"""Run the API locally: `uv run python -m claims_copilot.api`.

It binds to 127.0.0.1 by default. There is no authentication in this phase (owner decision
2026-10-19), so binding elsewhere needs `--allow-remote`.
"""

from __future__ import annotations

import argparse
import ipaddress
from pathlib import Path

import uvicorn

from claims_copilot.api.app import create_app
from claims_copilot.api.policy import load_policy_index
from claims_copilot.tools.repository import DEFAULT_PAYER_PATH


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_copilot.api", description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--payer", type=Path, default=DEFAULT_PAYER_PATH, help="payer.sqlite path")
    parser.add_argument(
        "--allow-remote", action="store_true", help="allow a non-loopback host (no auth!)"
    )
    parser.add_argument(
        "--policy-mode",
        choices=("lexical", "hybrid"),
        default="lexical",
        help="lexical (default, free, offline) or hybrid (BM25 + dense + LLM rerank; paid calls "
        "through CostGuard; falls back to lexical and says so)",
    )
    args = parser.parse_args(argv)
    if not _is_loopback(args.host) and not args.allow_remote:
        parser.error("refusing to bind a non-loopback host without --allow-remote (no auth yet)")
    mode = args.policy_mode
    app = create_app(args.payer, policy_loader=lambda: load_policy_index(mode=mode))
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
