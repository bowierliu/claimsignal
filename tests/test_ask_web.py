"""The Ask tab in the browser script (spec item 11), run under node with a fake DOM.

Views come from the real AskService (fake provider), so the script is checked against what the
server actually sends."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from agent_fixtures import FakeProvider, answer_json
from ask_fixtures import (
    DOSSIER,
    MOD_CHUNK,
    UNIT_FINDING,
    ask_chunks,
    ask_sources,
    insufficient,
    make_service,
    planned,
    scripted,
)
from claims_copilot.agent.ask_search import AskPolicySearch
from claims_copilot.agent.types import ProviderError
from claims_copilot.api.workbench import WEB_DIR
from claims_copilot.ingest.chunk import Chunk

HOSTILE = "<img src=x onerror=alert(1)>"
NODE = shutil.which("node")


def hostile_search() -> AskPolicySearch:
    chunks = [c for c in ask_chunks() if c.chunk_id != MOD_CHUNK]
    chunks.append(
        Chunk(MOD_CHUNK, "doc-a", 3, 4, "Section 1", f"{HOSTILE} Modifier 59 marks a service.", "b")
    )
    return AskPolicySearch(
        chunks, ask_sources(), dense=None, embedder=None, reranker=None, guard=None
    )


def build_views(tmp_path: Path) -> list[dict[str, Any]]:
    # Views 1 and 2 share one session: the follow-up keeps the session claim (C0000001) with
    # no claim in the field or the question, which is exactly the state the fake-DOM test uses
    # to check the field is never refilled from the session.
    sessioned = make_service(
        tmp_path / "a",
        planned(
            {
                "What did the checks find?": (
                    [DOSSIER, ("search_policy", {"q": "modifier 59"})],
                    answer_json(
                        summary=[
                            {
                                "text": f"{HOSTILE} Line 3 bills 5 units.",
                                "citations": [UNIT_FINDING],
                            },
                            {"text": "The manual describes modifier 59.", "citations": [MOD_CHUNK]},
                        ],
                        policy_quotes=[{"chunk_id": MOD_CHUNK, "quote": HOSTILE}],
                    ),
                ),
                "What about helicopters?": (
                    [("search_policy", {"q": "helicopter"})],
                    insufficient(),
                ),
            }
        ),
        search=hostile_search(),
    )
    answered = sessioned.ask(None, "What did the checks find?", "C0000001")
    assert answered["status"] == "ANSWERED", answered
    answered["sources"][0]["label"] = HOSTILE
    answered["sources"][1]["url"] = "javascript:alert(1)"

    insufficient_view = sessioned.ask(answered["session"]["token"], "What about helicopters?", None)
    assert insufficient_view["status"] == "INSUFFICIENT_EVIDENCE"
    assert insufficient_view["session"]["claim_id"] == "C0000001"  # session memory kept it
    # A note never occurs on this turn; inject one to exercise the session-line rendering.
    insufficient_view["session"]["note"] = "The question named C0000240; it is now in scope."

    invalid_view = make_service(
        tmp_path / "c",
        scripted([DOSSIER], answer_json(summary=[{"text": "A fact.", "citations": ["E99"]}])),
    ).ask(None, "And the modifier?", None)
    assert invalid_view["status"] == "INVALID_OUTPUT"

    # A provider failure frames as a service failure, with the adapter's safe error text.
    failed_view = make_service(
        tmp_path / "d",
        FakeProvider(
            [ProviderError("Anthropic messages request gave up after 3 attempts (HTTP 529)")]
        ),
    ).ask(None, "What did the checks find?", None)
    assert failed_view["status"] == "INVALID_OUTPUT" and failed_view["reason"] == "PROVIDER_ERROR"
    return [answered, insufficient_view, invalid_view, failed_view]


def build_fixtures(tmp_path: Path) -> dict[str, Any]:
    views = build_views(tmp_path)
    # A fifth ask whose response is held back until the fake-DOM test has clicked
    # "New session": the late answer must be discarded, never rendered (reset-race
    # regression, 2026-11-16). Its token differs from the live session's on purpose.
    slow = copy.deepcopy(views[0])
    slow["session"]["token"] = "a-stale-session-value"  # noqa: S105 - fixture, not a credential
    return {"views": [*views, {"defer": True}], "slow": slow, "hostile": HOSTILE}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_ask_tab_renders_views_as_text_and_posts_same_origin_json(tmp_path: Path) -> None:
    for sub in ("a", "b", "c", "d"):
        (tmp_path / sub).mkdir()
    path = tmp_path / "ask_fixtures.json"
    path.write_text(json.dumps(build_fixtures(tmp_path)), "utf-8")
    result = subprocess.run(  # noqa: S603 - fixed arguments, no user input
        [
            NODE or "node",
            str(Path(__file__).parent / "web_smoke_ask.js"),
            str(WEB_DIR / "app.js"),
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == "OK"
