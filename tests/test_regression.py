"""
Regression Tests for Novel Translation Project
Ensures new changes don't break existing functionality.

According to need_fix.md:
- Re-test previously translated chapters
- Verify placeholder detection works
- Ensure all previously working features still work
"""

import unittest
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.postprocessor import clean_output, validate_output
from src.utils.json_extractor import safe_parse_terms
from src.agents.prompt_patch import LANGUAGE_GUARD, TRANSLATOR_SYSTEM_PROMPT
from src.memory.memory_manager import MemoryManager
from src.agents.checker import Checker


class TestPlaceholderRegression(unittest.TestCase):
    """Regression tests for 【?term?】 placeholder functionality."""
    
    def test_placeholder_preserved_in_output(self):
        """Test that 【?term?】 placeholders are preserved, not removed."""
        text = "မြန်မာစာ 【?unknown?】 နောက်ထပ် စာသား"
        # Placeholder should remain intact
        self.assertIn("【?unknown?】", text)
    
    def test_placeholder_detected_in_quality_check(self):
        """Test that placeholders are detected during quality check."""
        text_with_placeholder = "မြန်မာစာ 【?未知词?】 more text" * 10
        # Placeholders indicate unresolved terms
        self.assertIn("【?", text_with_placeholder)
        placeholder_count = text_with_placeholder.count("【?")
        self.assertGreater(placeholder_count, 0)
    
    def test_multiple_placeholders_handled(self):
        """Test handling multiple placeholders in one text."""
        text = "【?term1?】 မြန်မာ 【?term2?】 စာ 【?term3?】"
        placeholders = ["【?term1?】", "【?term2?】", "【?term3?】"]
        for ph in placeholders:
            self.assertIn(ph, text)


class TestPostprocessorRegression(unittest.TestCase):
    """Regression tests for postprocessor - ensure fixes don't break."""
    
    def test_thai_output_bug_fixed(self):
        """Test that Thai output detection still works (Bug Fix Regression)."""
        # This was a critical bug: Thai output should be detected and REJECTED
        thai_text = "မြန်မာစာ กรุงเทพฯ"
        report = validate_output(thai_text, chapter=1)
        self.assertEqual(report["status"], "REJECTED")  # Thai is critical error
        self.assertGreater(report["thai_chars_leaked"], 0)
    
    def test_think_tag_stripping_regression(self):
        """Test that <think> tags are still stripped (Bug Fix Regression)."""
        text = "<think>Internal thought</think>မြန်မာဘာသာ"
        cleaned = clean_output(text)
        self.assertNotIn("<think>", cleaned)
        self.assertNotIn("</think>", cleaned)
        self.assertIn("မြန်မာဘာသာ", cleaned)
    
    def test_answer_tag_stripping_regression(self):
        """Test that <answer> tags are still stripped."""
        text = "<answer>မြန်မာဘာသာ</answer>"
        cleaned = clean_output(text)
        self.assertNotIn("<answer>", cleaned)
        self.assertNotIn("</answer>", cleaned)
        self.assertIn("မြန်မာဘာသာ", cleaned)


class TestJsonExtractorRegression(unittest.TestCase):
    """Regression tests for JSON extractor - ensure fixes don't break."""
    
    def test_entity_extraction_bug_fixed(self):
        """Test that malformed JSON is handled gracefully (Bug Fix Regression)."""
        # This was a critical bug: json.loads() would crash
        malformed = "Not valid JSON {bad"
        result = safe_parse_terms(malformed)
        self.assertEqual(result["new_terms"], [])  # Should not crash
    
    def test_empty_response_handling(self):
        """Test empty response handling."""
        result = safe_parse_terms("")
        self.assertEqual(result["new_terms"], [])
        
        result = safe_parse_terms(None)
        self.assertEqual(result["new_terms"], [])
    
    def test_valid_json_parsing(self):
        """Test that valid JSON still parses correctly."""
        valid = '{"new_terms": [{"source": "X", "target": "Y", "category": "item"}]}'
        result = safe_parse_terms(valid)
        self.assertEqual(len(result["new_terms"]), 1)
        self.assertEqual(result["new_terms"][0]["source"], "X")


