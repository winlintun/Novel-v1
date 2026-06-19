"""
Tests for all repository CRUD operations.
"""

import pytest
import os
import tempfile
from pathlib import Path
from src.db.connection import DatabaseConnection
from src.db.schema import SchemaManager
from src.db.repositories.novel_repo import NovelRepository
from src.db.repositories.glossary_repo import GlossaryRepository
from src.db.repositories.chapter_repo import ChapterRepository
from src.db.repositories.context_repo import ContextRepository
from src.db.repositories.sync_repo import SyncRepository


@pytest.fixture
def db():
    # Close the temp file's OS handle before opening the DB so Windows can
    # unlink it during teardown (WinError 32 otherwise).
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = DatabaseConnection(path)
    yield conn
    conn.close()
    for p in (path, path + "-wal", path + "-shm"):
        Path(p).unlink(missing_ok=True)


@pytest.fixture
def schema(db):
    sm = SchemaManager(db)
    sm.create_all()
    return sm


@pytest.fixture
def repos(db, schema):
    return {
        "novel": NovelRepository(db),
        "glossary": GlossaryRepository(db),
        "chapter": ChapterRepository(db),
        "context": ContextRepository(db),
        "sync": SyncRepository(db),
    }


class TestNovelRepository:
    def test_create_novel(self, repos):
        novel = repos["novel"].create("novel_test", "Test Novel", "chinese")
        assert novel["id"] == "novel_test"
        assert novel["name"] == "Test Novel"

    def test_get_by_id(self, repos):
        repos["novel"].create("novel_get", "Get Test", "english")
        result = repos["novel"].get_by_id("novel_get")
        assert result is not None
        assert result["name"] == "Get Test"

    def test_get_by_id_not_found(self, repos):
        result = repos["novel"].get_by_id("nonexistent")
        assert result is None

    def test_get_all(self, repos):
        repos["novel"].create("novel_a", "A", "chinese")
        repos["novel"].create("novel_b", "B", "english")
        results = repos["novel"].get_all()
        assert len(results) == 2

    def test_update(self, repos):
        repos["novel"].create("novel_upd", "Original", "chinese")
        updated = repos["novel"].update("novel_upd", name="Updated", source_language="japanese")
        assert updated["name"] == "Updated"
        assert updated["source_language"] == "japanese"

    def test_delete(self, repos):
        repos["novel"].create("novel_del", "Delete", "chinese")
        assert repos["novel"].exists("novel_del")
        repos["novel"].delete("novel_del")
        assert not repos["novel"].exists("novel_del")

    def test_exists(self, repos):
        repos["novel"].create("novel_exists", "Exists", "chinese")
        assert repos["novel"].exists("novel_exists") is True
        assert repos["novel"].exists("novel_notexists") is False


class TestGlossaryRepository:
    @pytest.fixture(autouse=True)
    def setup_novel(self, repos):
        repos["novel"].create("novel_glossary", "Glossary Test", "chinese")

    def test_add_term(self, repos):
        term = repos["glossary"].add_term("novel_glossary", "道", "လမ်း", "concept")
        assert term["source_term"] == "道"
        assert term["target_term"] == "လမ်း"

    def test_get_term_by_source(self, repos):
        repos["glossary"].add_term("novel_glossary", "气", "စွမ်းအင်", "concept")
        result = repos["glossary"].get_term_by_source("novel_glossary", "气")
        assert result is not None
        assert result["target_term"] == "စွမ်းအင်"

    def test_get_terms_by_novel(self, repos):
        repos["glossary"].add_term("novel_glossary", "A", "အေ", "general")
        repos["glossary"].add_term("novel_glossary", "B", "ဘီ", "general")
        terms = repos["glossary"].get_terms_by_novel("novel_glossary")
        assert len(terms) == 2

    def test_update_term(self, repos):
        term = repos["glossary"].add_term("novel_glossary", "Change", "အောက်", "general")
        updated = repos["glossary"].update_term(term["id"], target_term="အပေါ်", status="approved")
        assert updated["target_term"] == "အပေါ်"
        assert updated["status"] == "approved"

    def test_search_terms(self, repos):
        repos["glossary"].add_term("novel_glossary", "TestWord", "စမ်းသပ်", "general")
        results = repos["glossary"].search_terms("novel_glossary", "Test")
        assert len(results) == 1

    def test_add_variant(self, repos):
        term = repos["glossary"].add_term("novel_glossary", "Variant", "မူ", "general")
        var_id = repos["glossary"].add_variant(term["id"], "変", "exact")
        assert var_id > 0
        variants = repos["glossary"].get_variants(term["id"])
        assert len(variants) == 1


