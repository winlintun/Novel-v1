"""
Tests for GlossaryGenerator agent.
"""

import unittest
from unittest.mock import MagicMock, patch, mock_open


class TestGlossaryGenerator(unittest.TestCase):
    """Test cases for GlossaryGenerator."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_ollama = MagicMock()
        self.mock_memory = MagicMock()
        self.mock_config = MagicMock()
        self.mock_config.models.translator = "padauk-gemma:q8_0"

    def test_initialization(self):
        """GlossaryGenerator initializes correctly."""
        from src.agents.glossary_generator import GlossaryGenerator
        
        generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            config=self.mock_config
        )
        
        self.assertIsNotNone(generator)

    def test_extract_terms_returns_list(self):
        """extract_terms returns list of terms (v3.2.1 schema)."""
        from src.agents.glossary_generator import GlossaryGenerator
        
        generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            config=self.mock_config
        )
        
        # v3.2.1 schema format
        self.mock_ollama.chat.return_value = {
            "message": {"content": '{"extraction_meta": {"schema_version": "3.2.1", "source_language": "Chinese", "total_terms_found": 0, "overall_confidence": "high"}, "terms": []}'}
        }
        
        result = generator.extract_terms("test text", source_lang="Chinese")
        
        self.assertIsInstance(result, list)

    def test_extract_terms_handles_invalid_json(self):
        """extract_terms handles invalid JSON gracefully."""
        from src.agents.glossary_generator import GlossaryGenerator
        
        generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            config=self.mock_config
        )
        
        self.mock_ollama.chat.return_value = {
            "message": {"content": "invalid json"}
        }
        
        result = generator.extract_terms("test text")
        
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_extract_terms_with_chinese(self):
        """extract_terms works with Chinese source (v3.2.1 schema)."""
        from src.agents.glossary_generator import GlossaryGenerator
        
        generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            config=self.mock_config
        )
        
        self.mock_ollama.chat.return_value = {
            "message": {"content": '{"extraction_meta": {"schema_version": "3.2.1", "source_language": "Chinese", "total_terms_found": 0, "overall_confidence": "high"}, "terms": []}'}
        }
        
        result = generator.extract_terms("中文测试", source_lang="Chinese")
        
        self.assertIsInstance(result, list)

    def test_extract_terms_with_english(self):
        """extract_terms works with English source (v3.2.1 schema)."""
        from src.agents.glossary_generator import GlossaryGenerator
        
        generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            config=self.mock_config
        )
        
        self.mock_ollama.chat.return_value = {
            "message": {"content": '{"extraction_meta": {"schema_version": "3.2.1", "source_language": "English", "total_terms_found": 0, "overall_confidence": "high"}, "terms": []}'}
        }
        
        result = generator.extract_terms("English test", source_lang="English")
        
        self.assertIsInstance(result, list)

    def test_process_files_returns_list(self):
        """process_files returns list of extracted terms (v3.2.1 schema)."""
        from src.agents.glossary_generator import GlossaryGenerator
        
        generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            config=self.mock_config
        )
        
        self.mock_ollama.chat.return_value = {
            "message": {"content": '{"extraction_meta": {"schema_version": "3.2.1", "source_language": "Chinese", "total_terms_found": 0, "overall_confidence": "high"}, "terms": []}'}
        }
        
        result = generator.process_files(["test.md"])
        
        self.assertIsInstance(result, list)

    def test_save_to_pending_calls_memory(self):
        """save_to_pending saves terms to memory manager (v3.2.1 schema)."""
        from src.agents.glossary_generator import GlossaryGenerator
        
        generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            config=self.mock_config
        )
        
        # v3.2.1 schema fields
        terms = [{"source": "test", "target": "စမ်း", "category": "character"}]
        generator.save_to_pending(terms, chapter_num=1)
        
        self.mock_memory.add_pending_term.assert_called_once()

    def test_generate_from_chapter_returns_count(self):
        """generate_from_chapter returns number of terms extracted."""
        from src.agents.glossary_generator import GlossaryGenerator
        
        generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            config=self.mock_config
        )
        
        # v3.2.1 schema
        self.mock_ollama.chat.return_value = {
            "message": {"content": '{"extraction_meta": {"schema_version": "3.2.1", "source_language": "English", "total_terms_found": 1, "overall_confidence": "high"}, "terms": [{"source": "t", "target": "တ", "category": "character"}]}'}
        }
        
        with patch("builtins.open", mock_open(read_data="test")):
            result = generator.generate_from_chapter("test.md", chapter_num=1)
        
        self.assertIsInstance(result, int)


class TestGlossaryGeneratorEdgeCases(unittest.TestCase):
    """Test GlossaryGenerator edge cases."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_ollama = MagicMock()
        self.mock_memory = MagicMock()
        self.mock_config = MagicMock()
        self.mock_config.models.translator = "padauk-gemma:q8_0"

    def test_extract_terms_empty_text(self):
        """extract_terms handles empty text."""
        from src.agents.glossary_generator import GlossaryGenerator
        
        generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            config=self.mock_config
        )
        
        result = generator.extract_terms("")
        
        self.assertIsInstance(result, list)

    def test_process_files_empty_list(self):
        """process_files handles empty file list."""
        from src.agents.glossary_generator import GlossaryGenerator
        
        generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            config=self.mock_config
        )
        
        result = generator.process_files([])
        
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_save_to_pending_empty_terms(self):
        """save_to_pending handles empty terms list."""
        from src.agents.glossary_generator import GlossaryGenerator
        
        generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            config=self.mock_config
        )
        
        generator.save_to_pending([])
        
        self.mock_memory.add_pending_term.assert_not_called()


