"""Run the API locally: `uv run python -m claims_copilot.api`.

It binds to 127.0.0.1 by default. If CLAIMS_COPILOT_API_KEY is set (environment or .env), every
route except /v1/health needs it in the X-API-Key header. Binding elsewhere needs `--allow-remote`
AND a key: the service refuses to listen on a network without authentication.
"""

from __future__ import annotations

import argparse
import ipaddress
from pathlib import Path

import uvicorn
from starlette.middleware.trustedhost import TrustedHostMiddleware

from claims_copilot.api.app import create_app
from claims_copilot.api.guard import Guard, GuardConfig
from claims_copilot.api.policy import load_policy_index
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
        help="lexical (default, free, offline) or hybrid (BM25 + dense + LLM rerank; paid calls "
        "through CostGuard; falls back to lexical and says so)",
    )
    parser.add_argument(
        "--ask",
        action="store_true",
        help="enable 'Ask the agent' in the workbench (paid model calls through CostGuard; "
        "$0.15 per question, $0.25 per session, $2.00 per server process)",
    )
    parser.add_argument("--ask-provider", choices=("anthropic", "openai"), default="anthropic")
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
        help="keep full Ask run records (question and tool payloads) in data/runs/ask/ "
        "(gitignored); off by default, so only id-and-count audit entries are kept",
    )
    args = parser.parse_args(argv)
    if not _is_loopback(args.host) and not args.allow_remote:
        parser.error("refusing to bind a non-loopback host without --allow-remote")
    key = get_secret("CLAIMS_COPILOT_API_KEY")
    if not _is_loopback(args.host) and key is None:
        parser.error("refusing to bind a non-loopback host without CLAIMS_COPILOT_API_KEY set")
    audit = AuditLog()
    guard = Guard(GuardConfig.from_keys(key) if key else GuardConfig(), audit)
    mode = args.policy_mode
    ask = None
    if args.ask:
        from claims_copilot.agent.ask_setup import AskUnavailableError, build_ask_service

        try:
            ask = build_ask_service(
                args.payer, provider=args.ask_provider, record_runs=args.record_runs, audit=audit
            )
        except AskUnavailableError as exc:
            parser.error(f"--ask cannot start: {exc}")
        note = ask.status()["policy_search_note"]
        print(f"Ask enabled ({args.ask_provider}); policy search: {note or 'hybrid + rerank'}")
    app = create_app(
        args.payer, policy_loader=lambda: load_policy_index(mode=mode), guard=guard, ask=ask
    )
    # A Host allowlist stops DNS rebinding: a page on another name cannot reach this server.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts(args.host, args.hostname))
    # No proxy sits in front by default, so X-Forwarded-For is never trusted for the caller label.
    uvicorn.run(app, host=args.host, port=args.port, proxy_headers=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
