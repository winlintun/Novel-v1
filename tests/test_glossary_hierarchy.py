"""Glossary hierarchy + lock-lifecycle tests (NEW_TODO.md §5)."""

from __future__ import annotations

import json

from src.pipeline.glossary import PendingGlossary, merge_glossary_files


def test_merge_glossary_files_layer_override(tmp_path):
    global_ = tmp_path / "global.json"
    novel = tmp_path / "novel.json"
    global_.write_text(json.dumps({
        "categories": {"character": {"entries": [
            {"term": "Chen Ge", "translation": "ချန်ဂီ", "locked": True},
            {"term": "Haunted House", "translation": "သရဲစံအိမ်", "locked": True},
        ]}}
    }, ensure_ascii=False), encoding="utf-8")
    novel.write_text(json.dumps({
        "entries": [
            {"term": "Chen Ge", "translation": "ချန်ဂီ (ပြင်သစ်)", "locked": True},
            {"term": "Xu Wan", "translation": "ရှောင်ဝမ်", "locked": True},
        ]
    }, ensure_ascii=False), encoding="utf-8")

    entries = merge_glossary_files(global_, novel)
    by_key = {e["term"]: e["translation"] for e in entries}
    # novel overrides global for Chen Ge; Xu Wan is novel-only; house from global stays
    assert by_key["Chen Ge"] == "ချန်ဂီ (ပြင်သစ်)"
    assert by_key["Xu Wan"] == "ရှောင်ဝမ်"
    assert by_key["Haunted House"] == "သရဲစံအိမ်"
    # order: first-seen wins position
    assert entries[0]["term"] == "Chen Ge"
    assert entries[2]["term"] == "Xu Wan"


def test_merge_missing_files_is_empty():
    assert merge_glossary_files("nope-global.json", "nope-novel.json") == []


def test_merge_deduplicates_aliases(tmp_path):
    f = tmp_path / "g.json"
    f.write_text(json.dumps({"entries": [
        {"en": "Chen Ge", "my": "ချန်ဂီ"},
        {"en": "Chen Ge", "my": "ချန်ဂီးမ"},
    ]}), encoding="utf-8")
    entries = merge_glossary_files(f)
    assert len(entries) == 1
    assert entries[0]["my"] == "ချန်ဂီးမ"


def test_pending_glossary_roundtrip(tmp_path):
    p = tmp_path / "pending" / "auto_detected.json"
    pg = PendingGlossary(p)
    assert pg.detected("Marco", source_snippet="Marco opened the door.")
    assert pg.detected("Marco") is False  # no dupes
    assert "Marco" in pg.pending_names()
    pg2 = PendingGlossary(p)  # reload from disk
    assert "Marco" in pg2.pending_names()


def test_pending_curate_moves_to_locked(tmp_path):
    p = tmp_path / "pending.json"
    pg = PendingGlossary(p)
    pg.detected("Uncle Xu")
    entry = pg.curate("Uncle Xu", "ဦးဇူး")
    assert entry["state"] == "locked"
    assert pg.proposed() == []
    pg.detected("Marco")
    entry2 = pg.curate("Marco", "မာကို", locked=False)
    assert entry2["state"] == "proposed"
    proposed = pg.proposed()
    assert len(proposed) == 1
    assert proposed[0]["en"] == "Marco" and proposed[0]["state"] == "proposed"


def test_pending_cap_limits_entries(tmp_path):
    p = tmp_path / "pending.json"
    pg = PendingGlossary(p, max_pending=3)
    for name in ("A", "B", "C"):
        assert pg.detected(name) is True
    assert pg.detected("D") is False
    assert len(pg.entries) == 3


def test_pending_remove(tmp_path):
    p = tmp_path / "pending.json"
    pg = PendingGlossary(p)
    pg.detected("Marco")
    assert pg.remove("Marco") is True
    assert pg.remove("Marco") is False
    assert pg.pending_names() == []


def test_pending_ignores_corrupt_file(tmp_path):
    p = tmp_path / "pending.json"
    p.write_text("{not json", encoding="utf-8")
    pg = PendingGlossary(p)
    assert pg.entries == []
    assert pg.detected("Marco") is True
    assert pg.entries[0]["en"] == "Marco"


def test_pending_skips_empty_names(tmp_path):
    pg = PendingGlossary(tmp_path / "pending.json")
    assert pg.detected("") is False
    assert pg.detected("   ") is False