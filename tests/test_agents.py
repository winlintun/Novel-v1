"""
Unit tests for core agents (Translator, Refiner, Checker, ContextUpdater).
Mocks OllamaClient to avoid real API calls.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.translator import Translator
from src.agents.refiner import Refiner
from src.agents.checker import Checker
from src.agents.context_updater import ContextUpdater
from src.memory.memory_manager import MemoryManager
from src.utils.ollama_client import OllamaClient


class TestTranslator(unittest.TestCase):
    def setUp(self):
        self.mock_ollama = MagicMock(spec=OllamaClient)
        self.mock_memory = MagicMock(spec=MemoryManager)
        
        # Default memory mock return
        self.mock_memory.get_all_memory_for_prompt.return_value = {
            'glossary': 'GLOSSARY: 主角=ဇော်ဂျီ',
            'context': 'No previous context.',
            'rules': 'No session rules.',
            'summary': ''
        }
        
        self.translator = Translator(self.mock_ollama, self.mock_memory)

    def test_build_prompt(self):
        """Test that translation prompt includes glossary and context."""
        text = "你好"
        prompt = self.translator.build_prompt(text)
        
        self.assertIn("GLOSSARY", prompt)
        self.assertIn("ဇော်ဂျီ", prompt)
        self.assertIn("你好", prompt)

    def test_translate_paragraph(self):
        """Test single paragraph translation."""
        self.mock_ollama.chat.return_value = "မင်္ဂလာပါ"
        
        result = self.translator.translate_paragraph("你好")
        
        self.assertEqual(result, "မင်္ဂလာပါ")
        self.mock_memory.push_to_buffer.assert_called_with("မင်္ဂလာပါ")


class TestRefiner(unittest.TestCase):
    def setUp(self):
        self.mock_ollama = MagicMock(spec=OllamaClient)
        self.refiner = Refiner(self.mock_ollama)

    def test_refine_paragraph(self):
        """Test refinement call."""
        self.mock_ollama.chat.return_value = "မြန်မာစာ"
        
        result = self.refiner.refine_paragraph("Raw Myanmar")
        
        self.assertEqual(result, "မြန်မာစာ")
        self.mock_ollama.chat.assert_called()


class TestChecker(unittest.TestCase):
    def setUp(self):
        self.mock_memory = MagicMock(spec=MemoryManager)
        self.checker = Checker(self.mock_memory)

    def test_check_glossary_consistency_pass(self):
        """Test glossary check passes when correct term is used."""
        self.mock_memory.get_all_terms.return_value = [
            {'source': '主角', 'target': 'ဇော်ဂျီ'}
        ]
        
        # In translation, '主角' should NOT appear, 'ဇော်ဂျီ' SHOULD appear
        text = "ဇော်ဂျီ က ပြောတယ်"
        issues = self.checker.check_glossary_consistency(text)
        
        # Checker.check_glossary_consistency actually checks if SOURCE exists in target text
        self.assertEqual(len(issues), 0)

    def test_check_glossary_consistency_fail(self):
        """Test glossary check fails when source term is found in translation."""
        self.mock_memory.get_all_terms.return_value = [
            {'source': '主角', 'target': 'ဇော်ဂျီ'}
        ]
        
        text = "主角 က ပြောတယ်" # '主角' is still there!
        issues = self.checker.check_glossary_consistency(text)
        
        self.assertGreater(len(issues), 0)
        self.assertEqual(issues[0]['type'], 'untranslated_term')

    def test_check_markdown_formatting(self):
        """Test markdown preservation check."""
        original = "# Chapter 1\n**Bold**"
        translated = "# အခန်း ၁\n**စာလုံးကြီး**"
        
        issues = self.checker.check_markdown_formatting(original, translated)
        self.assertEqual(len(issues), 0)
        
        # Mismatch
        bad_translated = "အခန်း ၁\nစာလုံးကြီး" # No #, no **
        issues = self.checker.check_markdown_formatting(original, bad_translated)
        self.assertGreater(len(issues), 0)

    def test_quality_score(self):
        """Test quality score calculation."""
        # Use longer text (> 50 chars) to avoid automatic -50 penalty
        text = "နေကောင်းလား မင်္ဂလာပါ မြန်မာစာ သင်ယူနေပါတယ်ခင်ဗျာ။ အားလုံးပဲ မင်္ဂလာရှိသော နေ့လေးတစ်နေ့ ဖြစ်ပါစေလို့ ဆုတောင်းပေးပါတယ်"
        score = self.checker.calculate_quality_score(text)
        self.assertGreaterEqual(score, 90)
        
        bad_text = "abc 123 !@#" # No Myanmar
        score = self.checker.calculate_quality_score(bad_text)
        self.assertLess(score, 60)


class TestContextUpdater(unittest.TestCase):
    def setUp(self):
        self.mock_ollama = MagicMock(spec=OllamaClient)
        self.mock_memory = MagicMock(spec=MemoryManager)
        self.updater = ContextUpdater(self.mock_ollama, self.mock_memory)

    def test_process_chapter(self):
        """Test post-chapter processing."""
        # Mock term extraction
        self.mock_ollama.chat.return_value = '{"new_terms": [{"source": "新词", "target": "သစ်", "category": "item"}]}'
        
        original = "新词"
        translated = "သစ်"
        
        from unittest.mock import ANY
        self.updater.process_chapter(original, translated, 1)
        
        # Verify glossary_pending update
        self.mock_memory.update_chapter_context.assert_called_with(1)


if __name__ == '__main__':
    # Define ANY for assertion
    from unittest.mock import ANY
    unittest.main()
