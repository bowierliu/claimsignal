"""The deployment files keep their promises: no secret, no key material, no answer key, non-root.

Nothing here builds or runs a container (there is no container runtime on the development
machine, KF-053). These are static checks on the files, plus one real run of the entrypoint.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from claims_copilot.project import REPO_ROOT

DOCKERFILE = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
DOCKERIGNORE = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
ENTRYPOINT = REPO_ROOT / "deploy" / "entrypoint.sh"
COMPOSE = (REPO_ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8")
TASK = json.loads((REPO_ROOT / "deploy" / "ecs-task-definition.json").read_text(encoding="utf-8"))
SECRET_WORDS = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD)", re.IGNORECASE)


def instructions(name: str) -> list[str]:
    return [line.strip() for line in DOCKERFILE.splitlines() if line.strip().startswith(name + " ")]


def test_the_image_runs_as_a_non_root_user() -> None:
    users = instructions("USER")
    assert users and users[-1] != "USER root" and not users[-1].startswith("USER 0")
    assert "useradd" in DOCKERFILE and "10001" in users[-1]


def test_no_credential_is_baked_in_by_env_or_arg() -> None:
    for line in instructions("ENV") + instructions("ARG"):
        assert not SECRET_WORDS.search(line), line


def test_nothing_secret_or_third_party_is_copied_into_the_image() -> None:
    copies = " ".join(instructions("COPY"))
    for forbidden in (".env", "data/raw", "data/chunks", "data/index", "data/text", "truth"):
        assert forbidden not in copies
    assert "ADD " not in DOCKERFILE and "curl " not in DOCKERFILE


def test_the_answer_key_is_generated_outside_the_data_directory_and_not_kept() -> None:
    assert "--out /tmp/synth" in DOCKERFILE
    assert "cp /tmp/synth/payer.sqlite" in DOCKERFILE
    code = "\n".join(x for x in DOCKERFILE.splitlines() if not x.lstrip().startswith("#"))
    assert "truth" not in code


def test_base_images_are_pinned_to_a_version_not_latest() -> None:
    froms = [x for x in instructions("FROM")]
    assert froms and all(":latest" not in f and ":" in f for f in froms)


def test_the_image_has_a_health_check_and_an_entrypoint() -> None:
    assert instructions("HEALTHCHECK") and instructions("ENTRYPOINT")
    assert "/v1/health" in DOCKERFILE


def test_every_file_the_dockerfile_copies_exists() -> None:
    for line in instructions("COPY"):
        if "--from=" in line:
            continue  # copies between build stages, not from the repository
        parts = [p for p in line.split()[1:] if not p.startswith("--")]
        for source in parts[:-1]:
            assert (REPO_ROOT / source).exists(), source


def test_the_build_context_excludes_secrets_and_local_data() -> None:
    for needed in (".env", ".env.*", ".git", "data"):
        assert needed in DOCKERIGNORE
    assert "!.env.example" in DOCKERIGNORE


def test_the_entrypoint_refuses_to_start_without_a_key_and_never_prints_one() -> None:
    text = ENTRYPOINT.read_text(encoding="utf-8")
    assert "set -eu" in text and "exec python -m claims_copilot.api" in text
    assert "--allow-remote" in text and "--policy-mode lexical" in text
    assert os.access(ENTRYPOINT, os.X_OK)
    uses = re.findall(r"CLAIMS_COPILOT_API_KEY", text)
    assert len(uses) == 2  # the empty-check and its message; no echo of the value
    sh = shutil.which("sh")
    assert sh is not None
    env = {k: v for k, v in os.environ.items() if k != "CLAIMS_COPILOT_API_KEY"}
    result = subprocess.run(  # noqa: S603 - fixed arguments
        [sh, str(ENTRYPOINT)], capture_output=True, text=True, env=env, check=False, timeout=30
    )
    assert result.returncode == 78 and "refusing to start" in result.stderr


def test_compose_publishes_on_loopback_only_and_hardens_the_container() -> None:
    assert '"127.0.0.1:8000:8000"' in COMPOSE
    assert not re.search(r"-\s*\"?8000:8000", COMPOSE)
    for required in ("read_only: true", "- ALL", "no-new-privileges:true", "healthcheck:"):
        assert required in COMPOSE
    # The key comes from the caller's environment, required, never written in the file.
    assert "CLAIMS_COPILOT_API_KEY: ${CLAIMS_COPILOT_API_KEY:?" in COMPOSE


def test_the_ecs_task_takes_its_key_from_secrets_manager_and_is_hardened() -> None:
    (container,) = TASK["containerDefinitions"]
    assert container["readonlyRootFilesystem"] is True
    assert container["user"] == "10001:10001"
    assert container["linuxParameters"]["capabilities"]["drop"] == ["ALL"]
    (secret,) = container["secrets"]
    assert secret["name"] == "CLAIMS_COPILOT_API_KEY"
    assert secret["valueFrom"].startswith("arn:aws:secretsmanager:")
    assert "environment" not in container  # no plain-text configuration of anything secret
    assert ":latest" not in container["image"]
    assert container["healthCheck"]["command"][0] == "CMD-SHELL"


def test_the_task_definition_holds_placeholders_not_real_account_data() -> None:
    text = json.dumps(TASK)
    assert not re.search(r"\b\d{12}\b", text)  # no account id
    for placeholder in ("ACCOUNT_ID", "REGION", "IMAGE_TAG"):
        assert placeholder in text


def test_writable_paths_match_what_the_application_writes() -> None:
    from claims_copilot.obs.audit import AUDIT_PATH
    from claims_copilot.obs.trace import TRACE_DIR

    app_dir = Path("/app")
    assert app_dir / AUDIT_PATH.parent.relative_to(REPO_ROOT) == Path("/app/data/audit")
    assert app_dir / TRACE_DIR.relative_to(REPO_ROOT) == Path("/app/data/traces")
    mounts = {m["containerPath"] for m in TASK["containerDefinitions"][0]["mountPoints"]}
    assert {"/app/data/audit", "/app/data/traces"} <= mounts


def test_run_output_directories_are_gitignored() -> None:
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for path in ("data/audit/", "data/traces/", "data/runs/", ".env"):
        assert path in ignored
