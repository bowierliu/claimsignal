"""Serve the synthetic portfolio demo on one loopback origin."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import FileResponse, JSONResponse, Response

from claims_copilot.agent.portfolio_ask import build_portfolio_ask
from claims_copilot.api.app import create_app as create_workbench
from claims_copilot.evals.handbuilt import build_handbuilt
from claims_copilot.portfolio import CASES, InvalidSelectionError, investigate
from claims_copilot.portfolio_guard import Guard, GuardError
from claims_copilot.project import REPO_ROOT

HOST = "127.0.0.1"
PORT = 8763
ORIGIN = f"http://{HOST}:{PORT}"
ASSETS = {"app.js", "cases.js", "style.css", "favicon.svg"}
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
)


def create_app(payer: Path) -> FastAPI:
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[HOST])

    @app.get("/")
    def index() -> Response:
        return FileResponse(
            REPO_ROOT / "docs/index.html",
            headers={"Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/demo/{name}")
    def asset(name: str) -> Response:
        if name not in ASSETS:
            return Response(status_code=404)
        return FileResponse(REPO_ROOT / "docs/demo" / name)

    @app.get("/api/status")
    def status() -> dict[str, str]:
        return {"service": "claims-portfolio-v1"}

    @app.post("/api/investigations/{key}")
    def live(key: str, request: Request) -> Response:
        if (
            request.headers.get("host") != f"{HOST}:{PORT}"
            or request.headers.get("origin") != ORIGIN
            or request.headers.get("x-demo-request") != "investigate"
        ):
            return JSONResponse({"error": "Use the local demo page to start a run."}, 403)
        if (
            request.query_params
            or request.headers.get("content-length", "0") != "0"
            or "transfer-encoding" in request.headers
        ):
            return JSONResponse({"error": "Choose one of the supplied synthetic cases."}, 400)
        case = CASES.get(key)
        if case is None:
            return JSONResponse({"error": "Unknown synthetic case."}, 404)
        body: dict[str, Any]
        try:
            with Guard.from_env().investigation("local-owner") as run:
                body = investigate(run, payer, case)
        except InvalidSelectionError:
            return JSONResponse(
                {"error": "Evidence withheld. The model did not return a supported selection."}, 422
            )
        except GuardError as exc:
            message = str(exc)
            limited = any(word in message.lower() for word in ("budget", "limit reached"))
            return JSONResponse({"error": message}, 429 if limited else 503)
        except (OSError, RuntimeError):
            return JSONResponse(
                {"error": "The investigation could not finish. No answer shown."}, 503
            )
        return JSONResponse(body, headers={"Cache-Control": "no-store"})

    # The original workbench keeps its own access checks and reply validation when mounted.
    ask = build_portfolio_ask(payer, payer.parent)
    app.mount("/", create_workbench(payer, ask=ask))
    return app


def main() -> None:
    with TemporaryDirectory() as root:
        path = Path(root) / "payer.sqlite"
        build_handbuilt(path)
        uvicorn.run(create_app(path), host=HOST, port=PORT, access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()
