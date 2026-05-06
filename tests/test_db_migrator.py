"""
Tests for JSON-to-SQLite migration.
"""

import pytest
import json
import tempfile
from pathlib import Path
from src.db.connection import DatabaseConnection
from src.db.migrator import JsonToSqlMigrator


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        conn = DatabaseConnection(f.name)
        yield conn
        conn.close()
        Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def novel_dir(tmp_path):
    """Create a mock novel output directory with JSON files."""
    novel_slug = "test-novel"
    glossary_dir = tmp_path / "data" / "output" / novel_slug / "glossary"
    glossary_dir.mkdir(parents=True)

    glossary = {
        "version": "1.0",
        "terms": [
            {"id": "term_001", "source": "道", "target": "လမ်း", "category": "concept", "verified": True},
            {"id": "term_002", "source": "气", "target": "စွမ်းအင်", "category": "concept", "verified": False},
            {"id": "term_003", "source": "方源", "target": "ဖန့်ယွမ်", "category": "character", "verified": True},
        ],
        "total_terms": 3,
    }
    with open(glossary_dir / "glossary.json", "w", encoding="utf-8-sig") as f:
        json.dump(glossary, f, ensure_ascii=False)

    pending = {
        "pending_terms": [
            {"source": "蛊", "target": "ပိုးကောင်", "category": "item", "status": "pending"},
        ]
    }
    with open(glossary_dir / "glossary_pending.json", "w", encoding="utf-8-sig") as f:
        json.dump(pending, f, ensure_ascii=False)

    context = {
        "current_chapter": 3,
        "last_translated_chapter": 2,
        "summary": "Chapter 3 summary",
        "active_characters": {"方源": {"target": "ဖန့်ယွမ်"}},
        "recent_events": [{"chapter": 3, "description": "Event"}],
        "paragraph_buffer": [],
    }
    with open(glossary_dir / "context_memory.json", "w", encoding="utf-8-sig") as f:
        json.dump(context, f, ensure_ascii=False)

    output_dir = tmp_path / "data" / "output" / novel_slug
    ch1 = output_dir / "test-novel_chapter_0001.mm.md"
    ch1.write_text("# Chapter 1\nContent", encoding="utf-8-sig")
    ch2 = output_dir / "test-novel_chapter_0002.mm.md"
    ch2.write_text("# Chapter 2\nContent", encoding="utf-8-sig")

    original_cwd = Path.cwd()
    import os
    os.chdir(tmp_path)

    yield novel_slug

    os.chdir(original_cwd)


class TestJsonToSqlMigrator:
    def test_migrate_glossary_terms(self, db, novel_dir):
        migrator = JsonToSqlMigrator(db, novel_dir)
        summary = migrator.migrate(backup_dir="backups/test")
        assert summary["glossary_terms"] == 3

    def test_migrate_pending_terms(self, db, novel_dir):
        migrator = JsonToSqlMigrator(db, novel_dir)
        summary = migrator.migrate(backup_dir="backups/test")
        assert summary["pending_terms"] == 1

    def test_migrate_chapters(self, db, novel_dir):
        migrator = JsonToSqlMigrator(db, novel_dir)
        summary = migrator.migrate(backup_dir="backups/test")
        assert summary["chapters"] == 2

    def test_migrate_context_snapshot(self, db, novel_dir):
        migrator = JsonToSqlMigrator(db, novel_dir)
        summary = migrator.migrate(backup_dir="backups/test")
        assert summary["context_snapshots"] == 1

    def test_migrate_creates_backup(self, db, novel_dir, tmp_path):
        migrator = JsonToSqlMigrator(db, novel_dir)
        summary = migrator.migrate(backup_dir=str(tmp_path / "backups" / "test"))
        backup_path = Path(summary["backup_dir"])
        assert backup_path.exists()
        assert (backup_path / "glossary.json").exists()
        assert (backup_path / "glossary_pending.json").exists()

    def test_migrate_creates_novel_record(self, db, novel_dir):
        migrator = JsonToSqlMigrator(db, novel_dir)
        migrator.migrate(backup_dir="backups/test")
        novel = db.fetchone("SELECT * FROM novels WHERE id = ?", (f"novel_{novel_dir}",))
        assert novel is not None
        assert novel["name"] == novel_dir

    def test_migrate_idempotent(self, db, novel_dir):
        migrator = JsonToSqlMigrator(db, novel_dir)
        summary1 = migrator.migrate(backup_dir="backups/test")
        summary2 = migrator.migrate(backup_dir="backups/test2")
        assert summary1["glossary_terms"] == summary2["glossary_terms"]

    def test_migrate_empty_directory(self, db, tmp_path):
        novel_slug = "empty-novel"
        glossary_dir = tmp_path / "data" / "output" / novel_slug / "glossary"
        glossary_dir.mkdir(parents=True)
        output_dir = tmp_path / "data" / "output" / novel_slug

        original_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        migrator = JsonToSqlMigrator(db, novel_slug)
        summary = migrator.migrate(backup_dir="backups/empty")

        assert summary["glossary_terms"] == 0
        assert summary["pending_terms"] == 0
        assert summary["chapters"] == 0
        assert summary["context_snapshots"] == 0

        os.chdir(original_cwd)
