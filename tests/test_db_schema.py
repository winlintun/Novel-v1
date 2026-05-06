"""
Tests for SQLite schema creation and integrity.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from src.db.connection import DatabaseConnection
from src.db.schema import SchemaManager, SCHEMA_VERSION


@pytest.fixture
def db():
    """Create a temporary database connection."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        conn = DatabaseConnection(f.name)
        yield conn
        conn.close()
        Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def schema(db):
    """Create schema manager with initialized tables."""
    sm = SchemaManager(db)
    sm.create_all()
    return sm


EXPECTED_TABLES = [
    "novels", "glossary_terms", "term_variants", "chapters",
    "term_usage", "context_snapshots", "sync_jobs", "sync_job_chapters",
    "chapter_versions", "audit_log",
]


class TestSchemaCreation:
    def test_create_all_creates_all_tables(self, schema):
        for table in EXPECTED_TABLES:
            assert schema.table_exists(table), f"Table {table} not created"

    def test_create_all_is_idempotent(self, schema):
        schema.create_all()
        schema.create_all()
        for table in EXPECTED_TABLES:
            assert schema.table_exists(table)

    def test_drop_all_removes_all_tables(self, schema):
        schema.drop_all()
        for table in EXPECTED_TABLES:
            assert not schema.table_exists(table), f"Table {table} not dropped"

    def test_schema_version(self, schema):
        assert schema.get_schema_version() == SCHEMA_VERSION


class TestTableConstraints:
    def test_novel_primary_key(self, schema):
        schema.db.execute(
            "INSERT INTO novels (id, name, source_language) VALUES (?, ?, ?)",
            ("novel_test", "Test Novel", "chinese"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            schema.db.execute(
                "INSERT INTO novels (id, name, source_language) VALUES (?, ?, ?)",
                ("novel_test", "Duplicate", "english"),
            )

    def test_glossary_foreign_key(self, schema):
        schema.db.execute(
            "INSERT INTO novels (id, name, source_language) VALUES (?, ?, ?)",
            ("novel_fk", "FK Test", "chinese"),
        )
        schema.db.execute(
            """INSERT INTO glossary_terms (id, novel_id, source_term, target_term, canonical_form)
               VALUES (?, ?, ?, ?, ?)""",
            ("term_fk", "novel_fk", "源", "မြစ်", "源"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            schema.db.execute(
                """INSERT INTO glossary_terms (id, novel_id, source_term, target_term, canonical_form)
                   VALUES (?, ?, ?, ?, ?)""",
                ("term_bad_fk", "novel_nonexistent", "源", "မြစ်", "源"),
            )

    def test_chapter_unique_novel_num(self, schema):
        schema.db.execute(
            "INSERT INTO novels (id, name, source_language) VALUES (?, ?, ?)",
            ("novel_uniq", "Unique Test", "chinese"),
        )
        schema.db.execute(
            """INSERT INTO chapters (id, novel_id, chapter_num, file_path)
               VALUES (?, ?, ?, ?)""",
            ("chapter_novel_uniq_0001", "novel_uniq", 1, "test.md"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            schema.db.execute(
                """INSERT INTO chapters (id, novel_id, chapter_num, file_path)
                   VALUES (?, ?, ?, ?)""",
                ("chapter_dup", "novel_uniq", 1, "test2.md"),
            )

    def test_sync_job_chapters_composite_pk(self, schema):
        schema.db.execute(
            "INSERT INTO novels (id, name, source_language) VALUES (?, ?, ?)",
            ("novel_sjc", "SJC Test", "chinese"),
        )
        schema.db.execute(
            """INSERT INTO glossary_terms (id, novel_id, source_term, target_term, canonical_form)
               VALUES (?, ?, ?, ?, ?)""",
            ("term_sjc", "novel_sjc", "源", "မြစ်", "源"),
        )
        schema.db.execute(
            """INSERT INTO chapters (id, novel_id, chapter_num, file_path)
               VALUES (?, ?, ?, ?)""",
            ("chapter_sjc_0001", "novel_sjc", 1, "test.md"),
        )
        cur = schema.db.execute(
            """INSERT INTO sync_jobs (term_id, old_value, new_value) VALUES (?, ?, ?)""",
            ("term_sjc", "old", "new"),
        )
        job_id = cur.lastrowid
        schema.db.execute(
            """INSERT INTO sync_job_chapters (job_id, chapter_id) VALUES (?, ?)""",
            (job_id, "chapter_sjc_0001"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            schema.db.execute(
                """INSERT INTO sync_job_chapters (job_id, chapter_id) VALUES (?, ?)""",
                (job_id, "chapter_sjc_0001"),
            )

    def test_cascade_delete_novel(self, schema):
        schema.db.execute(
            "INSERT INTO novels (id, name, source_language) VALUES (?, ?, ?)",
            ("novel_cascade", "Cascade Test", "chinese"),
        )
        schema.db.execute(
            """INSERT INTO glossary_terms (id, novel_id, source_term, target_term, canonical_form)
               VALUES (?, ?, ?, ?, ?)""",
            ("term_cascade", "novel_cascade", "源", "မြစ်", "源"),
        )
        schema.db.execute("DELETE FROM novels WHERE id = ?", ("novel_cascade",))
        assert not schema.db.row_exists("SELECT 1 FROM glossary_terms WHERE id = ?", ("term_cascade",))


class TestIndexes:
    def test_glossary_novel_index_exists(self, schema):
        rows = schema.db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_glossary_novel'"
        )
        assert len(rows) == 1

    def test_audit_log_indexes_exist(self, schema):
        rows = schema.db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_audit%'"
        )
        assert len(rows) >= 2


class TestTableCounts:
    def test_empty_table_count_is_zero(self, schema):
        for table in EXPECTED_TABLES:
            assert schema.get_table_count(table) == 0

    def test_count_after_insert(self, schema):
        schema.db.execute(
            "INSERT INTO novels (id, name, source_language) VALUES (?, ?, ?)",
            ("novel_count", "Count Test", "chinese"),
        )
        assert schema.get_table_count("novels") == 1
