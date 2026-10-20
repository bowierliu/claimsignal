"""The evidence registry: the runtime, not the model, names what can be cited.

Every tool result gets an id (`E1`, `E2`, ...). Findings and observations inside it get
`E1.f1`, `E1.o1`; dossier sub-results get `E1.r1.f1`. Policy search hits keep their `chunk_id`.
Registration happens AFTER oversized results are trimmed, so everything the model can cite is
something it was actually shown.
"""

from __future__ import annotations

import json
from typing import Any

_LIST_CAPS = (None, 20, 10, 5, 3)


class ResultTooLargeError(ValueError):
    """A tool result stays above the size limit even after trimming every list to 3 items."""


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _cap_lists(node: Any, cap: int) -> Any:
    if isinstance(node, list):
        return [_cap_lists(item, cap) for item in node[:cap]]
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        omitted: dict[str, int] = {}
        for key, value in node.items():
            if isinstance(value, list) and len(value) > cap:
                omitted[key] = len(value) - cap
            out[key] = _cap_lists(value, cap)
        if omitted:
            out["_omitted"] = omitted
        return out
    return node


def trim(payload: dict[str, Any], max_chars: int) -> dict[str, Any]:
    """Shorten every list (and say how many items were dropped) until the JSON fits."""
    for cap in _LIST_CAPS:
        candidate = payload if cap is None else _cap_lists(payload, cap)
        if len(dumps(candidate)) <= max_chars:
            return candidate
    raise ResultTooLargeError(f"result is larger than {max_chars} characters after trimming")


class EvidenceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, str] = {}
        self._chunks: dict[str, tuple[str, str]] = {}
        self._count = 0

    @property
    def latest_id(self) -> str | None:
        return f"E{self._count}" if self._count else None

    def register_result(self, payload: dict[str, Any]) -> str:
        """Annotate `payload` in place with evidence ids and return the result's id."""
        self._count += 1
        evidence_id = f"E{self._count}"
        payload["evidence_id"] = evidence_id
        self._sources[evidence_id] = f"result:{evidence_id}"
        self._walk(evidence_id, evidence_id, payload)
        return evidence_id

    def _walk(self, root: str, prefix: str, node: dict[str, Any]) -> None:
        for key, letter in (("findings", "f"), ("observations", "o")):
            items = node.get(key)
            if isinstance(items, list):
                for i, item in enumerate(items, start=1):
                    if isinstance(item, dict):
                        item["evidence_id"] = f"{prefix}.{letter}{i}"
                        self._sources[item["evidence_id"]] = f"result:{root}"
        # Screen flags are shown with their own ids (`E1.s1`); without them a model cites the
        # raw `flag_id`, which the registry rightly rejects (found in the first smoke run).
        flags = node.get("flags")
        if isinstance(flags, list):
            for i, item in enumerate(flags, start=1):
                if isinstance(item, dict):
                    item["evidence_id"] = f"{prefix}.s{i}"
                    # A screen flag is its own source: the screen and the checks are different
                    # mechanisms, so a flag that the checks do not support is a real disagreement.
                    self._sources[item["evidence_id"]] = f"flags:{root}"
        results = node.get("results")
        if isinstance(results, list):
            for j, item in enumerate(results, start=1):
                if isinstance(item, dict):
                    item["evidence_id"] = f"{prefix}.r{j}"
                    self._sources[item["evidence_id"]] = f"result:{root}"
                    self._walk(root, f"{prefix}.r{j}", item)
        hits = node.get("hits")
        if isinstance(hits, list):
            for hit in hits:
                if isinstance(hit, dict) and isinstance(hit.get("chunk_id"), str):
                    source = hit.get("source")
                    source_id = source.get("source_id") if isinstance(source, dict) else None
                    key = f"source:{source_id}" if isinstance(source_id, str) else "source:?"
                    text = hit.get("text")
                    self._chunks[hit["chunk_id"]] = (key, text if isinstance(text, str) else "")
                    self._sources[hit["chunk_id"]] = key

    def has(self, citation: str) -> bool:
        return citation in self._sources

    def source_key(self, citation: str) -> str:
        """Which independent source a citation comes from (a tool result or a policy source)."""
        return self._sources[citation]

    def chunk_text(self, chunk_id: str) -> str | None:
        found = self._chunks.get(chunk_id)
        return found[1] if found else None

    def ids(self) -> list[str]:
        return sorted(self._sources)
