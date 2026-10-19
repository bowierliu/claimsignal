"""Loader for the owner-approved source catalog (SOURCES/catalog.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast, get_args

Kind = Literal["pdf", "xml", "html", "zip"]
Role = Literal["corpus", "terms", "data"]
TermsStatus = Literal["OBSERVED", "UNVERIFIED"]


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class CatalogEntry:
    source_id: str
    role: Role
    group: str
    title: str
    publisher: str
    url: str
    kind: Kind
    version: str
    expected_phrases: tuple[str, ...]
    terms_source_id: str
    terms_status: TermsStatus
    terms_quote: str

    @property
    def extension(self) -> str:
        return {"pdf": "pdf", "xml": "xml", "html": "html", "zip": "zip"}[self.kind]


def _text(row: dict[str, Any], key: str, *, required: bool = True) -> str:
    value = row.get(key, "")
    if not isinstance(value, str):
        raise CatalogError(f"{row.get('source_id')}: {key} must be a string")
    if required and not value.strip():
        raise CatalogError(f"{row.get('source_id')}: {key} is required")
    return value


def parse_catalog(data: dict[str, Any]) -> list[CatalogEntry]:
    entries: list[CatalogEntry] = []
    seen: set[str] = set()
    rows = data.get("source")
    if not isinstance(rows, list) or not rows:
        raise CatalogError("catalog has no [[source]] entries")
    for row in rows:
        source_id = _text(row, "source_id")
        if source_id in seen:
            raise CatalogError(f"duplicate source_id {source_id}")
        seen.add(source_id)
        kind = _text(row, "kind")
        if kind not in get_args(Kind):
            raise CatalogError(f"{source_id}: unknown kind {kind!r}")
        typed_kind = cast(Kind, kind)
        role = row.get("role", "corpus")
        if role not in ("corpus", "terms", "data"):
            raise CatalogError(f"{source_id}: unknown role {role!r}")
        url = _text(row, "url")
        if not url.startswith("https://"):
            raise CatalogError(f"{source_id}: url must be https")
        phrases = row.get("expected_phrases")
        if (
            not isinstance(phrases, list)
            or not phrases
            or not all(isinstance(p, str) for p in phrases)
        ):
            raise CatalogError(f"{source_id}: expected_phrases must be a non-empty list of strings")
        terms_status = row.get("terms_status", "UNVERIFIED")
        if terms_status not in ("OBSERVED", "UNVERIFIED"):
            raise CatalogError(f"{source_id}: unknown terms_status {terms_status!r}")
        entries.append(
            CatalogEntry(
                source_id=source_id,
                role=role,
                group=_text(row, "group", required=False) or role,
                title=_text(row, "title"),
                publisher=_text(row, "publisher"),
                url=url,
                kind=typed_kind,
                version=_text(row, "version", required=False),
                expected_phrases=tuple(phrases),
                terms_source_id=_text(row, "terms_source_id", required=False),
                terms_status=terms_status,
                terms_quote=_text(row, "terms_quote", required=False),
            )
        )
    by_id = {e.source_id: e for e in entries}
    for entry in entries:
        if entry.terms_source_id and entry.terms_source_id not in by_id:
            raise CatalogError(
                f"{entry.source_id}: unknown terms_source_id {entry.terms_source_id}"
            )
    return entries


def load_catalog(path: Path) -> list[CatalogEntry]:
    with path.open("rb") as f:
        return parse_catalog(tomllib.load(f))