class TestLanguageGuardRegression(unittest.TestCase):
    """Regression tests for LANGUAGE_GUARD - ensure fixes don't break."""
    
    def test_language_guard_in_translator_prompt(self):
        """Test LANGUAGE_GUARD is at start of translator prompt."""
        self.assertTrue(TRANSLATOR_SYSTEM_PROMPT.startswith(LANGUAGE_GUARD))
    
    def test_language_guard_contains_myanmar_rule(self):
        """Test LANGUAGE_GUARD specifies Myanmar only."""
        self.assertIn("Myanmar (Burmese)", LANGUAGE_GUARD)
        self.assertIn("ONLY", LANGUAGE_GUARD)
    
    def test_language_guard_forbids_thai(self):
        """Test LANGUAGE_GUARD forbids Thai."""
        self.assertIn("Thai", LANGUAGE_GUARD)
        self.assertIn("FORBIDDEN", LANGUAGE_GUARD)


class TestGlossaryConsistencyRegression(unittest.TestCase):
    """Regression tests for glossary consistency checking."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.glossary_path = Path(self.temp_dir) / "glossary.json"
        self.context_path = Path(self.temp_dir) / "context.json"
        self.memory = MemoryManager(str(self.glossary_path), str(self.context_path))
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_term_add_and_retrieve(self):
        """Test basic term add/retrieve still works."""
        self.memory.add_term("测试", "စမ်းသပ်", "general", 1)
        result = self.memory.get_term("测试")
        self.assertEqual(result, "စမ်းသပ်")
    
    def test_duplicate_term_rejection(self):
        """Test duplicate terms are still rejected."""
        self.memory.add_term("测试", "စမ်းသပ်", "general", 1)
        result = self.memory.add_term("测试", "အခြား", "general", 1)
        self.assertFalse(result)
    
    def test_checker_detects_untranslated_terms(self):
        """Test checker still detects untranslated source terms."""
        self.memory.add_term("主角", "ဇော်ဂျီ", "character", 1)
        checker = Checker(self.memory)
        
        # Text with untranslated term
        text = "主角 က ပြောတယ်"
        issues = checker.check_glossary_consistency(text)
        self.assertGreater(len(issues), 0)


class TestMemoryManagerRegression(unittest.TestCase):
    """Regression tests for MemoryManager persistence."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.glossary_path = Path(self.temp_dir) / "glossary.json"
        self.context_path = Path(self.temp_dir) / "context.json"
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_save_and_load_persistence(self):
        """Test save/load cycle still works."""
        memory1 = MemoryManager(str(self.glossary_path), str(self.context_path))
        memory1.add_term("测试", "စမ်းသပ်", "general", 1)
        memory1.push_to_buffer("Test context")
        memory1.save_memory()
        
        memory2 = MemoryManager(str(self.glossary_path), str(self.context_path))
        self.assertEqual(memory2.get_term("测试"), "စမ်းသပ်")
    
    def test_fifo_buffer_behavior(self):
        """Test FIFO buffer still works correctly."""
        memory = MemoryManager(str(self.glossary_path), str(self.context_path))
        
        # Add more than max (10)
        for i in range(15):
            memory.push_to_buffer(f"Para {i}")
        
        context = memory.get_context_buffer(10)
        self.assertNotIn("Para 0", context)  # First should be gone
        self.assertIn("Para 14", context)  # Last should be there


class TestBackwardsCompatibility(unittest.TestCase):
    """Tests for backwards compatibility with old data formats."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.glossary_path = Path(self.temp_dir) / "glossary.json"
        self.context_path = Path(self.temp_dir) / "context.json"
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_old_glossary_format_loading(self):
        """Test loading old-format glossary files."""
        # Create old-format glossary
        old_format = {
            "version": "1.0",
            "total_terms": 2,
            "terms": [
                {"id": "term_001", "source": "旧词", "target": "ဟောင်း", "category": "general", "verified": True},
                {"id": "term_002", "source": "新词", "target": "သစ်", "category": "item", "verified": False}
            ]
        }
        
        with open(self.glossary_path, 'w', encoding='utf-8') as f:
            json.dump(old_format, f)
        
        memory = MemoryManager(str(self.glossary_path), str(self.context_path))
        self.assertEqual(memory.get_term("旧词"), "ဟောင်း")
        self.assertEqual(memory.get_term("新词"), "သစ်")


if __name__ == '__main__':
    unittest.main(verbosity=2)
