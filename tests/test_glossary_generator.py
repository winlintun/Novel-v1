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
        terms = [{"source_term": "test", "target_term": "စမ်း", "category": "character"}]
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
            "message": {"content": '{"extraction_meta": {"schema_version": "3.2.1", "source_language": "English", "total_terms_found": 1, "overall_confidence": "high"}, "terms": [{"source_term": "t", "target_term": "တ", "category": "character"}]}'}
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


if __name__ == "__main__":
    unittest.main()