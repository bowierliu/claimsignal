"""Measure request latency against a real local server: `uv run python -m claims_copilot.api.bench`.

Starts uvicorn on a free loopback port in a thread, sends sequential keep-alive requests with
httpx, and prints p50, p95 and max per endpoint. One client, one request at a time: this measures
service time on this machine for the default dataset, not capacity under load.
"""

from __future__ import annotations

import platform
import socket
import statistics
import threading
import time
from pathlib import Path

import httpx
import uvicorn

from claims_copilot.api.app import create_app
from claims_copilot.tools.repository import DEFAULT_PAYER_PATH

REQUESTS = 200
WARMUP = 10


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))]


def run(payer: Path = DEFAULT_PAYER_PATH) -> list[tuple[str, int, float, float, float]]:
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(payer), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.02)
    rows: list[tuple[str, int, float, float, float]] = []
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}/v1", timeout=30) as client:
            flags = client.get("/flags", params={"limit": 200}).json()["flags"]
            claim_ids = sorted({f["claim_id"] for f in flags})
            provider_ids = sorted(
                {
                    client.get(f"/claims/{cid}").json()["claim"]["provider_id"]
                    for cid in claim_ids[:50]
                }
            )
            cases = {
                "GET /claims/{id}": [f"/claims/{c}" for c in claim_ids],
                "GET /claims/{id}/dossier": [f"/claims/{c}/dossier" for c in claim_ids],
                "GET /providers/{id}/intensity": [
                    f"/providers/{p}/intensity" for p in provider_ids
                ],
                "GET /providers/{id}/peers": [f"/providers/{p}/peers" for p in provider_ids],
                "GET /policy/search": ["/policy/search?q=modifier+59+distinct+procedural+service"],
            }
            for name, urls in cases.items():
                times: list[float] = []
                for i in range(WARMUP + REQUESTS):
                    url = urls[i % len(urls)]
                    start = time.perf_counter()
                    resp = client.get(url)
                    elapsed = (time.perf_counter() - start) * 1000
                    resp.raise_for_status()
                    if i >= WARMUP:
                        times.append(elapsed)
                rows.append(
                    (
                        name,
                        len(times),
                        statistics.median(times),
                        _percentile(times, 95),
                        max(times),
                    )
                )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    return rows


def main() -> int:
    rows = run()
    print(f"machine: {platform.platform()}, python {platform.python_version()}")
    print(f"{'endpoint':<32}{'n':>5}{'p50 ms':>10}{'p95 ms':>10}{'max ms':>10}")
    for name, n, p50, p95, worst in rows:
        print(f"{name:<32}{n:>5}{p50:>10.1f}{p95:>10.1f}{worst:>10.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
