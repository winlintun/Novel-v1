"""Glossary loading / indexing tests."""

from __future__ import annotations

from src.pipeline.glossary import Glossary, load_entries


def test_load_flat_entries(glossary):
    assert len(glossary.index) >= 5
    assert glossary.index[0]["en"] == "Haunted House"  # sorted longest-first


def test_index_fields_present(glossary):
    chen = next(e for e in glossary.index if e["en"] == "Chen Ge")
    assert chen["my"] == "ချန်ဂီ"
    assert "Boss" in chen["aliases"]
    assert chen["pronoun"] == "ငါ"
    assert chen["category"] == "character"


def test_entries_for_matches_alias(glossary):
    found = glossary.entries_for("Chen Ge owned a Haunted House")
    names = [e["en"] for e in found]
    assert "Chen Ge" in names
    assert "Haunted House" in names


def test_speakers_in(glossary):
    assert glossary.speakers_in("Chen Ge said hello.") == ["Chen Ge"]
    assert "Xu Wan" in glossary.speakers_in("Xiao Wan ran.")


def test_term_set(glossary):
    ts = glossary.term_set()
    assert "Chen Ge" in ts and "Boss" in ts and "Haunted House" in ts


def test_section_dynamic_filters_by_text(glossary):
    section = glossary.section(["Uncle Xu and Haunted House"], dynamic=True)
    assert "Uncle Xu" in section
    assert "Chen Ge" not in section
    assert "= အန်ကယ်ရှူ" in section


def test_section_static_includes_all(glossary):
    section = glossary.section()
    assert "Chen Ge" in section and "Haunted House" in section


def test_load_entries_nested_categories(tmp_path):
    data = {
        "categories": {
            "chars": {
                "entries": [
                    {"term": "Cai", "translation": "ဆိုင်"},
                    {"term": "Chen Ge", "translation": "ချန်ဂီ"},
                ]
            }
        }
    }
    g = Glossary(entries=data)
    assert len(g.index) == 2
    assert g.index[0]["en"] == "Chen Ge"  # longest-first


def test_empty_index_when_missing_file():
    g = Glossary("does-not-exist.json")
    assert g.index == []