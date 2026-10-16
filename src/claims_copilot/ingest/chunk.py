"""Split scrubbed page text into overlapping, page-anchored chunks for retrieval.

Chunk ids are deterministic (`<source_id>:<page_start>-<page_end>:<index>`), so re-running on the
same text yields identical ids and hashes. Every chunk records the physical PDF page range it came
from so a citation can point a human at the page.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from claims_copilot.project import CHUNKS_DIR, MANIFEST_PATH, TEXT_DIR
from claims_copilot.sources.manifest import read_manifest

TARGET_CHARS = 1800
MIN_CHARS = 1100
MAX_CHARS = 2400
OVERLAP_CHARS = 250
HEADER_PAGE_FRACTION = 0.4
MIN_PAGES_FOR_HEADER_DETECTION = 8
MAX_HEADER_LINE_CHARS = 120
EDGE_LINES = 2

_SENTENCE_END = re.compile(r"[.;:!?][\"')\u201d\u2019]?\s")
_HEADING = re.compile(
    r"(?m)^\s*(\d+(?:\.\d+)+|[A-Z]\.|Chapter \d+)\s*[-\u2013\u2014]?\s*([A-Z0-9][^.\n]{4,90})$"
)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_id: str
    page_start: int
    page_end: int
    section: str
    text: str
    sha256: str


def strip_running_headers(pages: list[str]) -> list[str]:
    """Drop short, repeating lines (ignoring digits) at the top or bottom edge of many pages.

    Only the first and last EDGE_LINES non-empty lines of a page are candidates, so templated
    body lines in the middle of a page are never removed.
    """
    if len(pages) < MIN_PAGES_FOR_HEADER_DETECTION:
        return pages

    def key(line: str) -> str:
        return re.sub(r"\d+", "#", re.sub(r"\s+", " ", line.strip()))

    def edge_keys(page: str) -> set[str]:
        lines = [line for line in page.splitlines() if line.strip()]
        return {key(line) for line in lines[:EDGE_LINES] + lines[-EDGE_LINES:]}

    counts: Counter[str] = Counter()
    for page in pages:
        counts.update(edge_keys(page))
    threshold = HEADER_PAGE_FRACTION * len(pages)
    noisy = {k for k, n in counts.items() if n >= threshold and len(k) <= MAX_HEADER_LINE_CHARS}

    def clean(page: str) -> str:
        lines = [line for line in page.splitlines() if line.strip()]
        keep = [
            line
            for i, line in enumerate(lines)
            if not (key(line) in noisy and (i < EDGE_LINES or i >= len(lines) - EDGE_LINES))
        ]
        return "\n".join(keep)

    return [clean(page) for page in pages]


def _cut_point(text: str, start: int) -> int:
    """Pick a chunk end after `start`, preferring a sentence boundary in [MIN, MAX]."""
    hard_end = min(len(text), start + MAX_CHARS)
    if hard_end == len(text):
        return hard_end
    window_lo = start + MIN_CHARS
    best = None
    for m in _SENTENCE_END.finditer(text, window_lo, hard_end):
        best = m.end()
        if m.end() >= start + TARGET_CHARS:
            break
    if best is not None:
        return best
    space = text.rfind(" ", window_lo, hard_end)
    return space if space > start else hard_end


def chunk_source(source_id: str, pages: list[str]) -> list[Chunk]:
    pages = strip_running_headers(pages)
    parts: list[str] = []
    starts: list[int] = []
    pos = 0
    for page in pages:
        starts.append(pos)
        cleaned = re.sub(r"[ \t]+", " ", page).strip()
        parts.append(cleaned)
        pos += len(cleaned) + 2
    text = "\n\n".join(parts)

    def page_of(offset: int) -> int:
        return bisect.bisect_right(starts, offset)  # 1-based: starts[0] is page 1

    headings = [(m.start(), f"{m.group(1)} {m.group(2).strip()}") for m in _HEADING.finditer(text)]
    heading_offsets = [h[0] for h in headings]

    chunks: list[Chunk] = []
    cursor = 0
    index = 0
    while cursor < len(text):
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text):
            break
        end = _cut_point(text, cursor)
        body = text[cursor:end].strip()
        if body:
            first = page_of(cursor)
            last = page_of(max(cursor, end - 1))
            h = bisect.bisect_right(heading_offsets, cursor) - 1
            chunks.append(
                Chunk(
                    chunk_id=f"{source_id}:{first}-{last}:{index:04d}",
                    source_id=source_id,
                    page_start=first,
                    page_end=last,
                    section=headings[h][1] if h >= 0 else "",
                    text=body,
                    sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
                )
            )
            index += 1
        if end >= len(text):
            break
        next_cursor = end - OVERLAP_CHARS
        boundary = text.find(" ", next_cursor, end)
        cursor = max(boundary + 1 if boundary != -1 else end, cursor + 1)
    return chunks


def load_pages(path: Path) -> list[str]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    rows.sort(key=lambda r: r["page"])
    return [r["text"] for r in rows]


def run() -> None:
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    all_chunks: list[Chunk] = []
    for row in read_manifest(MANIFEST_PATH):
        if row.get("role") != "corpus" or row["status"] != "VERIFIED":
            continue
        chunks = chunk_source(row["source_id"], load_pages(TEXT_DIR / f"{row['source_id']}.jsonl"))
        all_chunks.extend(chunks)
        sizes = [len(c.text) for c in chunks]
        print(f"{row['source_id']:<26} chunks={len(chunks):>4} max={max(sizes, default=0):>5}")
    (CHUNKS_DIR / "chunks.jsonl").write_text(
        "".join(json.dumps(asdict(c), ensure_ascii=False) + "\n" for c in all_chunks),
        encoding="utf-8",
    )
    total = sum(len(c.text) for c in all_chunks)
    print(f"total chunks={len(all_chunks)} chars={total}")


if __name__ == "__main__":
    run()
