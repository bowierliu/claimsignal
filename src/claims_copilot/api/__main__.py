"""Run the API locally: `uv run python -m claims_copilot.api`.

It binds to 127.0.0.1 by default. If CLAIMS_COPILOT_API_KEY is set (environment or .env), every
route except /v1/health needs it in the X-API-Key header. Binding elsewhere needs `--allow-remote`
AND a key: the service refuses to listen on a network without authentication.
"""

from __future__ import annotations

import argparse
import ipaddress
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from starlette.middleware.trustedhost import TrustedHostMiddleware

from claims_copilot.api.app import create_app
from claims_copilot.api.guard import Guard, GuardConfig
from claims_copilot.obs.audit import AuditLog
from claims_copilot.secrets import get_secret
from claims_copilot.tools.repository import DEFAULT_PAYER_PATH


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def allowed_hosts(host: str, extra: list[str]) -> list[str]:
    """Host header names the server answers: loopback names, the bound host, and `extra`.

    A non-loopback bind with no `extra` names accepts any Host (behind a load balancer the name is
    not known here); that bind always requires the API key, which a rebinding page cannot send.
    """
    if not _is_loopback(host) and not extra:
        return ["*"]
    names = ["127.0.0.1", "localhost", "[::1]", host, *extra]
    return list(dict.fromkeys(f"[{n}]" if ":" in n and not n.startswith("[") else n for n in names))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_copilot.api", description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--payer", type=Path, default=DEFAULT_PAYER_PATH, help="payer.sqlite path")
    parser.add_argument(
        "--allow-remote", action="store_true", help="allow a non-loopback host (needs an API key)"
    )
    parser.add_argument(
        "--policy-mode",
        choices=("lexical", "hybrid"),
        default="lexical",
        help="the research workbench serves the offline lexical index",
    )
    parser.add_argument(
        "--ask",
        action="store_true",
        help="enable guarded, loopback-only freeform Ask using synthetic data and lexical search",
    )
    parser.add_argument("--ask-provider", choices=("anthropic", "openai"), default="openai")
    parser.add_argument(
        "--hostname",
        action="append",
        default=[],
        help="an extra Host header name to accept (repeatable); loopback names and --host "
        "are always accepted, any other name is refused",
    )
    parser.add_argument(
        "--record-runs",
        action="store_true",
        help="unsupported for interactive sessions (conversation payloads remain in memory)",
    )
    args = parser.parse_args(argv)
    if not _is_loopback(args.host) and not args.allow_remote:
        parser.error("refusing to bind a non-loopback host without --allow-remote")
    key = get_secret("CLAIMS_COPILOT_API_KEY")
    if not _is_loopback(args.host) and key is None:
        parser.error("refusing to bind a non-loopback host without CLAIMS_COPILOT_API_KEY set")
    audit = AuditLog()
    guard = Guard(GuardConfig.from_keys(key) if key else GuardConfig(), audit)
    if args.policy_mode != "lexical":
        parser.error("Only lexical retrieval is supported on the interactive server.")
    if args.ask and (not _is_loopback(args.host) or args.hostname or args.ask_provider != "openai"):
        parser.error(
            "Interactive Ask requires a loopback host and the priced portfolio OpenAI model."
        )
    if args.record_runs:
        parser.error("Interactive Ask keeps conversation payloads in memory only.")
    with TemporaryDirectory() as scratch:
        ask = None
        if args.ask:
            from claims_copilot.agent.portfolio_ask import build_portfolio_ask

            ask = build_portfolio_ask(args.payer, Path(scratch))
        app = create_app(args.payer, guard=guard, ask=ask)
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=allowed_hosts(args.host, args.hostname)
        )
        uvicorn.run(app, host=args.host, port=args.port, proxy_headers=False, access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
