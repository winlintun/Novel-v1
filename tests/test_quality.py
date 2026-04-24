"""
Quality Tests for Novel Translation Project
Tests translation quality metrics: name consistency, Myanmar ratio, etc.

According to need_fix.md:
- BLEU Score (or similar metric)
- အမည်တူညီမူ ရာခိုင်နှုန်း (Name consistency percentage)
- Myanmar Unicode ratio
- Placeholder detection rate
"""

import unittest
import sys
import re
from pathlib import Path
from unittest.mock import Mock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.postprocessor import (
    myanmar_char_ratio,
    detect_language_leakage,
    validate_output,
)
from src.agents.checker import Checker
from src.memory.memory_manager import MemoryManager


class TestMyanmarUnicodeRatio(unittest.TestCase):
    """Test Myanmar Unicode character ratio metric."""
    
    def test_pure_myanmar_100_percent(self):
        """Test pure Myanmar text is 100%."""
        text = "မြန်မာဘာသာစကားဖြင့်ရေးသားထားသောစာသား"
        ratio = myanmar_char_ratio(text)
        self.assertEqual(ratio, 1.0)
    
    def test_mixed_myanmar_english(self):
        """Test mixed Myanmar-English text ratio."""
        # 50% Myanmar, 50% English (approximately)
        text = "မြန်မာ English မြန်မာ English"
        ratio = myanmar_char_ratio(text)
        self.assertGreater(ratio, 0.4)
        self.assertLess(ratio, 0.6)
    
    def test_low_myanmar_ratio_flagged(self):
        """Test very low Myanmar ratio is rejected."""
        text = "This is mostly English with a little မြန်မာ"
        report = validate_output(text, chapter=1)
        # Very low Myanmar ratio (<30%) should be REJECTED
        self.assertIn(report["status"], ["NEEDS_REVIEW", "REJECTED"])
        self.assertLess(report["myanmar_ratio"], 0.70)
    
    def test_high_myanmar_ratio_approved(self):
        """Test high Myanmar ratio is approved."""
        text = "မြန်မာဘာသာ စာသား တစ်ခု လုံလောက်သော အရှည်" * 5
        report = validate_output(text, chapter=1)
        self.assertEqual(report["status"], "APPROVED")
        self.assertGreaterEqual(report["myanmar_ratio"], 0.70)


class TestNameConsistencyMetric(unittest.TestCase):
    """Test name consistency percentage metric.
    
    အမည်တူညီမူ ရာခိုင်နှုန်း - Percentage of names translated consistently
    """
    
    def setUp(self):
        self.mock_memory = Mock(spec=MemoryManager)
        self.mock_memory.get_all_terms.return_value = [
            {"source": "罗青", "target": "လူချင်း"},
            {"source": "林渊", "target": "လင်ယွန်း"},
            {"source": "天龙城", "target": "ထျန်လုံမြို့"},
        ]
        self.checker = Checker(self.mock_memory)
    
    def test_perfect_name_consistency(self):
        """Test 100% name consistency when all names use glossary terms."""
        text = "လူချင်း နှင့် လင်ယွန်း သည် ထျန်လုံမြို့ သို့ သွားသည်"
        
        # Check for any untranslated source terms
        issues = self.checker.check_glossary_consistency(text)
        
        # Should have no issues (100% consistency)
        self.assertEqual(len(issues), 0)
    
    def test_partial_name_consistency(self):
        """Test partial consistency when some names not translated."""
        # Text with untranslated source term
        text = "罗青 နှင့် လင်ယွန်း သည် ထျန်လုံမြို့ သို့ သွားသည်"
        
        issues = self.checker.check_glossary_consistency(text)
        
        # Should detect the untranslated term
        self.assertGreater(len(issues), 0)
        self.assertEqual(issues[0]["term"], "罗青")
    
    def test_calculate_consistency_percentage(self):
        """Test calculating consistency percentage."""
        # Simulate text with some glossary terms and some issues
        text = "罗青 နှင့် လင်ယွန်း"  # 1 untranslated, 1 translated
        
        issues = self.checker.check_glossary_consistency(text)
        
        # With 2 names and 1 issue, consistency is 50%
        total_names = 2
        consistency_pct = ((total_names - len(issues)) / total_names) * 100
        self.assertEqual(consistency_pct, 50.0)


