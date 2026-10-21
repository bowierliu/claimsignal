"""The scrubber masks credentials and personal identifiers and never leaks the match."""

from __future__ import annotations

import pytest

from claims_copilot.obs.redact import kinds, redact, scan

# Built at run time from pieces so no literal in this file looks like a real credential.
FAKE_PROVIDER_KEY = "sk-" + "a1b2c3d4e5" * 3
FAKE_BEARER = "Bearer " + "abcdefghij" * 3
FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
FAKE_PEM_HEADER = "-----BEGIN " + "RSA PRIVATE" + " KEY-----"


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        (f"key is {FAKE_PROVIDER_KEY}", "provider_key"),
        (f"Authorization: {FAKE_BEARER}", "bearer"),
        (f"aws {FAKE_AWS}", "cloud_key"),
        (FAKE_PEM_HEADER, "private_key"),
        ("password=hunter2hunter2", "named_secret"),
        ("ssn 123-45-6789 on file", "ssn"),
        ("call (415) 555-0100 today", "phone"),
        ("mail someone@example.org", "email"),
    ],
)
def test_each_shape_is_found_and_masked(text: str, kind: str) -> None:
    assert kind in kinds(text)
    assert "[REDACTED:" in redact(text)


def test_the_masked_text_does_not_contain_the_secret() -> None:
    text = f"token {FAKE_PROVIDER_KEY} and ssn 123-45-6789"
    out = redact(text)
    assert FAKE_PROVIDER_KEY not in out and "123-45-6789" not in out
    assert out.startswith("token ")


def test_ordinary_text_and_synthetic_ids_are_left_alone() -> None:
    text = "Claim C0000001 for member M000001 billed X0010 with 3 units on 2026-11-09."
    assert scan(text) == [] and redact(text) == text


def test_findings_do_not_keep_the_matched_text() -> None:
    finding = scan("ssn 123-45-6789")[0]
    assert set(vars(finding)) == {"kind", "start", "end"}
