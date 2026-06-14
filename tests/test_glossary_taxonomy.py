"""Tests for the two-tier glossary taxonomy + term_relationships graph."""

import tempfile
import os
import pytest

from src.glossary_taxonomy import (
    normalize_category, is_valid_relation, SUBTYPE_TO_CATEGORY, CATEGORIES,
)
from src.db.connection import DatabaseConnection
from src.db.schema import SchemaManager
from src.db.repositories.glossary_repo import GlossaryRepository, GLOBAL_NOVEL_ID


# ── taxonomy ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("place", ("place", None)),            # coarse category passes through
    ("village", ("place", "village")),     # fine subtype -> coarse + subtype
    ("mountain", ("place", "mountain")),
    ("sect master", ("title", "sect_master")),   # natural-language alias
    ("secret realm", ("place", "secret_realm")),
    ("location", ("place", "city")),       # legacy label
    ("power_level", ("cultivation", "realm")),
    ("relam", ("cultivation", "realm")),   # misspelling alias
    ("", ("general", None)),
    (None, ("general", None)),
])
def test_normalize_category(value, expected):
    assert normalize_category(value) == expected


def test_unknown_value_kept_as_general_subtype():
    cat, sub = normalize_category("zorblax")
    assert cat == "general"
    assert sub == "zorblax"  # never silently dropped


def test_reverse_index_consistent():
    for sub, cat in SUBTYPE_TO_CATEGORY.items():
        assert sub in CATEGORIES[cat]


def test_relation_validity():
    assert is_valid_relation("located_in")
    assert is_valid_relation("member_of")
    assert not is_valid_relation("teleports_to")


# ── DB layer: subtype + relationships (global + per-novel in one DB) ──────────

@pytest.fixture
def repo():
    tmp = os.path.join(tempfile.mkdtemp(), "tax.db")
    db = DatabaseConnection(tmp)
    SchemaManager(db).create_all()
    db.execute("INSERT OR IGNORE INTO novels (id,name) VALUES (?,?)", ("novel_t", "T"))
    db.execute("INSERT OR IGNORE INTO novels (id,name) VALUES (?,?)", (GLOBAL_NOVEL_ID, "g"))
    return GlossaryRepository(db)


def test_add_term_derives_subtype(repo):
    t = repo.add_term("novel_t", "Greenwood Village", "ဂရင်းဝုဒ်", category="village")
    assert t["category"] == "place"
    assert t["subtype"] == "village"


def test_explicit_subtype_anchors_category(repo):
    t = repo.add_term("novel_t", "Azure Peak", " မိုးပြာတောင်", category="general", subtype="peak")
    assert t["category"] == "place"
    assert t["subtype"] == "peak"


def test_relationship_global_and_per_novel(repo):
    village = repo.add_term("novel_t", "Greenwood", "ဂ", category="village")
    empire = repo.add_global_term("Heavenspan Empire", "ကောင်းကင်", category="empire")
    # per-novel term -> GLOBAL term edge
    rid = repo.add_relationship("novel_t", village["id"], empire["id"], "located_in")
    assert rid is not None
    related = repo.get_related_terms(village["id"])
    assert any(r["source_term"] == "Heavenspan Empire" for r in related)


def test_relationship_idempotent_and_validated(repo):
    a = repo.add_term("novel_t", "A", "အေ", category="city")
    b = repo.add_term("novel_t", "B", "ဘီ", category="kingdom")
    assert repo.add_relationship("novel_t", a["id"], b["id"], "located_in") is not None
    assert repo.add_relationship("novel_t", a["id"], b["id"], "located_in") is None  # dup
    assert repo.add_relationship("novel_t", a["id"], b["id"], "bogus_relation") is None  # invalid


def test_relationship_inverse(repo):
    master = repo.add_term("novel_t", "Elder Wu", "ဦးဝူ", category="elder")
    disc = repo.add_term("novel_t", "Bai", "ပိုင်", category="disciple")
    repo.add_relationship("novel_t", master["id"], disc["id"], "master_of", add_inverse=True)
    # inverse edge disciple_of must now be queryable from the disciple
    out = repo.get_relationships(disc["id"], "out")
    assert any(r["relation_type"] == "disciple_of" for r in out)
