"""Serves the investigator workbench: four static files, no build step, no third-party code.

The files are looked up in a fixed table, so no request can name another file. They hold no data;
every record is fetched from the read-only `/v1` API (which still needs the API key when one is
configured). The page is served with a strict content security policy: scripts and styles only from
this origin, requests only to this origin, no framing, no inline code.

"Ask the agent" (`/workbench/ask*`) is the one surface that makes model calls. It is off unless
the server starts with `--ask`, is not part of the `/v1` contract (`docs/openapi.json`), needs the
API key whenever one is configured (the guard does not treat it as an open path), accepts only a
same-origin JSON POST (so another site cannot make a browser spend money here), and has its own
stricter rate limit. The agent itself is passed in as an `AskBackend`; this module never imports it.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from claims_copilot.api.guard import RateLimiter
from claims_copilot.project import PRODUCT_NAME

WEB_DIR = Path(__file__).parent / "web"
PREFIX = "/workbench"
ASK_PREFIX = PREFIX + "/ask"
ASK_PER_MINUTE = 6
ASK_BURST = 3
ASSETS: dict[str, str] = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
    "favicon.svg": "image/svg+xml",
}
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
}
SESSION_PATTERN = r"^[A-Za-z0-9_-]{16,64}$"


class AskBackend(Protocol):
    busy_error: type[Exception]

    def status(self) -> dict[str, Any]: ...

    def reset(self, token: str | None) -> bool: ...

    def ask(self, token: str | None, question: str, claim_id: str | None) -> dict[str, Any]: ...


class AskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1000)
    claim_id: str | None = Field(default=None, pattern=r"^C\d{7}$")
    session: str | None = Field(default=None, pattern=SESSION_PATTERN)


class ResetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session: str | None = Field(default=None, pattern=SESSION_PATTERN)


def is_workbench_path(path: str) -> bool:
    return path == PREFIX or path.startswith(PREFIX + "/")


def is_ask_path(path: str) -> bool:
    return path == ASK_PREFIX or path.startswith(ASK_PREFIX + "/")


def _asset(name: str) -> Response:
    media = ASSETS.get(name)
    if media is None:
        return Response("Not found.", status_code=404, headers=SECURITY_HEADERS)
    body = (WEB_DIR / name).read_text(encoding="utf-8")
    if name == "index.html":
        body = body.replace("{{PRODUCT_NAME}}", escape(PRODUCT_NAME))
    return Response(body, media_type=media, headers=SECURITY_HEADERS)


def _json(body: dict[str, Any], status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers=SECURITY_HEADERS)


def _problem(request: Request, status: int, kind: str, title: str, detail: str) -> JSONResponse:
    body = {
        "type": f"https://claims-copilot.local/problems/{kind}",
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": getattr(request.state, "request_id", "unavailable"),
    }
    return _json(body, status)


def _cross_site(request: Request) -> bool:
    """True when a browser says this request came from another site."""
    site = request.headers.get("sec-fetch-site")
    if site is not None and site not in ("same-origin", "none"):
        return True
    origin = request.headers.get("origin")
    if origin is None:
        return False
    host = request.headers.get("host", "")
    return urlsplit(origin).netloc != host


def _ask_refusal(request: Request, limiter: RateLimiter) -> JSONResponse | None:
    if _cross_site(request):
        return _problem(request, 403, "cross-site", "Forbidden", "Same-origin requests only.")
    media = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if media != "application/json":
        return _problem(request, 415, "media-type", "Unsupported media type", "Send JSON.")
    caller = getattr(request.state, "caller", None) or (
        request.client.host if request.client else "unknown"
    )
    wait = limiter.allow(f"ask:{caller}")
    if wait is not None:
        refusal = _problem(request, 429, "rate-limited", "Rate limited", "Too many questions.")
        refusal.headers["Retry-After"] = str(wait)
        return refusal
    return None


def _backend(request: Request) -> AskBackend | None:
    return getattr(request.app.state, "ask", None)


OFF = "Ask is off on this server. Start it with --ask (it makes paid model calls)."


def install_workbench(app: FastAPI) -> None:
    @app.get(PREFIX, include_in_schema=False)
    @app.get(PREFIX + "/", include_in_schema=False)
    def index() -> Response:
        return _asset("index.html")

    limiter = RateLimiter(ASK_PER_MINUTE, ASK_BURST)

    @app.get(ASK_PREFIX + "/status", include_in_schema=False)
    def ask_status(request: Request) -> Response:
        backend = _backend(request)
        if backend is None:
            return _json({"enabled": False, "note": OFF})
        return _json(backend.status())

    @app.post(ASK_PREFIX, include_in_schema=False)
    def ask(request: Request, body: AskIn) -> Response:
        refusal = _ask_refusal(request, limiter)
        if refusal is not None:
            return refusal
        backend = _backend(request)
        if backend is None:
            return _problem(request, 503, "ask-off", "Ask is off", OFF)
        try:
            return _json(backend.ask(body.session, body.question, body.claim_id))
        except backend.busy_error:
            return _problem(
                request, 409, "busy", "Busy", "A question is already running. Try again shortly."
            )

    @app.post(ASK_PREFIX + "/reset", include_in_schema=False)
    def ask_reset(request: Request, body: ResetIn) -> Response:
        refusal = _ask_refusal(request, limiter)
        if refusal is not None:
            return refusal
        backend = _backend(request)
        cleared = backend.reset(body.session) if backend is not None else False
        return _json({"cleared": cleared})

    @app.get(PREFIX + "/{name}", include_in_schema=False)
    def asset(name: str) -> Response:
        return _asset(name)
