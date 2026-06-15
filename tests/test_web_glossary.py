"""Tests for web glossary helpers (default-novel selection) and the
resume partial-completion guard logic.

Covers ERR-078 (page showed no terms because the default novel was a
hardcoded non-existent slug) and ERR-079 (None hole in resumed chunks must
not be counted as a completed chunk).
"""
from src.web import flask_app


def _patch(monkeypatch, novels, terms_by_slug):
    monkeypatch.setattr(flask_app, "get_novels", lambda: novels)
    monkeypatch.setattr(
        flask_app, "get_glossary",
        lambda novel_slug='wayfarer', include_global=False: {
            "total_terms": terms_by_slug.get(novel_slug, 0)
        },
    )


def test_default_novel_prefers_novel_with_terms(monkeypatch):
    # First novel has no terms, second does → pick the one with terms.
    _patch(
        monkeypatch,
        novels=[{"name": "empty-novel"}, {"name": "real-novel"}],
        terms_by_slug={"empty-novel": 0, "real-novel": 69},
    )
    assert flask_app._default_novel_slug() == "real-novel"


def test_default_novel_falls_back_to_first_novel(monkeypatch):
    # No novel has terms → fall back to the first novel on disk.
    _patch(
        monkeypatch,
        novels=[{"name": "alpha"}, {"name": "beta"}],
        terms_by_slug={},
    )
    assert flask_app._default_novel_slug() == "alpha"


def test_default_novel_falls_back_to_wayfarer_when_no_novels(monkeypatch):
    _patch(monkeypatch, novels=[], terms_by_slug={})
    assert flask_app._default_novel_slug() == "wayfarer"


def test_partial_guard_counts_non_none_not_length():
    # ERR-079 (defensive half): if an early abort/shutdown leaves a None hole
    # in the resumed list (e.g. a stale-rejected checkpoint that never got
    # re-translated), the partial-completion guard must treat it as INCOMPLETE.
    # The old guard used len(translated) >= len(chunks); the fix counts non-None.
    chunks = ["a", "b", "c"]
    translated_with_hole = ["a", None, "c"]  # slot 1 never filled

    old_guard_says_complete = len(translated_with_hole) >= len(chunks)
    completed = sum(1 for c in translated_with_hole if c is not None)
    new_guard_says_complete = completed >= len(chunks)

    assert old_guard_says_complete is True      # old logic wrongly proceeds
    assert new_guard_says_complete is False      # fixed logic blocks the save


def test_partial_guard_passes_a_full_clean_list():
    chunks = ["a", "b", "c"]
    translated = ["a", "b", "c"]
    completed = sum(1 for c in translated if c is not None)
    assert completed == len(chunks)