class TestGlossaryGeneratorSaveBehavior(unittest.TestCase):
    """Integration tests for save_to_pending / save_relationships with a real DB."""

    def setUp(self):
        import tempfile, os
        from src.memory.memory_manager import MemoryManager
        self._tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self._tmpdir, "test_gen.db")
        self.memory = MemoryManager(
            novel_name="gen-test", db_path=self.db_path, auto_seed_global=False
        )
        from src.agents.glossary_generator import GlossaryGenerator
        self.mock_ollama = MagicMock()
        self.mock_config = MagicMock()
        self.mock_config.models.translator = "padauk-gemma:q8_0"
        self.generator = GlossaryGenerator(
            ollama_client=self.mock_ollama,
            memory_manager=self.memory,
            config=self.mock_config,
            auto_approve_threshold=0.0,
        )

    def tearDown(self):
        self.memory.close()
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_save_to_pending_writes_chapter_first_seen(self):
        """New terms get chapter_first_seen set in the DB."""
        terms = [{"source": "Bai Xiaochun", "target": "ဘိုင်ရှောင်ချန်", "category": "character", "confidence": 0.9}]
        saved = self.generator.save_to_pending(terms, chapter_num=3)
        self.assertEqual(saved, 1)
        row = self.memory.glossary_repo.get_term_by_source(self.memory.novel_id, "Bai Xiaochun")
        self.assertIsNotNone(row)
        self.assertEqual(row["chapter_first_seen"], 3)
        self.assertEqual(row["chapter_last_seen"], 3)

    def test_dedup_on_rerun_skips_existing(self):
        """Re-running save_to_pending skips terms already in the glossary."""
        terms = [{"source": "Fang He", "target": "ဖန်ဟယ်", "category": "character", "confidence": 0.9}]
        first = self.generator.save_to_pending(terms, chapter_num=1)
        self.assertEqual(first, 1)
        # Re-run (simulating --generate-glossary re-run over same chapters)
        second = self.generator.save_to_pending(terms, chapter_num=1)
        self.assertEqual(second, 0)  # skipped — no new terms saved

    def test_dedup_skips_approved_terms(self):
        """Terms already approved are skipped during generation."""
        self.memory.add_pending_term(
            source="Approved Term", target="အတည်ပြု", category="item",
            chapter=1, approved=True,
        )
        terms = [{"source": "Approved Term", "target": "အတည်ပြု", "category": "item", "confidence": 0.9}]
        saved = self.generator.save_to_pending(terms, chapter_num=2)
        self.assertEqual(saved, 0)

    def test_auto_approve_high_confidence(self):
        """Terms with confidence >= threshold are saved as approved."""
        self.generator.auto_approve_threshold = 0.85
        terms = [
            {"source": "High Conf", "target": "မြင့်", "category": "character", "confidence": 0.9},
            {"source": "Low Conf", "target": "နိမ့်", "category": "item", "confidence": 0.5},
        ]
        saved = self.generator.save_to_pending(terms, chapter_num=1)
        self.assertEqual(saved, 2)
        high = self.memory.glossary_repo.get_term_by_source(self.memory.novel_id, "High Conf")
        low = self.memory.glossary_repo.get_term_by_source(self.memory.novel_id, "Low Conf")
        self.assertEqual(high["status"], "approved")
        self.assertEqual(low["status"], "pending")

    def test_placeholder_target_never_auto_approved(self):
        """Placeholder targets are skipped entirely, never saved."""
        self.generator.auto_approve_threshold = 0.1
        terms = [{"source": "Unknown", "target": "【?term?】", "category": "item", "confidence": 0.95}]
        saved = self.generator.save_to_pending(terms, chapter_num=1)
        self.assertEqual(saved, 0)

    def test_save_relationships_creates_edges(self):
        """save_relationships creates term_relationships edges between saved terms."""
        # First save two terms
        terms = [
            {"source": "Bai Xiaochun", "target": "ဘိုင်ရှောင်ချန်", "category": "character", "confidence": 0.9},
            {"source": "Azure Origin Sect", "target": "အေးဇင်းဂိုဏ်း", "category": "organization", "confidence": 0.9},
        ]
        self.generator.save_to_pending(terms, chapter_num=1)
        # Approve them so get_term_by_source finds them (get_term_by_source checks scope=novel regardless of status)
        # Now save a relationship
        rels = [{"src": "Bai Xiaochun", "dst": "Azure Origin Sect", "relation_type": "member_of", "confidence": 0.9}]
        created = self.generator.save_relationships(rels, chapter_num=1)
        self.assertEqual(created, 1)

    def test_save_relationships_skips_missing_endpoints(self):
        """Relationships whose endpoints aren't in the glossary are skipped."""
        rels = [{"src": "Ghost", "dst": "Phantom", "relation_type": "member_of", "confidence": 0.9}]
        created = self.generator.save_relationships(rels, chapter_num=1)
        self.assertEqual(created, 0)

    def test_save_relationships_empty_list(self):
        """Empty relationships list returns 0."""
        self.assertEqual(self.generator.save_relationships([], 1), 0)

    def test_save_to_pending_returns_saved_count(self):
        """save_to_pending returns the count of NEW terms saved."""
        terms = [
            {"source": "Term A", "target": "အ", "category": "item", "confidence": 0.9},
            {"source": "Term B", "target": "ဘ", "category": "item", "confidence": 0.9},
        ]
        saved = self.generator.save_to_pending(terms, chapter_num=1)
        self.assertEqual(saved, 2)
        # Re-run: both are duplicates now
        saved_again = self.generator.save_to_pending(terms, chapter_num=1)
        self.assertEqual(saved_again, 0)


if __name__ == "__main__":
    unittest.main()