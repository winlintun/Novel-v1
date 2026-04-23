"""
Unit tests for postprocessor module.
Tests clean_output, validate_output, language detection.
"""

import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.postprocessor import (
    strip_reasoning_tags,
    strip_header_artifacts,
    detect_language_leakage,
    myanmar_char_ratio,
    clean_output,
    validate_output,
)


class TestStripReasoningTags(unittest.TestCase):
    """Test stripping of reasoning model tags."""
    
    def test_strip_think_tags(self):
        """Test stripping <think>...</think> tags."""
        text = "<think>Internal thought</think>မြန်မာဘာသာ"
        result = strip_reasoning_tags(text)
        self.assertNotIn("<think>", result)
        self.assertNotIn("</think>", result)
        self.assertNotIn("Internal thought", result)
        self.assertIn("မြန်မာဘာသာ", result)
    
    def test_strip_answer_tags(self):
        """Test stripping <answer> tags."""
        text = "<answer>မြန်မာဘာသာ</answer>"
        result = strip_reasoning_tags(text)
        self.assertNotIn("<answer>", result)
        self.assertNotIn("</answer>", result)
        self.assertIn("မြန်မာဘာသာ", result)
    
    def test_strip_html_comments(self):
        """Test stripping HTML comments."""
        text = "<!-- comment -->မြန်မာဘာသာ"
        result = strip_reasoning_tags(text)
        self.assertNotIn("<!--", result)
        self.assertNotIn("-->", result)
        self.assertIn("မြန်မာဘာသာ", result)
    
    def test_strip_multiline_think(self):
        """Test stripping multiline think blocks."""
        text = """<think>
Line 1
Line 2
</think>
မြန်မာဘာသာ"""
        result = strip_reasoning_tags(text)
        self.assertNotIn("<think>", result)
        self.assertNotIn("Line 1", result)
        self.assertIn("မြန်မာဘာသာ", result)
    
    def test_case_insensitive_strip(self):
        """Test case-insensitive tag stripping."""
        text = "<THINK>thought</THINK><ANSWER>text</ANSWER>"
        result = strip_reasoning_tags(text)
        self.assertNotIn("<THINK>", result)
        self.assertNotIn("<ANSWER>", result)


class TestStripHeaderArtifacts(unittest.TestCase):
    """Test stripping of header artifacts."""
    
    def test_strip_translation_headers(self):
        """Test stripping MYANMAR TRANSLATION headers."""
        text = "MYANMAR TRANSLATION:\nမြန်မာဘာသာ"
        result = strip_header_artifacts(text)
        self.assertNotIn("MYANMAR TRANSLATION:", result)
        self.assertIn("မြန်မာဘာသာ", result)
    
    def test_strip_input_headers(self):
        """Test stripping INPUT TEXT headers."""
        text = "INPUT TEXT:\nမြန်မာဘာသာ"
        result = strip_header_artifacts(text)
        self.assertNotIn("INPUT TEXT:", result)
        self.assertIn("မြန်မာဘာသာ", result)
    
    def test_strip_progress_headers(self):
        """Test stripping Translation Progress headers."""
        text = "Translation Progress: 50%\nမြန်မာဘာသာ"
        result = strip_header_artifacts(text)
        self.assertNotIn("Translation Progress", result)
        self.assertIn("မြန်မာဘာသာ", result)


class TestDetectLanguageLeakage(unittest.TestCase):
    """Test language leakage detection."""
    
    def test_detect_thai_chars(self):
        """Test detecting Thai characters."""
        text = "မြန်မာစာ กรุงเทพฯ more text"
        result = detect_language_leakage(text)
        self.assertGreater(result["thai_chars"], 0)
    
    def test_detect_chinese_chars(self):
        """Test detecting Chinese characters."""
        text = "မြန်မာစာ 中文 more text"
        result = detect_language_leakage(text)
        self.assertGreater(result["chinese_chars"], 0)
    
    def test_no_leakage_clean_text(self):
        """Test clean Myanmar text has no leakage."""
        text = "မြန်မာဘာသာ စာသား သန့်သန့်ရှင်းရှင်း"
        result = detect_language_leakage(text)
        self.assertEqual(result["thai_chars"], 0)
        self.assertEqual(result["chinese_chars"], 0)
    
    def detect_mixed_leakage(self):
        """Test detecting both Thai and Chinese."""
        text = "မြန်မာစာ กรุง中文 mixed"
        result = detect_language_leakage(text)
        self.assertGreater(result["thai_chars"], 0)
        self.assertGreater(result["chinese_chars"], 0)


