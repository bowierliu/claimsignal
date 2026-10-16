"""Scrub tests use invented descriptors only: no real CPT descriptor text belongs in the repo."""

from __future__ import annotations

from claims_copilot.ingest.scrub import PLACEHOLDER, scrub


def test_parenthetical_descriptor_is_redacted_but_code_kept() -> None:
    text = "Do not report 90001 (Widget frobnication; with extra gadget, single) with 90002."
    clean, reds = scrub(text)
    assert clean == f"Do not report 90001 ({PLACEHOLDER}) with 90002."
    assert "frobnication" not in clean
    assert [(r.code, r.rule) for r in reds] == [("90001", "paren")]
    assert reds[0].chars == len("Widget frobnication; with extra gadget, single")
    assert len(reds[0].sha256) == 64


def test_descriptor_wrapped_across_lines_with_nested_parens() -> None:
    text = "code 90003 (Gadget\n  calibration (manual) and\n  recording) applies"
    clean, reds = scrub(text)
    assert "calibration" not in clean
    assert clean.startswith(f"code 90003 ({PLACEHOLDER})")
    assert len(reds) == 1


def test_cms_commentary_parentheticals_are_kept() -> None:
    for kept in (
        "code 90802 (or any successor codes) is",
        "report 95146 (the two-venom code) once",
        "code 90004 (see section 4 for details)",
    ):
        assert scrub(kept) == (kept, [])


def test_dash_style_descriptor_is_redacted() -> None:
    clean, reds = scrub("90005 \u2013 Widget inspection of the outer housing\nNext line")
    assert clean == f"90005 \u2013 {PLACEHOLDER}\nNext line"
    assert reds[0].rule == "dash"


def test_code_ranges_dates_and_revision_numbers_are_untouched() -> None:
    for plain in (
        "codes 90006 - 90009 are payable",
        "(Rev. 13725, Issued: 04-10-26; Effective: 01-01-26)",
        "R4047CP 05/11/2018 Updates",
    ):
        assert scrub(plain) == (plain, []), plain


def test_scrub_is_idempotent_and_leaves_no_residual_descriptor() -> None:
    once, _ = scrub("90001 (Widget frobnication; single) and 90007 \u2013 Gadget calibration kit")
    twice, reds = scrub(once)
    assert twice == once
    assert reds == []


def test_category_ii_and_iii_codes_are_covered() -> None:
    clean, reds = scrub("report 0001F (Widget status documented and reviewed) now")
    assert PLACEHOLDER in clean
    assert reds[0].code == "0001F"


def test_log_never_contains_descriptor_text() -> None:
    _, reds = scrub("90001 (Widget frobnication; single)")
    assert "Widget" not in repr(reds)


def test_table_style_line_descriptor_with_wrapped_continuation() -> None:
    text = (
        "intro\n90010 Gadget examination, outer housing; less than 3 views\n  per side\n"
        "Next paragraph"
    )
    clean, reds = scrub(text)
    assert clean == f"intro\n90010 {PLACEHOLDER}\nNext paragraph"
    assert reds[0].rule == "line"


def test_dash_descriptor_continuation_lines_are_absorbed() -> None:
    clean, _ = scrub(
        "code 90011: Widget inspection of the\nouter housing and frame; second step\nSee below"
    )
    assert "housing" not in clean
    assert clean.endswith("\nSee below")


def test_federal_register_citations_are_not_descriptors() -> None:
    text = "final rule (84 Fed. Reg. 60648 (Nov. 8, 2019)) permits"
    assert scrub(text) == (text, [])


def test_long_nested_descriptor_up_to_600_chars_is_redacted() -> None:
    inner = "Widget frobnication of programmable gadget (includes calibration status); " * 5
    clean, reds = scrub(f"or 90014 ({inner.strip()}) since payment")
    assert "calibration" not in clean
    assert clean == f"or 90014 ({PLACEHOLDER}) since payment"
    assert len(reds) == 1


def test_inline_descriptor_needs_punctuation_to_be_redacted() -> None:
    clean, reds = scrub("report 90012 Widget frobnication, single; with gadget in one session")
    assert "frobnication" not in clean
    assert reds[0].rule == "inline"
    plain = "when 90013 Medicare pays the claim as billed"
    assert scrub(plain) == (plain, [])
