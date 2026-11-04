"""Serves the investigator workbench: four static files, no build step, no third-party code.

The files are looked up in a fixed table, so no request can name another file. They hold no data;
every record is fetched from the read-only `/v1` API (which still needs the API key when one is
configured). The page is served with a strict content security policy: scripts and styles only from
this origin, requests only to this origin, no framing, no inline code.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response

from claims_copilot.project import PRODUCT_NAME

WEB_DIR = Path(__file__).parent / "web"
PREFIX = "/workbench"
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


def is_workbench_path(path: str) -> bool:
    return path == PREFIX or path.startswith(PREFIX + "/")


def _asset(name: str) -> Response:
    media = ASSETS.get(name)
    if media is None:
        return Response("Not found.", status_code=404, headers=SECURITY_HEADERS)
    body = (WEB_DIR / name).read_text(encoding="utf-8")
    if name == "index.html":
        body = body.replace("{{PRODUCT_NAME}}", escape(PRODUCT_NAME))
    return Response(body, media_type=media, headers=SECURITY_HEADERS)


def install_workbench(app: FastAPI) -> None:
    @app.get(PREFIX, include_in_schema=False)
    @app.get(PREFIX + "/", include_in_schema=False)
    def index() -> Response:
        return _asset("index.html")

    @app.get(PREFIX + "/{name}", include_in_schema=False)
    def asset(name: str) -> Response:
        return _asset(name)
