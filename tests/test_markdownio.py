"""Markdown chapter I/O tests (SPEC §5)."""

from __future__ import annotations

from src.pipeline import markdownio


def test_parse_chapter_extracts_frontmatter():
    md = (
        '---\ntitle: "Chapter 1"\nindex: "1"\n---\n'
        "\n# Chapter 1: Dying House of Horrors\n\n"
        "First paragraph.\n\nSecond paragraph."
    )
    fm, raw_fm, heading, paras = markdownio.parse_chapter(md)

    assert fm["title"] == "Chapter 1"
    assert fm["index"] == "1"
    assert heading == "# Chapter 1: Dying House of Horrors"
    assert paras == ["First paragraph.", "Second paragraph."]


def test_parse_chapter_without_frontmatter():
    md = "# Only Heading\n\nBody text."
    fm, raw_fm, heading, paras = markdownio.parse_chapter(md)
    assert fm == {}
    assert raw_fm == ""
    assert heading == "# Only Heading"
    assert paras == ["Body text."]


def test_build_output_roundtrip(chapter_path):
    text = chapter_path.read_text(encoding="utf-8")
    fm, _raw, heading, paras = markdownio.parse_chapter(text)
    out = markdownio.build_output(fm, heading, paras)

    fm2, _raw2, heading2, paras2 = markdownio.parse_chapter(out)
    assert fm2.get("title") == fm.get("title")
    assert heading2 == heading
    assert paras2 == paras


def test_paragraph_count():
    assert markdownio.paragraph_count("a\n\nb\n\nc") == 3
    assert markdownio.paragraph_count("  a  \n\n  b  ") == 2


def test_hash_version_stable():
    assert markdownio.hash_version("same") == markdownio.hash_version("same")
    assert markdownio.hash_version("same") != markdownio.hash_version("different")