class TestLanguageLeakageMetrics(unittest.TestCase):
    """Test language leakage detection metrics."""
    
    def test_no_leakage_clean_text(self):
        """Test clean text has zero leakage."""
        text = "မြန်မာဘာသာ စာသား သန့်သန့်ရှင်းရှင်း"
        leakage = detect_language_leakage(text)
        
        self.assertEqual(leakage["thai_chars"], 0)
        self.assertEqual(leakage["chinese_chars"], 0)
    
    def test_thai_leakage_detected(self):
        """Test Thai characters are detected."""
        text = "မြန်မာစာ กรุงเทพฯ"
        leakage = detect_language_leakage(text)
        
        self.assertGreater(leakage["thai_chars"], 0)
        self.assertEqual(leakage["chinese_chars"], 0)
    
    def test_chinese_leakage_detected(self):
        """Test Chinese characters are detected."""
        text = "မြန်မာစာ 中文"
        leakage = detect_language_leakage(text)
        
        self.assertEqual(leakage["thai_chars"], 0)
        self.assertGreater(leakage["chinese_chars"], 0)
    
    def test_mixed_leakage_detected(self):
        """Test mixed leakage is detected."""
        text = "မြန်မာ 中文 กรุง"
        leakage = detect_language_leakage(text)
        
        self.assertGreater(leakage["thai_chars"], 0)
        self.assertGreater(leakage["chinese_chars"], 0)


class TestPlaceholderMetrics(unittest.TestCase):
    """Test placeholder detection metrics."""
    
    def count_placeholders(self, text: str) -> int:
        """Count 【?term?】 placeholders in text."""
        pattern = r'【\?[^】]+\?】'
        return len(re.findall(pattern, text))
    
    def test_no_placeholders_perfect_score(self):
        """Test text with no placeholders has perfect score."""
        text = "မြန်မာဘာသာ စာသား လုံလောက်သော အရှည်"
        count = self.count_placeholders(text)
        self.assertEqual(count, 0)
    
    def test_single_placeholder_detected(self):
        """Test single placeholder is detected."""
        text = "မြန်မာစာ 【?unknown?】 နောက်ထပ်"
        count = self.count_placeholders(text)
        self.assertEqual(count, 1)
    
    def test_multiple_placeholders_detected(self):
        """Test multiple placeholders are detected."""
        text = "【?term1?】 မြန်မာ 【?term2?】 စာ 【?term3?】"
        count = self.count_placeholders(text)
        self.assertEqual(count, 3)
    
    def test_placeholder_rate_calculation(self):
        """Test calculating placeholder rate per 1000 chars."""
        text = "မြန်မာစာ 【?term1?】 【?term2?】" * 50
        placeholder_count = self.count_placeholders(text)
        char_count = len(text)
        
        # Calculate rate per 1000 characters
        rate_per_1000 = (placeholder_count / char_count) * 1000
        
        # Lower is better (0 is perfect)
        self.assertGreater(rate_per_1000, 0)


class TestQualityScoreCalculation(unittest.TestCase):
    """Test overall quality score calculation."""
    
    def setUp(self):
        self.mock_memory = Mock(spec=MemoryManager)
        self.mock_memory.get_all_terms.return_value = []
        self.checker = Checker(self.mock_memory)
    
    def test_high_quality_score(self):
        """Test high-quality Myanmar text scores well."""
        # Good Myanmar text
        text = "မြန်မာဘာသာပြန်ချက်ကောင်းပါသည်။" * 20
        score = self.checker.calculate_quality_score(text)
        
        # Should be high quality (>= 90 for good Myanmar)
        self.assertGreaterEqual(score, 90)
    
    def test_low_quality_foreign_text(self):
        """Test non-Myanmar text scores poorly."""
        text = "This is mostly English text only, no Myanmar characters at all." * 5  # Make longer to avoid length penalty
        score = self.checker.calculate_quality_score(text)
        
        # Should be reduced due to low Myanmar ratio (< 0.5 subtracts 30)
        self.assertLess(score, 80)
    
    def test_error_marker_penalty(self):
        """Test error markers reduce quality score."""
        text = "[TRANSLATION ERROR: failed] မြန်မာစာ"
        score = self.checker.calculate_quality_score(text)
        
        # Error markers should significantly reduce score
        self.assertLess(score, 70)
    
    def test_replacement_char_detected(self):
        """Test replacement characters are detected in Unicode check."""
        text = "မြန်မာ�စာ" * 10  # Contains replacement char
        issues = self.checker.check_myanmar_unicode(text)
        
        # Replacement chars should be detected as Unicode issues
        self.assertGreater(len(issues), 0)
        self.assertTrue(any("replacement" in issue.lower() for issue in issues))


