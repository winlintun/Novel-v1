"""
Tests for FastTranslator agent.
"""

import unittest
from unittest.mock import MagicMock


class TestFastTranslator(unittest.TestCase):
    """Test cases for FastTranslator."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_ollama = MagicMock()
        self.mock_memory = MagicMock()
        self.mock_memory.get_all_memory_for_prompt.return_value = {
            "glossary": "",
            "context": ""
        }

    def test_initialization(self):
        """FastTranslator initializes with required parameters."""
        from src.agents.fast_translator import FastTranslator
        
        translator = FastTranslator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            use_streaming=True
        )
        
        self.assertEqual(translator.ollama, self.mock_ollama)
        self.assertEqual(translator.memory, self.mock_memory)
        self.assertTrue(translator.use_streaming)

    def test_initialization_without_streaming(self):
        """FastTranslator works without streaming."""
        from src.agents.fast_translator import FastTranslator
        
        translator = FastTranslator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory,
            use_streaming=False
        )
        
        self.assertFalse(translator.use_streaming)

    def test_build_prompt_returns_string(self):
        """build_prompt returns a string."""
        from src.agents.fast_translator import FastTranslator
        
        translator = FastTranslator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory
        )
        
        result = translator.build_prompt("test text")
        
        self.assertIsInstance(result, str)

    def test_translate_chunk_returns_string(self):
        """translate_chunk returns translated string."""
        from src.agents.fast_translator import FastTranslator
        
        translator = FastTranslator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory
        )
        
        self.mock_ollama.chat.return_value = {"message": {"content": "translated"}}
        
        result = translator.translate_chunk("test", chapter_num=1)
        
        self.assertIsInstance(result, str)

    def test_translate_chunks_returns_list(self):
        """translate_chunks returns list of translations."""
        from src.agents.fast_translator import FastTranslator
        
        translator = FastTranslator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory
        )
        
        chunks = [{"text": "chunk1"}, {"text": "chunk2"}]
        
        self.mock_ollama.chat.return_value = {"message": {"content": "translated"}}
        
        result = translator.translate_chunks(chunks, chapter_num=1)
        
        self.assertIsInstance(result, list)

    def test_translate_chapter_returns_string(self):
        """translate_chapter returns full translation."""
        from src.agents.fast_translator import FastTranslator
        
        translator = FastTranslator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory
        )
        
        self.mock_ollama.chat.return_value = {"message": {"content": "full chapter"}}
        
        result = translator.translate_chapter("long text", chapter_num=5)
        
        self.assertIsInstance(result, str)


class TestFastTranslatorEdgeCases(unittest.TestCase):
    """Test FastTranslator edge cases."""

    def setUp(self):
        self.mock_ollama = MagicMock()
        self.mock_memory = MagicMock()
        self.mock_memory.get_all_memory_for_prompt.return_value = {"glossary": "", "context": ""}

    def test_translate_chunk_with_empty_text(self):
        """translate_chunk handles empty text."""
        from src.agents.fast_translator import FastTranslator
        
        translator = FastTranslator(
            ollama_client=self.mock_ollama,
            memory_manager=self.mock_memory
        )
        
        result = translator.translate_chunk("", chapter_num=1)
        
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()