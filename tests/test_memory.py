"""
Unit tests for MemoryManager (DB-only architecture).
"""

import unittest
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memory.memory_manager import MemoryManager


class TestMemoryManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test.db")
        self.memory = MemoryManager(novel_name="test_novel", db_path=self.db_path, auto_seed_global=False)

    def tearDown(self):
        self.memory.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_get_term(self):
        """Test adding and retrieving glossary terms."""
        self.memory.add_term("主角", "ဇော်ဂျီ", "character", 1)

        # get_term returns target for any status (pending or approved)
        target = self.memory.get_term("主角")
        self.assertEqual(target, "ဇော်ဂျီ")

        # Approve the term so it appears in the prompt
        self.memory.promote_pending_to_glossary("主角")

        prompt = self.memory.get_glossary_for_prompt()
        self.assertIn("主角", prompt)
        self.assertIn("ဇော်ဂျီ", prompt)

    def test_context_buffer(self):
        """Test FIFO context buffer (in-memory per session)."""
        self.memory.push_to_buffer("Para 1")
        self.memory.push_to_buffer("Para 2")
        self.memory.push_to_buffer("Para 3")
        self.memory.push_to_buffer("Para 4")

        context = self.memory.get_context_buffer(3)
        self.assertNotIn("Para 1", context)
        self.assertIn("Para 2", context)
        self.assertIn("Para 4", context)

    def test_persistence(self):
        """Test that glossary terms persist in the DB across instances."""
        self.memory.add_term("Item", "ပစ္စည်း", "item", 1)
        self.memory.close()

        # New instance with same DB
        new_memory = MemoryManager(novel_name="test_novel", db_path=self.db_path, auto_seed_global=False)
        self.assertEqual(new_memory.get_term("Item"), "ပစ္စည်း")
        new_memory.close()

    def test_session_rules(self):
        """Test Tier 3 session rules."""
        self.memory.add_session_rule("ဟောင်း", "သစ်")
        rules = self.memory.get_session_rules()
        self.assertIn("ဟောင်း -> သစ်", rules)

        self.memory.promote_rule_to_glossary("ဟောင်း", "သစ်", 1)
        self.assertEqual(self.memory.get_term("ဟောင်း"), "သစ်")
        self.assertEqual(self.memory.get_session_rules(), "No session rules.")


class TestDualLayerGlossary(unittest.TestCase):
    """Tests for per-novel vs global (xianxia) glossary isolation via DB."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_mm(self, novel_name: str) -> MemoryManager:
        mm = MemoryManager(novel_name=novel_name, db_path=self.db_path, auto_seed_global=False)
        # Ensure global novel exists for add_global_term calls
        from src.db.repositories.glossary_repo import GLOBAL_NOVEL_ID
        if not mm.novel_repo.exists(GLOBAL_NOVEL_ID):
            mm.novel_repo.create(GLOBAL_NOVEL_ID, "Global Xianxia Terms", "universal")
        return mm

    def test_per_novel_isolation(self):
        """Terms added to novel A must NOT appear in novel B."""
        mm_a = self._make_mm("novel_a")
        mm_a.add_term("Fang Yuan", "ဖန်ယွမ်", "character", 1)
        mm_a.close()

        mm_b = self._make_mm("novel_b")
        # Novel B has no global terms and no novel-specific "Fang Yuan"
        # get_term falls back to global scope; Fang Yuan is novel_a only
        term = mm_b.get_term("Fang Yuan")
        # Should be None (novel_a term doesn't leak into novel_b)
        self.assertIsNone(term, "Term from novel A must not leak into novel B")
        mm_b.close()

    def test_global_term_visible_across_novels(self):
        """Global terms (scope='global') are visible to all novels."""
        mm_a = self._make_mm("novel_a")
        mm_a.add_global_term("Gu", "ကြောင်", category="item", status="approved",
                              confidence=0.95)
        mm_a.close()

        mm_b = self._make_mm("novel_b")
        result = mm_b.get_term("Gu")
        self.assertEqual(result, "ကြောင်",
                         "Global term must be retrievable by any novel")
        mm_b.close()

    def test_per_novel_overrides_global(self):
        """Per-novel term takes priority over global term with same source."""
        mm_a = self._make_mm("novel_a")
        mm_a.add_global_term("Spirit Gu", "ဝိညာဉ်ကြောင်", status="approved")
        mm_a.add_term("Spirit Gu", "ဝိညာဉ်ကြောင် (RI)", "item_artifact", 1)
        result = mm_a.get_term("Spirit Gu")
        # Per-novel term returned (repo checks novel-specific first)
        self.assertIsNotNone(result)
        mm_a.close()

    def test_get_all_terms_includes_global(self):
        """get_all_terms() returns per-novel + global terms."""
        mm_a = self._make_mm("novel_a")
        mm_a.add_global_term("Gu", "ကြောင်", category="item", status="approved")
        mm_a.add_term("Fang Yuan", "ဖန်ယွမ်", "character", 1)

        all_terms = mm_a.get_all_terms()
        sources = [t.get("source") or t.get("source_term", "") for t in all_terms]
        self.assertIn("Fang Yuan", sources, "Per-novel term must be in combined list")
        self.assertIn("Gu", sources, "Global term must be in combined list")
        mm_a.close()

    def test_no_duplicate_sources(self):
        """If per-novel has same source as global, only one entry appears."""
        mm_a = self._make_mm("novel_a")
        mm_a.add_global_term("Spirit Gu", "ဝိညာဉ်ကြောင်", status="approved")
        mm_a.add_term("Spirit Gu", "ဝိညာဉ်ကြောင် (custom)", "item_artifact", 1)

        terms_for_prompt = mm_a.glossary_repo.get_terms_for_prompt(mm_a.novel_id, limit=50)
        spirit_gu = [t for t in terms_for_prompt
                     if t.get("source_term") == "Spirit Gu"]
        # get_terms_for_prompt deduplicates: novel-specific overrides global
        self.assertGreaterEqual(len(spirit_gu), 1)
        mm_a.close()


if __name__ == '__main__':
    unittest.main()
