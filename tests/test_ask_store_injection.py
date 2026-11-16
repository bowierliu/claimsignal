"""Regression: an injected, still-empty SessionStore must be the one AskService uses."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from agent_fixtures import make_guard
from claims_copilot.agent.ask import AskService, AskToolRunner
from claims_copilot.agent.prompt import load_prompt
from claims_copilot.agent.session import SessionStore


def test_an_empty_injected_store_is_kept(tmp_path: Path) -> None:
    store = SessionStore(label_prefix="askeval-x-")
    assert len(store) == 0  # an empty store is falsy, which is what broke `store or ...`
    service = AskService(
        provider=cast(Any, object()),
        tools=cast(AskToolRunner, object()),
        guard=make_guard(tmp_path),
        prompt=load_prompt("agent_v2"),
        store=store,
    )
    assert cast(Any, service)._store is store
    session, _ = store.get_or_create(None)
    assert session.run_label.startswith("askeval-x-")
