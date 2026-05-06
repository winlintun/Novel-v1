"""
Tests for VersionManager and versioning system.
"""

import pytest
from pathlib import Path

from src.db.connection import DatabaseConnection
from src.db.schema import SchemaManager
from src.memory.version_manager import VersionManager


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(str(db_path))
    schema = SchemaManager(db)
    schema.create_all()
    yield db
    db.close()


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def version_manager(temp_db, temp_output_dir):
    """Create a VersionManager instance."""
    return VersionManager(temp_db, temp_output_dir)


class TestChapterVersioning:
    """Test chapter version snapshot and rollback."""

    def test_snapshot_chapter_creates_version(self, version_manager, temp_output_dir):
        """Test that snapshot_chapter creates a version record."""
        # Create a test chapter file
        novel_dir = temp_output_dir / "test-novel"
        novel_dir.mkdir()
        chapter_file = novel_dir / "test-novel_chapter_0001.mm.md"
        chapter_file.write_text("# အခန်း ၁\n\nစမ်းသပ်စာသား။", encoding="utf-8-sig")

        # Create snapshot
        version = version_manager.snapshot_chapter("test-novel", 1, reason="test")

        assert version is not None
        assert version["version_num"] == 1
        assert "test" in version["reason"]
        assert Path(version["file_snapshot_path"]).exists()

    def test_list_versions_returns_all_versions(self, version_manager, temp_output_dir):
        """Test listing versions for a chapter."""
        # Create chapter file and multiple versions
        novel_dir = temp_output_dir / "test-novel"
        novel_dir.mkdir()
        chapter_file = novel_dir / "test-novel_chapter_0001.mm.md"
        chapter_file.write_text("# အခန်း ၁\n\nVersion 1", encoding="utf-8-sig")

        version_manager.snapshot_chapter("test-novel", 1, reason="v1")
        chapter_file.write_text("# အခန်း ၁\n\nVersion 2", encoding="utf-8-sig")
        version_manager.snapshot_chapter("test-novel", 1, reason="v2")

        versions = version_manager.list_versions("test-novel", 1)

        assert len(versions) == 2
        assert versions[0]["version_num"] == 1
        assert versions[1]["version_num"] == 2

    def test_rollback_restores_version(self, version_manager, temp_output_dir):
        """Test rolling back to a previous version."""
        # Create chapter with multiple versions
        novel_dir = temp_output_dir / "test-novel"
        novel_dir.mkdir()
        chapter_file = novel_dir / "test-novel_chapter_0001.mm.md"
        
        chapter_file.write_text("# အခန်း ၁\n\nမူလစာသား", encoding="utf-8-sig")
        version_manager.snapshot_chapter("test-novel", 1, reason="original")
        
        chapter_file.write_text("# အခန်း ၁\n\nပြောင်းလဲသည့်စာသား", encoding="utf-8-sig")

        # Rollback to version 1
        result = version_manager.rollback_chapter("test-novel", 1, 1)

        assert result is not None
        restored_text = result.read_text(encoding="utf-8-sig")
        assert "မူလစာသား" in restored_text
        assert "ပြောင်းလဲသည့်စာသား" not in restored_text

    def test_diff_versions(self, version_manager, temp_output_dir):
        """Test generating diff between versions."""
        # Create chapter with different content
        novel_dir = temp_output_dir / "test-novel"
        novel_dir.mkdir()
        chapter_file = novel_dir / "test-novel_chapter_0001.mm.md"

        chapter_file.write_text("# အခန်း ၁\n\nစာကြောင်း အ\nစာကြောင်း ဘီ", encoding="utf-8-sig")
        version_manager.snapshot_chapter("test-novel", 1, reason="v1")

        chapter_file.write_text("# အခန်း ၁\n\nစာကြောင်း အ\nစာကြောင်း စီ", encoding="utf-8-sig")
        version_manager.snapshot_chapter("test-novel", 1, reason="v2")

        diff = version_manager.diff_versions("test-novel", 1, 1, 2)

        assert diff is not None
        assert "ဘီ" in diff  # Removed
        assert "စီ" in diff  # Added


