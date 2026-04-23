"""
Unit Tests for Novel Translation Pipeline
"""

import unittest
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.file_handler import FileHandler
from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager
from src.agents.preprocessor import Preprocessor
from src.agents.translator import Translator
from src.agents.checker import Checker


class TestFileHandler(unittest.TestCase):
    """Test FileHandler utility."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_read_write_text(self):
        """Test text file read/write."""
        filepath = Path(self.temp_dir) / "test.txt"
        content = "Test content\nမြန်မာစာသား"
        
        FileHandler.write_text(str(filepath), content)
        result = FileHandler.read_text(str(filepath))
        
        self.assertEqual(result, content)
    
    def test_read_write_json(self):
        """Test JSON file read/write."""
        filepath = Path(self.temp_dir) / "test.json"
        data = {"key": "value", "myanmar": "မြန်မာ", "number": 42}
        
        FileHandler.write_json(str(filepath), data)
        result = FileHandler.read_json(str(filepath))
        
        self.assertEqual(result, data)
    
    def test_read_missing_json_returns_empty(self):
        """Test that missing JSON returns empty dict."""
        filepath = Path(self.temp_dir) / "nonexistent.json"
        result = FileHandler.read_json(str(filepath))
        self.assertEqual(result, {})
    
    def test_read_missing_text_raises_error(self):
        """Test that missing text file raises error."""
        filepath = Path(self.temp_dir) / "nonexistent.txt"
        with self.assertRaises(FileNotFoundError):
            FileHandler.read_text(str(filepath))
    
    def test_ensure_dir(self):
        """Test directory creation."""
        dirpath = Path(self.temp_dir) / "nested" / "dir"
        result = FileHandler.ensure_dir(str(dirpath))
        
        self.assertTrue(result.exists())
        self.assertTrue(result.is_dir())


class TestPreprocessor(unittest.TestCase):
    """Test Preprocessor agent."""
    
    def test_estimate_tokens_chinese(self):
        """Test token estimation for Chinese."""
        preprocessor = Preprocessor()
        
        # Pure Chinese
        text = "这是测试文本"
        tokens = preprocessor.estimate_tokens(text)
        
        # Should be roughly 1.5x character count
        self.assertGreater(tokens, len(text))
    
    def test_split_into_paragraphs(self):
        """Test paragraph splitting."""
        preprocessor = Preprocessor()
        
        text = "Para 1\n\nPara 2\n\nPara 3"
        paragraphs = preprocessor.split_into_paragraphs(text)
        
        self.assertEqual(len(paragraphs), 3)
    
    def test_create_chunks_respects_size(self):
        """Test that chunks respect size limits."""
        preprocessor = Preprocessor(chunk_size=100)
        
        # Create text larger than chunk size
        text = "中文测试 " * 100
        chunks = preprocessor.create_chunks(text)
        
        # Should create multiple chunks
        self.assertGreater(len(chunks), 1)
        
        # Each chunk should have reasonable size
        for chunk in chunks:
            self.assertIn('chunk_id', chunk)
            self.assertIn('text', chunk)
            self.assertIn('size', chunk)
    
    def test_get_chapter_info(self):
        """Test chapter info extraction from filename."""
        preprocessor = Preprocessor()
        
        filepath = "/path/to/novel_name_001.md"
        info = preprocessor.get_chapter_info(filepath)
        
        self.assertEqual(info['novel_name'], 'novel_name')
        self.assertEqual(info['chapter_num'], 1)
        self.assertEqual(info['filename'], 'novel_name_001.md')


class TestMemoryManager(unittest.TestCase):
    """Test MemoryManager."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.glossary_path = Path(self.temp_dir) / "glossary.json"
        self.context_path = Path(self.temp_dir) / "context.json"
        self.memory = MemoryManager(str(self.glossary_path), str(self.context_path))
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_add_term_increases_count(self):
        """Test adding term increases count."""
        initial = self.memory.glossary.get('total_terms', 0)
        
        result = self.memory.add_term("测试", "စမ်းသပ်", "general", 1)
        
        self.assertTrue(result)
        self.assertEqual(self.memory.glossary['total_terms'], initial + 1)
    
    def test_add_duplicate_term_fails(self):
        """Test adding duplicate term fails."""
        self.memory.add_term("测试", "စမ်းသပ်", "general", 1)
        result = self.memory.add_term("测试", "အခြား", "general", 1)
        
        self.assertFalse(result)
    
    def test_get_term_returns_target(self):
        """Test get_term returns correct translation."""
        self.memory.add_term("测试", "စမ်းသပ်", "general", 1)
        
        result = self.memory.get_term("测试")
        
        self.assertEqual(result, "စမ်းသပ်")
    
    def test_get_term_not_found_returns_none(self):
        """Test get_term returns None for unknown term."""
        result = self.memory.get_term("不存在")
        self.assertIsNone(result)
    
    def test_context_buffer_fifo(self):
        """Test FIFO buffer behavior."""
        # Add more than max items (10)
        for i in range(15):
            self.memory.push_to_buffer(f"Paragraph {i}")
        
        # Should only keep last 10
        buffer_list = list(self.memory.paragraph_buffer)
        self.assertEqual(len(buffer_list), 10)
        self.assertEqual(buffer_list[0], "Paragraph 5")
        self.assertEqual(buffer_list[-1], "Paragraph 14")
    
    def test_save_and_load_memory(self):
        """Test memory persistence."""
        # Add some data
        self.memory.add_term("测试", "စမ်းသပ်", "general", 1)
        self.memory.push_to_buffer("Test content")
        
        # Save
        self.memory.save_memory()
        
        # Load in new instance
        new_memory = MemoryManager(str(self.glossary_path), str(self.context_path))
        
        self.assertEqual(new_memory.get_term("测试"), "စမ်းသပ်")