class TestChapterRepository:
    @pytest.fixture(autouse=True)
    def setup_novel(self, repos):
        repos["novel"].create("novel_chapter", "Chapter Test", "chinese")

    def test_create(self, repos):
        ch = repos["chapter"].create("novel_chapter", 1, "chapter_001.md")
        assert ch["chapter_num"] == 1
        assert ch["file_path"] == "chapter_001.md"

    def test_get_by_number(self, repos):
        repos["chapter"].create("novel_chapter", 5, "ch5.md")
        result = repos["chapter"].get_by_number("novel_chapter", 5)
        assert result is not None
        assert result["chapter_num"] == 5

    def test_update_status(self, repos):
        ch = repos["chapter"].create("novel_chapter", 2, "ch2.md")
        updated = repos["chapter"].update_status(ch["id"], "reviewed")
        assert updated["translation_status"] == "reviewed"

    def test_create_version(self, repos):
        ch = repos["chapter"].create("novel_chapter", 3, "ch3.md")
        v1 = repos["chapter"].create_version(ch["id"], "backup/v1.md", "initial")
        assert v1["version_num"] == 1
        v2 = repos["chapter"].create_version(ch["id"], "backup/v2.md", "edit")
        assert v2["version_num"] == 2

    def test_get_all_versions(self, repos):
        ch = repos["chapter"].create("novel_chapter", 4, "ch4.md")
        repos["chapter"].create_version(ch["id"], "v1.md", "r1")
        repos["chapter"].create_version(ch["id"], "v2.md", "r2")
        versions = repos["chapter"].get_all_versions(ch["id"])
        assert len(versions) == 2


class TestContextRepository:
    @pytest.fixture(autouse=True)
    def setup_data(self, repos):
        repos["novel"].create("novel_ctx", "Context Test", "chinese")
        repos["chapter"].create("novel_ctx", 1, "ch1.md", paragraph_count=10)

    def test_create_snapshot(self, repos):
        snap = repos["context"].create_snapshot("chapter_novel_ctx_0001", '{"active_chars":[]}')
        assert snap is not None
        assert snap["chapter_id"] == "chapter_novel_ctx_0001"

    def test_get_snapshots_for_chapter(self, repos):
        repos["context"].create_snapshot("chapter_novel_ctx_0001", '{"v":1}')
        repos["context"].create_snapshot("chapter_novel_ctx_0001", '{"v":2}')
        snaps = repos["context"].get_snapshots_for_chapter("chapter_novel_ctx_0001")
        assert len(snaps) == 2

    def test_record_usage(self, repos):
        term = repos["glossary"].add_term("novel_ctx", "Usage", "အသုံး", "general")
        usage_id = repos["context"].record_usage(term["id"], "chapter_novel_ctx_0001", 5, "Variant")
        assert usage_id > 0

    def test_get_usage_by_term(self, repos):
        term = repos["glossary"].add_term("novel_ctx", "Freq", "ဖြစ်နေသည်", "general")
        repos["context"].record_usage(term["id"], "chapter_novel_ctx_0001", 1)
        repos["context"].record_usage(term["id"], "chapter_novel_ctx_0001", 3)
        usage = repos["context"].get_usage_by_term(term["id"])
        assert len(usage) == 2


class TestSyncRepository:
    @pytest.fixture(autouse=True)
    def setup_data(self, repos):
        repos["novel"].create("novel_sync", "Sync Test", "chinese")
        repos["glossary"].add_term("novel_sync", "SyncTerm", "သီးသန့်", "general")
        repos["chapter"].create("novel_sync", 1, "ch1.md")

    def test_create_job(self, repos):
        term = repos["glossary"].get_term_by_source("novel_sync", "SyncTerm")
        job = repos["sync"].create_job(term["id"], "old_val", "new_val")
        assert job["old_value"] == "old_val"
        assert job["new_value"] == "new_val"

    def test_get_pending_jobs(self, repos):
        term = repos["glossary"].get_term_by_source("novel_sync", "SyncTerm")
        repos["sync"].create_job(term["id"], "a", "b")
        repos["sync"].create_job(term["id"], "c", "d")
        pending = repos["sync"].get_pending_jobs()
        assert len(pending) == 2

    def test_update_job_status(self, repos):
        term = repos["glossary"].get_term_by_source("novel_sync", "SyncTerm")
        job = repos["sync"].create_job(term["id"], "x", "y")
        updated = repos["sync"].update_job_status(job["id"], "applied")
        assert updated["status"] == "applied"
        assert updated["applied_at"] is not None

    def test_add_job_chapter(self, repos):
        term = repos["glossary"].get_term_by_source("novel_sync", "SyncTerm")
        job = repos["sync"].create_job(term["id"], "o", "n")
        repos["sync"].add_job_chapter(job["id"], "chapter_novel_sync_0001")
        chapters = repos["sync"].get_job_chapters(job["id"])
        assert len(chapters) == 1

    def test_is_job_complete(self, repos):
        term = repos["glossary"].get_term_by_source("novel_sync", "SyncTerm")
        job = repos["sync"].create_job(term["id"], "o", "n")
        repos["sync"].add_job_chapter(job["id"], "chapter_novel_sync_0001")
        assert not repos["sync"].is_job_complete(job["id"])
        repos["sync"].update_chapter_status(job["id"], "chapter_novel_sync_0001", "applied")
        assert repos["sync"].is_job_complete(job["id"])

    def test_log_action(self, repos):
        log_id = repos["sync"].log_action("glossary_terms", "term_001", "update", '{"old":1}', '{"new":2}', "cli")
        assert log_id > 0
        logs = repos["sync"].get_audit_log(table_name="glossary_terms")
        assert len(logs) == 1
        assert logs[0]["action"] == "update"
