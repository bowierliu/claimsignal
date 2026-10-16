from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from types import ModuleType

import pytest

from claims_copilot.project import REPO_ROOT

HOOK_PATH = REPO_ROOT / ".cursor" / "hooks" / "block_secrets_in_shell.py"


def load_hook() -> ModuleType:
    spec = importlib.util.spec_from_file_location("block_secrets_in_shell", HOOK_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load_hook()

# Fake credentials are assembled at runtime so the literal never appears in the repo.
FAKE = {
    "openai_or_anthropic_key": "sk-" + "proj-" + "A1b2C3d4" * 6,
    "github_token": "ghp" + "_" + "Z9y8X7w6" * 5,
    "aws_access_key_id": "AKIA" + "QWERTYUIOPASDFGH",
    "private_key_block": "-----BEGIN " + "RSA PRIVATE KEY-----",
    "credential_in_url": "https://" + "user:" + "hunter2" + "@github.com/o/r.git",
    "literal_secret_assignment": "OPENAI_API_KEY" + "=" + "notarealkey123",
}


@pytest.mark.parametrize("kind", sorted(FAKE))
def test_each_secret_kind_is_denied_without_echoing_it(kind: str) -> None:
    secret = FAKE[kind]
    decision = hook.decide({"command": f"echo {secret}", "cwd": str(REPO_ROOT)})
    assert decision["permission"] == "deny"
    assert kind in decision["agent_message"]
    assert secret not in json.dumps(decision)


@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest -q",
        "git remote -v",
        "git clone git@github.com:owner/repo.git",
        'curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models',
        "export OPENAI_API_KEY=$(security find-generic-password -s openai -w)",
        "grep OPENAI_API_KEY= .env.example",
    ],
)
def test_ordinary_commands_are_allowed(command: str) -> None:
    assert hook.decide({"command": command}) == {"permission": "allow"}


@pytest.mark.parametrize("payload", [None, [], {}, {"command": 3}])
def test_malformed_payload_is_denied(payload: object) -> None:
    assert hook.decide(payload)["permission"] == "deny"


def test_script_speaks_the_hook_protocol_over_stdio() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"command": "ls", "cwd": str(REPO_ROOT), "sandbox": False}),
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {"permission": "allow"}