class TestGlossarySync:
    """Test glossary change sync jobs."""

    def test_preview_glossary_change(self, version_manager, temp_db, temp_output_dir):
        """Test previewing which chapters would be affected."""
        # Setup: create novel, term, and chapter with usage
        temp_db.execute(
            "INSERT INTO novels (id, name) VALUES (?, ?)",
            ("test-novel", "test-novel")
        )
        temp_db.execute(
            """INSERT INTO glossary_terms 
               (id, novel_id, source_term, target_term, canonical_form, category)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("term_1", "test-novel", "测试", "စမ်းသပ်", "စမ်းသပ်", "general")
        )
        temp_db.execute(
            """INSERT INTO chapters (id, novel_id, chapter_num, file_path)
               VALUES (?, ?, ?, ?)""",
            ("ch_1", "test-novel", 1, "/path/to/ch1.md")
        )
        temp_db.execute(
            """INSERT INTO term_usage (term_id, chapter_id, paragraph_idx, confidence)
               VALUES (?, ?, ?, ?)""",
            ("term_1", "ch_1", 1, 0.9)
        )

        # Create chapter file with the term
        novel_dir = temp_output_dir / "test-novel"
        novel_dir.mkdir()
        chapter_file = novel_dir / "test-novel_chapter_0001.mm.md"
        chapter_file.write_text("စမ်းသပ်စာသား", encoding="utf-8-sig")

        preview = version_manager.preview_glossary_change("test-novel", "term_1", "အသစ်")

        assert preview["term_id"] == "term_1"
        assert preview["old_value"] == "စမ်းသပ်"
        assert preview["new_value"] == "အသစ်"
        assert len(preview["affected_chapters"]) > 0

    def test_create_sync_job(self, version_manager, temp_db, temp_output_dir):
        """Test creating a sync job."""
        # Setup
        temp_db.execute(
            "INSERT INTO novels (id, name) VALUES (?, ?)",
            ("test-novel", "test-novel")
        )
        temp_db.execute(
            """INSERT INTO glossary_terms 
               (id, novel_id, source_term, target_term, canonical_form, category)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("term_1", "test-novel", "测试", "စမ်းသပ်", "စမ်းသပ်", "general")
        )

        job = version_manager.create_sync_job("test-novel", "term_1", "အသစ်")

        assert job is not None
        assert job["term_id"] == "term_1"
        assert job["old_value"] == "စမ်းသပ်"
        assert job["new_value"] == "အသစ်"
        assert job["status"] == "pending_review"

    def test_execute_sync_job_dry_run(self, version_manager, temp_db, temp_output_dir):
        """Test dry-run execution of sync job."""
        # Setup
        temp_db.execute(
            "INSERT INTO novels (id, name) VALUES (?, ?)",
            ("test-novel", "test-novel")
        )
        temp_db.execute(
            """INSERT INTO glossary_terms 
               (id, novel_id, source_term, target_term, canonical_form, category)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("term_1", "test-novel", "测试", "OLD_TERM", "OLD_TERM", "general")
        )
        temp_db.execute(
            """INSERT INTO chapters (id, novel_id, chapter_num, file_path)
               VALUES (?, ?, ?, ?)""",
            ("ch_1", "test-novel", 1, "/path/to/ch1.md")
        )
        
        # Create chapter file with old term
        novel_dir = temp_output_dir / "test-novel"
        novel_dir.mkdir()
        chapter_file = novel_dir / "test-novel_chapter_0001.mm.md"
        chapter_file.write_text("This contains OLD_TERM to replace.", encoding="utf-8-sig")

        job = version_manager.create_sync_job("test-novel", "term_1", "NEW_TERM", chapter_nums=[1])

        # Execute dry run
        result = version_manager.execute_sync_job(job["id"], dry_run=True)

        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["replacements_total"] == 1

        # Verify file was NOT changed
        content = chapter_file.read_text(encoding="utf-8-sig")
        assert "OLD_TERM" in content

    def test_execute_sync_job_apply(self, version_manager, temp_db, temp_output_dir):
        """Test actual execution of sync job."""
        # Setup
        temp_db.execute(
            "INSERT INTO novels (id, name) VALUES (?, ?)",
            ("test-novel", "test-novel")
        )
        temp_db.execute(
            """INSERT INTO glossary_terms 
               (id, novel_id, source_term, target_term, canonical_form, category)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("term_1", "test-novel", "测试", "OLD_TERM", "OLD_TERM", "general")
        )
        temp_db.execute(
            """INSERT INTO chapters (id, novel_id, chapter_num, file_path)
               VALUES (?, ?, ?, ?)""",
            ("ch_1", "test-novel", 1, "/path/to/ch1.md")
        )
        
        # Create chapter file
        novel_dir = temp_output_dir / "test-novel"
        novel_dir.mkdir()
        chapter_file = novel_dir / "test-novel_chapter_0001.mm.md"
        chapter_file.write_text("This contains OLD_TERM to replace.", encoding="utf-8-sig")

        job = version_manager.create_sync_job("test-novel", "term_1", "NEW_TERM", chapter_nums=[1])

        # Execute for real
        result = version_manager.execute_sync_job(job["id"], dry_run=False)

        assert result["success"] is True
        assert result["dry_run"] is False
        assert result["chapters_updated"] == 1

        # Verify file WAS changed
        content = chapter_file.read_text(encoding="utf-8-sig")
        assert "NEW_TERM" in content
        assert "OLD_TERM" not in content