class TestQualityReport(unittest.TestCase):
    """Test comprehensive quality report generation."""
    
    def test_report_contains_all_metrics(self):
        """Test quality report contains all required metrics."""
        text = "မြန်မာဘာသာ စာသား"
        report = validate_output(text, chapter=1)
        
        required_fields = [
            "chapter",
            "myanmar_ratio",
            "thai_chars_leaked",
            "chinese_chars_leaked",
            "status"
        ]
        
        for field in required_fields:
            self.assertIn(field, report)
    
    def test_approved_status_criteria(self):
        """Test APPROVED status criteria."""
        # High Myanmar ratio, no Thai
        text = "မြန်မာဘာသာ" * 50
        report = validate_output(text, chapter=1)
        
        self.assertEqual(report["status"], "APPROVED")
        self.assertGreaterEqual(report["myanmar_ratio"], 0.70)
        self.assertEqual(report["thai_chars_leaked"], 0)
    
    def test_rejected_criteria_thai(self):
        """Test REJECTED status triggered by Thai leakage (critical error)."""
        text = "မြန်မာစာ กรุงเทพฯ"
        report = validate_output(text, chapter=1)

        self.assertEqual(report["status"], "REJECTED")

    def test_needs_review_criteria_low_ratio(self):
        """Test NEEDS_REVIEW triggered by moderately low Myanmar ratio (30-70%)."""
        # Create text with ~50% Myanmar ratio
        text = "မြန်မာစာ English here မြန်မာစာ more English words"
        report = validate_output(text, chapter=1)

        # Should be flagged, exact status depends on ratio calculation
        self.assertIn(report["status"], ["NEEDS_REVIEW", "REJECTED"])


class TestBleuScoreApproximation(unittest.TestCase):
    """Test BLEU-like score approximation for translation quality.
    
    Note: Full BLEU requires reference translation.
    These tests use simple n-gram overlap as approximation.
    """
    
    def calculate_ngram_overlap(self, reference: str, candidate: str, n: int = 2) -> float:
        """Calculate simple n-gram overlap score."""
        def get_ngrams(text, n):
            words = text.split()
            return set(tuple(words[i:i+n]) for i in range(len(words)-n+1))
        
        ref_ngrams = get_ngrams(reference, n)
        cand_ngrams = get_ngrams(candidate, n)
        
        if not ref_ngrams:
            return 0.0
        
        overlap = len(ref_ngrams & cand_ngrams)
        return overlap / len(ref_ngrams)
    
    def test_perfect_overlap(self):
        """Test identical texts have perfect overlap."""
        text = "မြန်မာ စာ သား"
        score = self.calculate_ngram_overlap(text, text, n=2)
        self.assertEqual(score, 1.0)
    
    def test_partial_overlap(self):
        """Test partial overlap score."""
        ref = "မြန်မာ စာ သား"
        cand = "မြန်မာ စာ တည်း"
        score = self.calculate_ngram_overlap(ref, cand, n=2)
        
        # Should have partial overlap
        self.assertGreater(score, 0)
        self.assertLess(score, 1.0)
    
    def test_no_overlap(self):
        """Test completely different texts have zero overlap."""
        ref = "မြန်မာ စာ"
        cand = "English words"
        score = self.calculate_ngram_overlap(ref, cand, n=2)
        self.assertEqual(score, 0.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