class TestTranslator(unittest.TestCase):
    """Test Translator agent."""
    
    def setUp(self):
        self.mock_ollama = Mock(spec=OllamaClient)
        self.mock_memory = Mock(spec=MemoryManager)
        
        self.mock_memory.get_all_memory_for_prompt.return_value = {
            'glossary': 'Test glossary',
            'context': 'Test context',
            'rules': 'No rules',
            'summary': 'Test summary'
        }
        
        self.translator = Translator(self.mock_ollama, self.mock_memory)
    
    def test_build_prompt_includes_glossary(self):
        """Test prompt includes glossary."""
        text = "测试文本"
        prompt = self.translator.build_prompt(text)
        
        self.assertIn("Test glossary", prompt)
        self.assertIn(text, prompt)
    
    def test_translate_paragraph_calls_ollama(self):
        """Test translation calls Ollama."""
        self.mock_ollama.chat.return_value = "မြန်မာဘာသာပြန်"
        
        result = self.translator.translate_paragraph("测试")
        
        self.mock_ollama.chat.assert_called_once()
        self.assertEqual(result, "မြန်မာဘာသာပြန်")
    
    def test_translate_updates_memory(self):
        """Test translation updates memory buffer."""
        self.mock_ollama.chat.return_value = "ဘာသာပြန်"
        
        self.translator.translate_paragraph("测试")
        
        self.mock_memory.push_to_buffer.assert_called_once_with("ဘာသာပြန်")


class TestChecker(unittest.TestCase):
    """Test Checker agent."""
    
    def setUp(self):
        self.mock_memory = Mock(spec=MemoryManager)
        self.mock_memory.get_all_terms.return_value = [
            {'source': '罗青', 'target': 'လူချင်း'}
        ]
        
        self.checker = Checker(self.mock_memory)
    
    def test_check_glossary_consistency(self):
        """Test glossary consistency check."""
        # Text with untranslated term
        text = "罗青 is a character"
        issues = self.checker.check_glossary_consistency(text)
        
        # Should detect untranslated source term
        self.assertTrue(len(issues) > 0)
    
    def test_calculate_quality_score(self):
        """Test quality score calculation."""
        # Good Myanmar text
        good_text = "မြန်မာဘာသာပြန်ချက်ကောင်းပါသည်။" * 10
        score = self.checker.calculate_quality_score(good_text)
        
        self.assertGreater(score, 50)
        
        # Bad text with error marker
        bad_text = "[TRANSLATION ERROR: failed]"
        score = self.checker.calculate_quality_score(bad_text)
        
        self.assertLess(score, 70)
    
    def test_check_myanmar_unicode(self):
        """Test Myanmar Unicode validation."""
        # Valid text
        valid = "မြန်မာစာတည်း"
        issues = self.checker.check_myanmar_unicode(valid)
        self.assertEqual(len(issues), 0)
        
        # Invalid with replacement char
        invalid = "မြန်မာ�စာ"
        issues = self.checker.check_myanmar_unicode(invalid)
        self.assertTrue(len(issues) > 0)


class TestOllamaClient(unittest.TestCase):
    """Test OllamaClient."""
    
    @patch('src.utils.ollama_client.ollama')
    def test_chat_with_retry(self, mock_ollama_module):
        """Test chat with retry logic."""
        mock_client = Mock()
        mock_ollama_module.Client.return_value = mock_client
        
        mock_response = {'message': {'content': 'Test response'}}
        mock_client.chat.return_value = mock_response
        
        client = OllamaClient(model="test-model", max_retries=3)
        result = client.chat("Test prompt")
        
        self.assertEqual(result, 'Test response')
        mock_client.chat.assert_called_once()
    
    @patch('src.utils.ollama_client.ollama')
    def test_check_model_available(self, mock_ollama_module):
        """Test model availability check."""
        mock_client = Mock()
        mock_ollama_module.Client.return_value = mock_client
        
        mock_client.list.return_value = {'models': [{'name': 'test-model'}]}
        
        client = OllamaClient(model="test-model")
        available = client.check_model_available()
        
        self.assertTrue(available)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