class TestAuditLog:
    """Test audit logging functionality."""

    def test_audit_log_entries_created(self, version_manager, temp_db, temp_output_dir):
        """Test that operations create audit log entries."""
        # Create chapter and snapshot
        novel_dir = temp_output_dir / "test-novel"
        novel_dir.mkdir()
        chapter_file = novel_dir / "test-novel_chapter_0001.mm.md"
        chapter_file.write_text("Content", encoding="utf-8-sig")

        version_manager.snapshot_chapter("test-novel", 1, reason="test")

        # Check audit log
        logs = version_manager.get_audit_log(novel_name="test-novel")

        assert len(logs) > 0
        assert logs[0]["action"] == "version_created"

    def test_list_sync_jobs(self, version_manager, temp_db):
        """Test listing sync jobs."""
        # Setup
        temp_db.execute(
            "INSERT INTO novels (id, name) VALUES (?, ?)",
            ("test-novel", "test-novel")
        )
        temp_db.execute(
            """INSERT INTO glossary_terms 
               (id, novel_id, source_term, target_term, canonical_form, category)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("term_1", "test-novel", "测试", "OLD", "OLD", "general")
        )

        # Create multiple jobs
        version_manager.create_sync_job("test-novel", "term_1", "NEW1")
        version_manager.create_sync_job("test-novel", "term_1", "NEW2")

        jobs = version_manager.list_sync_jobs(novel_name="test-novel")

        assert len(jobs) == 2


class TestErrorHandling:
    """Test error handling edge cases."""

    def test_snapshot_nonexistent_chapter(self, version_manager):
        """Test snapshotting a chapter that doesn't exist."""
        result = version_manager.snapshot_chapter("nonexistent", 999)
        assert result is None

    def test_rollback_nonexistent_version(self, version_manager, temp_output_dir):
        """Test rolling back to a version that doesn't exist."""
        # Setup minimal structure
        novel_dir = temp_output_dir / "test-novel"
        novel_dir.mkdir()
        chapter_file = novel_dir / "test-novel_chapter_0001.mm.md"
        chapter_file.write_text("Content", encoding="utf-8-sig")

        result = version_manager.rollback_chapter("test-novel", 1, 999)
        assert result is None

    def test_preview_nonexistent_term(self, version_manager):
        """Test previewing a change for a term that doesn't exist."""
        preview = version_manager.preview_glossary_change("test-novel", "nonexistent", "value")
        assert "error" in preview
