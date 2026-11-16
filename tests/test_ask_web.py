"""The Ask tab in the browser script (spec item 11), run under node with a fake DOM.

Views come from the real AskService (fake provider), so the script is checked against what the
server actually sends."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from agent_fixtures import answer_json
from ask_fixtures import (
    DOSSIER,
    MOD_CHUNK,
    UNIT_FINDING,
    ask_chunks,
    ask_sources,
    insufficient,
    make_service,
    scripted,
)
from claims_copilot.agent.ask_search import AskPolicySearch
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
    answered = make_service(
        tmp_path / "a",
        scripted(
            [DOSSIER, ("search_policy", {"q": "modifier 59"})],
            answer_json(
                summary=[
                    {"text": f"{HOSTILE} Line 3 bills 5 units.", "citations": [UNIT_FINDING]},
                    {"text": "The manual describes modifier 59.", "citations": [MOD_CHUNK]},
                ],
                policy_quotes=[{"chunk_id": MOD_CHUNK, "quote": HOSTILE}],
            ),
        ),
        search=hostile_search(),
    ).ask(None, "What did the checks find?", "C0000001")
    assert answered["status"] == "ANSWERED", answered
    answered["sources"][0]["label"] = HOSTILE
    answered["sources"][1]["url"] = "javascript:alert(1)"

    insufficient_view = make_service(
        tmp_path / "b", scripted([("search_policy", {"q": "helicopter"})], insufficient())
    ).ask(None, "What about helicopters?", None)
    assert insufficient_view["status"] == "INSUFFICIENT_EVIDENCE"

    invalid_view = make_service(
        tmp_path / "c",
        scripted([DOSSIER], answer_json(summary=[{"text": "A fact.", "citations": ["E99"]}])),
    ).ask(None, "And the modifier?", None)
    assert invalid_view["status"] == "INVALID_OUTPUT"
    return [answered, insufficient_view, invalid_view]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_ask_tab_renders_views_as_text_and_posts_same_origin_json(tmp_path: Path) -> None:
    for sub in ("a", "b", "c"):
        (tmp_path / sub).mkdir()
    path = tmp_path / "ask_fixtures.json"
    path.write_text(json.dumps({"views": build_views(tmp_path), "hostile": HOSTILE}), "utf-8")
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
