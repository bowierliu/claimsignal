"""The runner binds to loopback unless told otherwise (no authentication in this phase)."""

from __future__ import annotations

import pytest

from claims_copilot.api.__main__ import _is_loopback, main


@pytest.mark.parametrize(
    ("host", "loopback"),
    [
        ("127.0.0.1", True),
        ("localhost", True),
        ("::1", True),
        ("0.0.0.0", False),  # noqa: S104 - the value under test, not a bind
        ("192.168.1.20", False),
        ("example.com", False),
    ],
)
def test_loopback_detection(host: str, loopback: bool) -> None:
    assert _is_loopback(host) is loopback


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20"])  # noqa: S104
def test_a_non_loopback_host_is_refused_without_the_flag(host: str) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--host", host])
    assert exc.value.code == 2
