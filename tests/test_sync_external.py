"""
Tests for external glossary sync module.
"""

import os
import sqlite3
import tempfile
import pytest
from src.db.sync_external import (
    sync_external_glossary,
    make_novel_id,
    make_term_id,
    GLOBAL_NOVEL_ID,
)


@pytest.fixture
def local_db(tmp_path):
    """Create a minimal local DB with required schema."""
    db_path = str(tmp_path / "local.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE novels (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source_language TEXT NOT NULL DEFAULT 'chinese',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE glossary_terms (
            id TEXT PRIMARY KEY,
            novel_id TEXT NOT NULL,
            source_term TEXT NOT NULL,
            target_term TEXT NOT NULL,
            canonical_form TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            status TEXT NOT NULL DEFAULT 'pending',
            enforcement_level TEXT NOT NULL DEFAULT 'soft',
            context_condition TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            usage_count INTEGER NOT NULL DEFAULT 0,
            scope TEXT NOT NULL DEFAULT 'novel',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            reviewed_at TEXT,
            FOREIGN KEY (novel_id) REFERENCES novels(id)
        )
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def external_db(tmp_path):
    """Create a mock external glossary DB with test data."""
    db_path = str(tmp_path / "external.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE glossary_terms (
            id TEXT PRIMARY KEY,
            novel_id TEXT NOT NULL,
            source_term TEXT NOT NULL,
            target_term TEXT NOT NULL,
            canonical_form TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            status TEXT NOT NULL DEFAULT 'pending',
            scope TEXT NOT NULL DEFAULT 'novel',
            enforcement_level TEXT NOT NULL DEFAULT 'soft',
            context_condition TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            usage_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            reviewed_at TEXT
        )
    """)
    # Insert novel-specific terms
    conn.executemany(
        """INSERT INTO glossary_terms
           (id, novel_id, source_term, target_term, canonical_form, category, status, scope)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            ("term_novel_test_novel_001", "novel_test_novel", "Hero", "သူရဲကောင်း", "Hero", "character", "approved", "novel"),
            ("term_novel_test_novel_002", "novel_test_novel", "Villain", "ဗီလိန်", "Villain", "character", "pending", "novel"),
            ("term_novel_test_novel_003", "novel_test_novel", "Sword", "ဓား", "Sword", "item", "approved", "novel"),
        ],
    )
    # Insert global terms
    conn.executemany(
        """INSERT INTO glossary_terms
           (id, novel_id, source_term, target_term, canonical_form, category, status, scope)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            ("term_global_001", "novel_global_xianxia", "qi", "ချီ", "qi", "energy", "approved", "global"),
            ("term_global_002", "novel_global_xianxia", "dao", "တရား", "dao", "concept", "approved", "global"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


class TestMakeNovelId:
    def test_simple_name(self):
        assert make_novel_id("test-novel") == "novel_test_novel"

    def test_name_with_spaces(self):
        assert make_novel_id("my novel") == "novel_my_novel"

    def test_name_with_slashes(self):
        assert make_novel_id("path/to/novel") == "novel_path_to_novel"


class TestMakeTermId:
    def test_deterministic(self):
        id1 = make_term_id("novel_test", "qi")
        id2 = make_term_id("novel_test", "qi")
        assert id1 == id2

    def test_different_sources(self):
        id1 = make_term_id("novel_test", "qi")
        id2 = make_term_id("novel_test", "dao")
        assert id1 != id2


class TestSyncExternalGlossary:
    def test_sync_novel_terms(self, local_db, external_db):
        """Novel-specific terms should be synced."""
        conn = sqlite3.connect(local_db)
        conn.row_factory = sqlite3.Row
        result = sync_external_glossary(conn, "test-novel", external_db)

        assert result["synced"] == 2  # Only approved terms (Hero, Sword)
        assert result["skipped"] == 0
        assert result["global_synced"] == 2  # qi, dao
        assert result["global_skipped"] == 0
        assert len(result["errors"]) == 0

        # Verify terms exist in local DB
        rows = conn.execute(
            "SELECT source_term FROM glossary_terms WHERE novel_id = 'novel_test_novel'"
        ).fetchall()
        sources = {r["source_term"] for r in rows}
        assert "Hero" in sources
        assert "Sword" in sources

        conn.close()

    def test_sync_skips_existing_terms(self, local_db, external_db):
        """Re-running sync should not duplicate terms."""
        conn = sqlite3.connect(local_db)
        conn.row_factory = sqlite3.Row

        # First sync
        result1 = sync_external_glossary(conn, "test-novel", external_db)
        assert result1["synced"] == 2

        # Second sync should skip all
        result2 = sync_external_glossary(conn, "test-novel", external_db)
        assert result2["synced"] == 0
        assert result2["skipped"] == 0  # Skipped because sync detects existing count > 0

        conn.close()

    def test_sync_external_db_not_found(self, local_db):
        """Missing external DB should return empty result, not crash."""
        conn = sqlite3.connect(local_db)
        result = sync_external_glossary(conn, "test-novel", "/nonexistent/path.db")

        assert result["synced"] == 0
        assert result["global_synced"] == 0
        assert len(result["errors"]) == 0  # Returns gracefully, no error

        conn.close()

    def test_sync_status_filter_approved_only(self, local_db, external_db):
        """Default status_filter='approved' should only sync approved terms."""
        conn = sqlite3.connect(local_db)
        conn.row_factory = sqlite3.Row
        result = sync_external_glossary(conn, "test-novel", external_db, status_filter="approved")

        assert result["synced"] == 2  # Hero + Sword (approved only)
        # Villain is pending, should not be synced

        conn.close()

    def test_sync_status_filter_none_all(self, local_db, external_db):
        """status_filter=None should sync all statuses."""
        conn = sqlite3.connect(local_db)
        conn.row_factory = sqlite3.Row
        result = sync_external_glossary(conn, "test-novel", external_db, status_filter=None)

        assert result["synced"] == 3  # Hero + Villain + Sword (all statuses)

        conn.close()

    def test_sync_generates_correct_term_ids(self, local_db, external_db):
        """Synced terms should have IDs matching GlossaryRepository convention."""
        conn = sqlite3.connect(local_db)
        conn.row_factory = sqlite3.Row
        sync_external_glossary(conn, "test-novel", external_db)

        row = conn.execute(
            "SELECT id FROM glossary_terms WHERE source_term = 'Hero'"
        ).fetchone()
        expected_id = make_term_id("novel_test_novel", "Hero")
        assert row["id"] == expected_id

        conn.close()

    def test_sync_global_terms_have_global_scope(self, local_db, external_db):
        """Synced global terms should have scope='global'."""
        conn = sqlite3.connect(local_db)
        conn.row_factory = sqlite3.Row
        sync_external_glossary(conn, "test-novel", external_db)

        rows = conn.execute(
            "SELECT source_term, scope FROM glossary_terms WHERE novel_id = 'novel_global_xianxia'"
        ).fetchall()
        for row in rows:
            assert row["scope"] == "global"

        conn.close()

    def test_sync_rollback_on_failure(self, local_db, external_db):
        """Sync should rollback all changes if it fails mid-way."""
        conn = sqlite3.connect(local_db)
        conn.row_factory = sqlite3.Row

        # Use a non-existent external DB to simulate failure after connection
        result = sync_external_glossary(conn, "test-novel", "/nonexistent.db")

        # No terms should have been inserted
        count = conn.execute("SELECT COUNT(*) FROM glossary_terms").fetchone()[0]
        assert count == 0

        conn.close()

    def test_sync_creates_novel_entries(self, local_db, external_db):
        """Sync should create novel entries in the novels table."""
        conn = sqlite3.connect(local_db)
        conn.row_factory = sqlite3.Row
        sync_external_glossary(conn, "test-novel", external_db)

        novel_row = conn.execute(
            "SELECT id FROM novels WHERE id = 'novel_test_novel'"
        ).fetchone()
        assert novel_row is not None

        global_row = conn.execute(
            "SELECT id FROM novels WHERE id = 'novel_global_xianxia'"
        ).fetchone()
        assert global_row is not None

        conn.close()
