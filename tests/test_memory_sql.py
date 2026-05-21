"""
Tests for MemoryManager SQL backend integration.
"""

import pytest
from src.memory.memory_manager import MemoryManager


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_memory.db")


class TestMemoryManagerSQLBackend:
    def test_init_with_sql(self, db_path):
        mm = MemoryManager(novel_name="test-novel", use_sql=True, db_path=db_path)
        assert mm.use_sql is True
        assert mm.novel_id == "novel_test-novel"
        assert mm.novel_repo.exists("novel_test-novel")
        mm.close()

    def test_add_term_sql(self, db_path):
        mm = MemoryManager(novel_name="test-novel", use_sql=True, db_path=db_path)
        result = mm.add_term("道", "လမ်း", "concept", 1)
        assert result is True
        term = mm.get_term("道")
        assert term == "လမ်း"
        mm.close()

    def test_get_term_not_found(self, db_path):
        mm = MemoryManager(novel_name="test-novel", use_sql=True, db_path=db_path)
        result = mm.get_term("nonexistent")
        assert result is None
        mm.close()

    def test_duplicate_term_rejected(self, db_path):
        mm = MemoryManager(novel_name="test-novel", use_sql=True, db_path=db_path)
        mm.add_term("Unique", "တစ်ခု", "general")
        result = mm.add_term("Unique", "တစ်ခု", "general")
        assert result is False
        mm.close()

    def test_non_myanmar_target_rejected(self, db_path):
        mm = MemoryManager(novel_name="test-novel", use_sql=True, db_path=db_path)
        result = mm.add_term("Test", "EnglishOnly", "general")
        assert result is False
        mm.close()

    def test_get_all_terms(self, db_path):
        mm = MemoryManager(novel_name="test-novel", use_sql=True, db_path=db_path)
        mm.add_term("လမ်း", "လမ်းကြောင်း", "general")
        mm.add_term("မြစ်", "မြစ်ကြီး", "general")
        # Use get_term to verify our specific terms exist (get_all_terms has limit=100)
        assert mm.get_term("လမ်း") == "လမ်းကြောင်း"
        assert mm.get_term("မြစ်") == "မြစ်ကြီး"
        # get_all_terms returns at least our 2 terms (may include synced globals)
        terms = mm.get_all_terms()
        assert len(terms) >= 2
        mm.close()

    def test_get_glossary_for_prompt(self, db_path):
        mm = MemoryManager(novel_name="test-novel", use_sql=True, db_path=db_path)
        mm.add_term("Word", "စာ", "general")
        # Need to approve the term for it to appear in prompt
        term = mm.glossary_repo.get_term_by_source(mm.novel_id, "Word")
        if term:
            mm.glossary_repo.update_term(term["id"], status="approved")
        prompt = mm.get_glossary_for_prompt(limit=10)
        assert "GLOSSARY" in prompt
        mm.close()

    def test_update_chapter_context(self, db_path):
        mm = MemoryManager(novel_name="test-novel", use_sql=True, db_path=db_path)
        mm.update_chapter_context(1, "Translated content here", "Summary")
        ch = mm.chapter_repo.get_by_id("chapter_novel_test-novel_0001")
        assert ch is not None
        assert ch["translation_status"] == "translated"
        snaps = mm.context_repo.get_snapshots_for_chapter("chapter_novel_test-novel_0001")
        assert len(snaps) == 1
        mm.close()

    def test_save_memory_is_noop_for_sql(self, db_path):
        mm = MemoryManager(novel_name="test-novel", use_sql=True, db_path=db_path)
        mm.save_memory()  # Should not raise or error
        mm.close()

    def test_sql_json_parity_add_term(self, db_path, tmp_path):
        """SQL and JSON backends should behave similarly for add_term."""
        import json
        # Use temp directory for JSON backend to avoid persistence issues
        json_glossary_dir = tmp_path / "json_parity_test" / "glossary"
        json_glossary_dir.mkdir(parents=True)
        
        # Create empty glossary file
        glossary_file = json_glossary_dir / "glossary.json"
        with open(glossary_file, 'w', encoding='utf-8-sig') as f:
            json.dump({"version": "1.0", "terms": [], "total_terms": 0}, f)
        context_file = json_glossary_dir / "context_memory.json"
        with open(context_file, 'w', encoding='utf-8-sig') as f:
            json.dump({"current_chapter": 0, "summary": ""}, f)
        pending_file = json_glossary_dir / "glossary_pending.json"
        with open(pending_file, 'w', encoding='utf-8-sig') as f:
            json.dump({"pending_terms": []}, f)
        
        mm_sql = MemoryManager(novel_name="sql-test", use_sql=True, db_path=db_path)
        mm_json = MemoryManager(
            glossary_path=str(glossary_file),
            context_path=str(context_file),
            use_sql=False
        )
        mm_json.pending_path = str(pending_file)

        sql_result = mm_sql.add_term("道", "လမ်း", "concept")
        json_result = mm_json.add_term("道", "လမ်း", "concept")

        assert sql_result == json_result  # Both should succeed

        mm_sql.close()

    def test_sql_json_parity_get_term(self, db_path):
        """get_term should return same value for both backends."""
        mm_sql = MemoryManager(novel_name="sql-test2", use_sql=True, db_path=db_path)
        mm_json = MemoryManager(novel_name="json-test2", use_sql=False)

        mm_sql.add_term("气", "စွမ်းအင်", "concept")
        mm_json.add_term("气", "စွမ်းအင်", "concept")

        sql_term = mm_sql.get_term("气")
        json_term = mm_json.get_term("气")

        assert sql_term == json_term == "စွမ်းအင်"

        mm_sql.close()
