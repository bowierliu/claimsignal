"""API access control: key required, wrong keys refused without echo, rate limited, audited."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api_fixtures import build_db
from claims_copilot.api.app import create_app
from claims_copilot.api.guard import Guard, GuardConfig, RateLimiter, key_digest
from claims_copilot.obs.audit import AuditLog
from tool_fixtures import icd_fixture

GOOD = "test-key-" + "k" * 24
BAD = "wrong-key-" + "w" * 24


def client(
    tmp_path: Path, config: GuardConfig, clock: Callable[[], float] = lambda: 0.0
) -> tuple[TestClient, AuditLog]:
    audit = AuditLog(tmp_path / "audit.jsonl", now=lambda: "2026-01-01T00:00:00+00:00")
    app = create_app(
        build_db(tmp_path / "payer.sqlite"),
        icd_loader=lambda: icd_fixture("E119"),
        policy_loader=lambda: None,
        guard=Guard(config, audit, clock),
    )
    return TestClient(app), audit


def test_a_missing_or_wrong_key_is_refused_and_not_echoed(tmp_path: Path) -> None:
    c, audit = client(tmp_path, GuardConfig.from_keys(GOOD))
    for headers in ({}, {"X-API-Key": BAD}):
        r = c.get("/v1/claims/C0000001", headers=headers)
        assert r.status_code == 401 and BAD not in r.text and GOOD not in r.text
        assert r.json()["request_id"] != "unavailable"
    assert [e["subject"] for e in audit.read()] == ["(denied)", "(denied)"]
    assert BAD not in (tmp_path / "audit.jsonl").read_text(encoding="utf-8")


def test_the_right_key_is_served_and_the_request_is_audited(tmp_path: Path) -> None:
    c, audit = client(tmp_path, GuardConfig.from_keys(GOOD))
    r = c.get("/v1/claims/C0000001?secret=1", headers={"X-API-Key": GOOD})
    assert r.status_code == 200
    (entry,) = audit.read()
    assert entry["subject"] == "/v1/claims/{claim_id}" and entry["details"]["status"] == 200
    assert entry["actor"] == f"key:{key_digest(GOOD)[:8]}" and "secret" not in str(entry)
    assert audit.verify().ok


def test_the_health_probe_is_open(tmp_path: Path) -> None:
    c, audit = client(tmp_path, GuardConfig.from_keys(GOOD))
    assert c.get("/v1/health").status_code == 200 and audit.read() == []


def test_without_a_configured_key_loopback_use_is_open_but_still_audited(tmp_path: Path) -> None:
    c, audit = client(tmp_path, GuardConfig())
    assert c.get("/v1/claims/C0000001").status_code == 200
    assert audit.read()[0]["actor"].startswith("anon:")


def test_requests_over_the_limit_get_429_with_retry_after(tmp_path: Path) -> None:
    c, _ = client(tmp_path, GuardConfig.from_keys(GOOD, requests_per_minute=60, burst=2))
    h = {"X-API-Key": GOOD}
    codes = [c.get("/v1/claims/C0000001", headers=h).status_code for _ in range(4)]
    assert codes == [200, 200, 429, 429]
    limited = c.get("/v1/claims/C0000001", headers=h)
    assert int(limited.headers["Retry-After"]) >= 1


def test_the_bucket_refills_over_time() -> None:
    now = [0.0]
    limiter = RateLimiter(60, 2, lambda: now[0])
    assert limiter.allow("a") is None and limiter.allow("a") is None
    assert limiter.allow("a") is not None
    now[0] = 1.0  # one token per second at 60/minute
    assert limiter.allow("a") is None and limiter.allow("a") is not None


def test_callers_do_not_share_a_bucket() -> None:
    limiter = RateLimiter(60, 1, lambda: 0.0)
    assert limiter.allow("a") is None and limiter.allow("b") is None
    assert limiter.allow("a") is not None


def test_a_bad_limit_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError):
        RateLimiter(0, 1)


def test_the_key_is_kept_only_as_a_digest() -> None:
    config = GuardConfig.from_keys(GOOD)
    assert GOOD not in repr(config) and key_digest(GOOD) in config.key_digests