class TestMyanmarCharRatio(unittest.TestCase):
    """Test Myanmar character ratio calculation."""
    
    def test_pure_myanmar(self):
        """Test pure Myanmar text returns 1.0."""
        text = "မြန်မာဘာသာ"
        ratio = myanmar_char_ratio(text)
        self.assertEqual(ratio, 1.0)
    
    def test_mixed_content(self):
        """Test mixed content returns correct ratio."""
        text = "မြန်မာ ABC"  # 4 Myanmar + 3 Latin + 1 space
        ratio = myanmar_char_ratio(text)
        self.assertGreater(ratio, 0.5)
        self.assertLess(ratio, 1.0)
    
    def test_no_myanmar(self):
        """Test text with no Myanmar returns 0."""
        text = "Hello World 123"
        ratio = myanmar_char_ratio(text)
        self.assertEqual(ratio, 0.0)
    
    def test_empty_string(self):
        """Test empty string returns 0."""
        ratio = myanmar_char_ratio("")
        self.assertEqual(ratio, 0.0)
    
    def test_whitespace_only(self):
        """Test whitespace-only string returns 0."""
        ratio = myanmar_char_ratio("   \n\t  ")
        self.assertEqual(ratio, 0.0)


class TestCleanOutput(unittest.TestCase):
    """Test full clean_output pipeline."""
    
    def test_full_pipeline(self):
        """Test complete cleaning pipeline."""
        raw = """<think>Thinking...</think>
MYANMAR TRANSLATION:
မြန်မာဘာသာ



More text"""
        result = clean_output(raw)
        self.assertNotIn("<think>", result)
        self.assertNotIn("MYANMAR TRANSLATION:", result)
        self.assertIn("မြန်မာဘာသာ", result)
        # Should collapse multiple blank lines
        self.assertNotIn("\n\n\n", result)
    
    def test_strips_leading_trailing_whitespace(self):
        """Test leading/trailing whitespace is stripped."""
        raw = "   \n\nမြန်မာဘာသာ\n\n   "
        result = clean_output(raw)
        self.assertEqual(result[0], "မ")  # Starts with Myanmar
        self.assertEqual(result[-1], "ာ")  # Ends with Myanmar


class TestValidateOutput(unittest.TestCase):
    """Test output validation and quality scoring."""
    
    def test_approved_high_quality(self):
        """Test high-quality Myanmar text is approved."""
        text = "မြန်မာဘာသာ စာသား တစ်ခု လုံလောက်သော အရှည်"
        report = validate_output(text, chapter=1)
        self.assertEqual(report["chapter"], 1)
        self.assertEqual(report["status"], "APPROVED")
        self.assertGreaterEqual(report["myanmar_ratio"], 0.70)
        self.assertEqual(report["thai_chars_leaked"], 0)
    
    def test_needs_review_low_ratio(self):
        """Test low Myanmar ratio needs review."""
        text = "This is mostly English text with a little မြန်မာ"
        report = validate_output(text, chapter=2)
        self.assertEqual(report["status"], "NEEDS_REVIEW")
        self.assertLess(report["myanmar_ratio"], 0.70)
    
    def test_needs_review_thai_leakage(self):
        """Test Thai leakage triggers review."""
        text = "မြန်မာဘာသာ กรุงเทพฯ"
        report = validate_output(text, chapter=3)
        self.assertEqual(report["status"], "NEEDS_REVIEW")
        self.assertGreater(report["thai_chars_leaked"], 0)
    
    def test_report_structure(self):
        """Test report contains all required fields."""
        text = "မြန်မာဘာသာ"
        report = validate_output(text, chapter=5)
        required_fields = ["chapter", "myanmar_ratio", "thai_chars_leaked", "chinese_chars_leaked", "status"]
        for field in required_fields:
            self.assertIn(field, report)


if __name__ == '__main__':
    unittest.main()
