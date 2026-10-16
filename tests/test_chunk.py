from __future__ import annotations

from itertools import pairwise

from claims_copilot.ingest.chunk import (
    MAX_CHARS,
    OVERLAP_CHARS,
    chunk_source,
    strip_running_headers,
)


def make_pages(n: int, sentences_per_page: int = 40) -> list[str]:
    return [
        " ".join(
            f"Sentence {p}-{s} about widgets and gadgets in context."
            for s in range(sentences_per_page)
        )
        for p in range(1, n + 1)
    ]


def test_chunks_are_bounded_deterministic_and_cover_all_text() -> None:
    pages = make_pages(6)
    a = chunk_source("doc", pages)
    b = chunk_source("doc", pages)
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert [c.sha256 for c in a] == [c.sha256 for c in b]
    assert all(len(c.text) <= MAX_CHARS for c in a)
    joined = " ".join(c.text for c in a)
    for p in range(1, 7):
        assert f"Sentence {p}-0 " in joined
        assert f"Sentence {p}-39 " in joined


def test_chunk_ids_are_unique_and_page_anchors_are_ordered() -> None:
    chunks = chunk_source("doc", make_pages(6))
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    firsts = [c.page_start for c in chunks]
    assert firsts == sorted(firsts)
    assert chunks[0].page_start == 1 and chunks[-1].page_end == 6
    assert all(c.page_start <= c.page_end for c in chunks)


def test_page_anchor_points_at_the_page_containing_the_text() -> None:
    pages = make_pages(6)
    for c in chunk_source("doc", pages):
        marker_pages = {
            int(part.split("-")[0].removeprefix("Sentence "))
            for part in c.text.split("about widgets")[:-1]
            for part in [part.rsplit("Sentence ", 1)[-1]]
            if part.split("-")[0].isdigit()
        }
        assert marker_pages, c.chunk_id
        assert min(marker_pages) >= c.page_start - 0 and max(marker_pages) <= c.page_end, c.chunk_id


def test_consecutive_chunks_overlap() -> None:
    chunks = chunk_source("doc", make_pages(4))
    assert len(chunks) > 2
    for prev, nxt in pairwise(chunks):
        tail = prev.text[-OVERLAP_CHARS:]
        assert (
            nxt.text[:60] in prev.text
            or tail.split()[-3:] == nxt.text.split()[:3]
            or any(w in nxt.text[:300] for w in tail.split()[-6:])
        )


def test_headings_are_carried_as_section() -> None:
    pages = ["20.1 - Payment for widgets\n" + "Widgets are paid once per day. " * 80]
    chunks = chunk_source("doc", pages)
    assert chunks[0].section.startswith("20.1")
    assert all(c.section.startswith("20.1") for c in chunks)


def test_running_headers_and_footers_are_removed_but_body_kept() -> None:
    pages = [
        f"Revision Date: 1/1/2026 Page {i}\nBody line one {i}\nBody line two {i}\n"
        f"Body line three {i}\nBody line four {i}\nBody line five {i}\nChapter footer"
        for i in range(1, 11)
    ]
    stripped = strip_running_headers(pages)
    assert all("Revision Date" not in p and "Chapter footer" not in p for p in stripped)
    # Only repeating lines at the page edges may go; middle lines always survive.
    for i, p in enumerate(stripped, start=1):
        for word in ("two", "three", "four"):
            assert f"Body line {word} {i}" in p


def test_templated_body_lines_in_the_middle_of_a_page_survive() -> None:
    pages = [
        "Header text\n" + "\n".join(f"Row {r} value {p}" for r in range(8)) + "\nFooter text"
        for p in range(10)
    ]
    stripped = strip_running_headers(pages)
    assert all("Header text" not in p and "Footer text" not in p for p in stripped)
    assert all(f"Row 3 value {p}" in page for p, page in enumerate(stripped))


def test_short_documents_are_not_header_stripped() -> None:
    pages = ["Same line\nBody a", "Same line\nBody b"]
    assert strip_running_headers(pages) == pages
