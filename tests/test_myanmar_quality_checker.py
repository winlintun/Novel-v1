"""
Unit Tests for Myanmar Quality Checker.
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.myanmar_quality_checker import MyanmarQualityChecker


class TestMyanmarQualityChecker(unittest.TestCase):
    def setUp(self):
        self.checker = MyanmarQualityChecker()

    def test_check_quality_clean_text(self):
        """Test quality check with clean text."""
        text = "မြန်မာစာသားသည်ကိုဖတ်ပါတယ်။"
        result = self.checker.check_quality(text)
        self.assertGreaterEqual(result["score"], 70)
        self.assertTrue(result["passed"])

    def test_check_quality_with_archaic_words(self):
        """Test detection of archaic words."""
        text = "သင်သည်သည်ကို"
        result = self.checker.check_quality(text)
        self.assertLess(result["score"], 100)
        self.assertTrue(any("archaic" in i.lower() for i in result["issues"]))

    def test_check_quality_with_repetition(self):
        """Test detection of word repetition."""
        text = "သူ သူ သူ သူ သူ"
        result = self.checker.check_quality(text)
        self.assertTrue(any("repeated" in i.lower() for i in result["issues"]))

    def test_check_quality_particle_repetition(self):
        """Test detection of particle repetition."""
        text = "သည်သည်သည် ကိုကိုကို"
        result = self.checker.check_quality(text)
        self.assertTrue(any("repeated particle" in i.lower() for i in result["issues"]))

    def test_check_quality_long_sentence(self):
        """Test detection of too long sentences."""
        words = " ".join(["စာသား"] * 60)
        text = words + "။"
        result = self.checker.check_quality(text)
        self.assertTrue(any("too long" in i.lower() for i in result["issues"]))

    def test_check_quality_missing_ending(self):
        """Test detection of missing sentence ending."""
        text = "မြန်မာစာသား"
        result = self.checker.check_quality(text)
        self.assertTrue(any("ending" in i.lower() for i in result["issues"]))

    def test_check_quality_low_particles(self):
        """Test detection of low particle usage."""
        text = "စာသားစာသား"
        result = self.checker.check_quality(text)
        self.assertTrue(any("particle" in i.lower() for i in result["issues"]))

    def test_check_quality_unnatural_pattern(self):
        """Test detection of unnatural patterns."""
        text = "သည် နဲ့ သည် ကို ကို"
        result = self.checker.check_quality(text)
        self.assertTrue(any("repeated" in i.lower() for i in result["issues"]))

    def test_check_quality_too_much_english(self):
        """Test detection of too much English."""
        text = "word word word word word word word word word word word word"
        result = self.checker.check_quality(text)
        self.assertTrue(any("english" in i.lower() for i in result["issues"]))

    def test_check_quality_bengali_script(self):
        """Test detection of Bengali script leakage."""
        text = "test বাংলা test"
        result = self.checker.check_quality(text)
        self.assertTrue(any("bengali" in i.lower() for i in result["issues"]))

    def test_check_quality_mixed_tone(self):
        """Test detection of mixed tone/register."""
        text = "သည်ကို မင်း တယ်။"
        result = self.checker._check_tone(text)
        self.assertTrue(result["has_formal"])
        self.assertTrue(result["has_informal"])

    def test_check_quality_returns_all_fields(self):
        """Test all required fields are returned."""
        text = "မြန်မာစာ။"
        result = self.checker.check_quality(text)
        self.assertIn("score", result)
        self.assertIn("issues", result)
        self.assertIn("passed", result)
        self.assertIn("tone_check", result)
        self.assertIn("naturalness_score", result)

    def test_check_tone_formal_only(self):
        """Test tone check with formal register."""
        text = "သည်ကို အတွက် ဖြင့်၍"
        result = self.checker._check_tone(text)
        self.assertTrue(result["has_formal"])
        self.assertFalse(result["has_informal"])

    def test_check_tone_casual_only(self):
        """Test tone check with casual register."""
        text = "မင်း ဒီ အဲဒါ တယ်"
        result = self.checker._check_tone(text)
        self.assertTrue(result["has_informal"])
        self.assertFalse(result["has_formal"])

    def test_check_tone_consistent(self):
        """Test tone check with consistent register."""
        text = "သည်ကို ဖြင့်၍"
        result = self.checker._check_tone(text)
        self.assertTrue(result["tone_consistent"])

    def test_check_tone_paragraph_mixing(self):
        """Test register mixing within paragraphs."""
        text = "သည်ကို\n\nတယ်။"
        result = self.checker._check_tone(text)
        self.assertEqual(result["register_mixed_paragraphs"], 0)

    def test_check_tone_skip_quotes(self):
        """Test dialogue in quotes is skipped."""
        text = 'သည်ကို "မင်း ဒီ တယ်" ဖြင့်။'
        result = self.checker._check_tone(text)
        self.assertEqual(result["register_mixed_paragraphs"], 0)

    def test_check_archaic_words_all(self):
        """Test archaic word detection."""
        text = "သင်သည် ဤ ထို"
        result = self.checker._check_archaic_words(text)
        self.assertEqual(len(result), 3)

    def test_check_repetition_words(self):
        """Test word repetition detection."""
        text = "စာ စာ စာ"
        result = self.checker._check_repetition(text)
        self.assertTrue(len(result) > 0)

    def test_check_sentence_flow(self):
        """Test sentence flow checks."""
        text = " ".join(["စာ"] * 60) + "။"
        result = self.checker._check_sentence_flow(text)
        self.assertTrue(len(result) > 0)

    def test_check_particles(self):
        """Test particle usage check."""
        text = "သည်ကို မှာ"
        result = self.checker._check_particles(text)
        self.assertEqual(len(result), 0)

    def test_check_unnatural_phrasing_patterns(self):
        """Test unnatural pattern detection."""
        text = "သည် နဲ့ သည်"
        result = self.checker._check_unnatural_phrasing(text)
        self.assertTrue(len(result) > 0)

    def test_calculate_naturalness(self):
        """Test naturalness score calculation."""
        text = "မြန်မာစာ။"
        result = self.checker._calculate_naturalness(text)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 100)

    def test_calculate_naturalness_with_issues(self):
        """Test naturalness with quality issues."""
        text = "သင်သည် စာ စာ စာ သည်သည်သည်"
        result = self.checker._calculate_naturalness(text)
        self.assertLess(result, 100)

    def test_check_dialogue_tone(self):
        """Test dialogue tone check."""
        text = '"ကျွန်တော်" ဟုတ်ပါတယ်။'
        result = self.checker.check_dialogue_tone(text)
        self.assertIsInstance(result, list)

    def test_check_dialogue_tone_with_hierarchy(self):
        """Test dialogue with character hierarchy."""
        text = '"ကျွန်တော်" ဟုတ်ပါတယ်။'
        hierarchy = {"character": "superior"}
        result = self.checker.check_dialogue_tone(text, hierarchy)
        self.assertIsInstance(result, list)

    def test_suggest_improvements(self):
        """Test improvement suggestions."""
        text = "သင်သည်"
        result = self.checker.suggest_improvements(text)
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

    def test_check_quality_score_bounds(self):
        """Test score is bounded 0-100."""
        text = "သင်သည် သင်သည် စာ စာ စာ ကို ကို ကို ကို ကို သည်သည်သည်"
        result = self.checker.check_quality(text)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)


if __name__ == "__main__":
    unittest.main()