#!/usr/bin/env python3
"""Tests for src/utils/translation_reviewer.py"""

import unittest
import os
import tempfile
from pathlib import Path

from src.utils.translation_reviewer import (
    _check_myanmar_ratio,
    _check_foreign_scripts,
    _check_latin_leakage,
    _check_markdown_structure,
    _check_content_completeness,
    _check_paragraph_structure,
    _check_archaic_words,
    _check_particle_repetition,
    _check_register_consistency,
    _check_sentence_enders,
    _check_overlong_sentences,
    _check_paragraph_duplication,
    review_translation,
    save_review_report,
    CheckResult,
    ReviewReport,
)


class TestMyanmarRatio(unittest.TestCase):
    def test_pure_myanmar_passes(self):
        r = _check_myanmar_ratio("မင်္ဂလာပါ သူငယ်ချင်း")
        self.assertTrue(r.passed)
        self.assertEqual(r.score_deduction, 0)

    def test_english_fails(self):
        r = _check_myanmar_ratio("Hello world this is English text that has no Myanmar chars at all just zeros")
        self.assertFalse(r.passed)
        self.assertGreater(r.score_deduction, 0)

    def test_empty_text(self):
        r = _check_myanmar_ratio("")
        self.assertFalse(r.passed)


class TestForeignScripts(unittest.TestCase):
    def test_clean_text(self):
        results = _check_foreign_scripts("မြန်မာစာသား")
        for r in results:
            self.assertTrue(r.passed)

    def test_chinese_leakage(self):
        results = _check_foreign_scripts("မြန်မာ 中文 text")
        chinese_check = [r for r in results if "Chinese" in r.name][0]
        self.assertFalse(chinese_check.passed)

    def test_bengali_leakage(self):
        results = _check_foreign_scripts("မြန်မা গ text")
        bengali_check = [r for r in results if "Bengali" in r.name][0]
        self.assertFalse(bengali_check.passed)


class TestLatinLeakage(unittest.TestCase):
    def test_no_latin(self):
        r = _check_latin_leakage("မြန်မာစာသားတွေပဲ")
        self.assertTrue(r.passed)

    def test_some_latin_words(self):
        r = _check_latin_leakage("မြန်မာ text with some english words here and there and some more to exceed five")
        self.assertFalse(r.passed)


class TestMarkdownStructure(unittest.TestCase):
    def test_one_h1(self):
        results = _check_markdown_structure("# အခန်း ၁\n\n## Title\n\nBody text")
        h1_check = [r for r in results if "H1" in r.name][0]
        self.assertTrue(h1_check.passed)

    def test_balanced_bold(self):
        results = _check_markdown_structure("Text **bold** more **bold**")
        bold_check = [r for r in results if "Bold" in r.name][0]
        self.assertTrue(bold_check.passed)

    def test_unbalanced_bold(self):
        results = _check_markdown_structure("Text **bold")
        bold_check = [r for r in results if "Bold" in r.name][0]
        self.assertFalse(bold_check.passed)


class TestContentCompleteness(unittest.TestCase):
    def test_short_text_fails(self):
        r = _check_content_completeness("Short")
        self.assertFalse(r.passed)

    def test_long_text_passes(self):
        r = _check_content_completeness("A" * 200 + " မြန်မာ")
        self.assertTrue(r.passed)


class TestParagraphStructure(unittest.TestCase):
    def test_no_breaks_fails(self):
        r = _check_paragraph_structure("Line one\nLine two\nLine three")
        self.assertFalse(r.passed)

    def test_with_breaks_passes(self):
        r = _check_paragraph_structure("Para one.\n\nPara two.\n\nPara three.")
        self.assertTrue(r.passed)


class TestArchaicWords(unittest.TestCase):
    def test_no_archaic(self):
        r = _check_archaic_words("မင်း ဒီ အဲဒါ အဲဒီ")
        self.assertTrue(r.passed)

    def test_archaic_found(self):
        r = _check_archaic_words("\u101e\u1004\u103a\u101e\u100a\u103a \u1024")  # သင်သည် ဤ
        self.assertFalse(r.passed)


class TestParticleRepetition(unittest.TestCase):
    def test_no_repetition(self):
        r = _check_particle_repetition("သူသည် ထမင်းကို စားသည်။")
        self.assertTrue(r.passed)

    def test_same_particle_repeated(self):
        r = _check_particle_repetition("သည်သည်သည်သည်")
        self.assertFalse(r.passed)

    def test_different_particles_not_flag(self):
        r = _check_particle_repetition("သည်ကိုမှာအတွက်ဖြင့်")
        self.assertTrue(r.passed)


class TestRegisterConsistency(unittest.TestCase):
    def test_single_register(self):
        r = _check_register_consistency("သူသည် ထမင်းကို စားသည်။")
        self.assertTrue(r.passed)

    def test_mixed_register(self):
        r = _check_register_consistency("သူသည် ထမင်းကို စားသည်။ စားတယ် သောက်ဘူး လုပ်မယ်ရဲ့။")
        self.assertFalse(r.passed)


class TestSentenceEnders(unittest.TestCase):
    def test_all_ended(self):
        r = _check_sentence_enders("စာသား။\nနောက်စာသား၏")
        self.assertTrue(r.passed)

    def test_unended_lines(self):
        r = _check_sentence_enders("စာသား\nနောက်စာသား\nတတိယ\nစတုတ္ထ\nပဉ္စမ")
        self.assertFalse(r.passed)


class TestOverlongSentences(unittest.TestCase):
    def test_short_sentences(self):
        r = _check_overlong_sentences("Short sentence။ Another short။")
        self.assertTrue(r.passed)

    def test_overlong_detected(self):
        long_words = " ".join(["စကားလုံး"] * 60)
        r = _check_overlong_sentences(f"{long_words}။")
        self.assertFalse(r.passed)


class TestParagraphDuplication(unittest.TestCase):
    def test_no_duplication(self):
        r = _check_paragraph_duplication("Para one။\n\nPara two။")
        self.assertTrue(r.passed)

    def test_single_paragraph(self):
        r = _check_paragraph_duplication("Only one para။")
        self.assertTrue(r.passed)


class TestReviewReport(unittest.TestCase):
    def test_add_check_pass(self):
        report = ReviewReport("test.mm.md", "test", 1, "single_stage", "padauk", 10)
        report.add_check(CheckResult("Test", True, 0, "OK"))
        self.assertEqual(report.total_score, 100)

    def test_add_check_fail(self):
        report = ReviewReport("test.mm.md", "test", 1, "single_stage", "padauk", 10)
        report.add_check(CheckResult("Test", False, 15, "Bad", "WARNING"))
        self.assertEqual(report.total_score, 85)

    def test_add_check_critical(self):
        report = ReviewReport("test.mm.md", "test", 1, "single_stage", "padauk", 10)
        report.add_check(CheckResult("Test", False, 10, "Bad", "CRITICAL"))
        self.assertEqual(len(report.critical_fixes), 1)

    def test_score_floor(self):
        report = ReviewReport("test.mm.md", "test", 1, "single_stage", "padauk", 10)
        report.add_check(CheckResult("T1", False, 60, "Bad", "CRITICAL"))
        report.add_check(CheckResult("T2", False, 60, "Bad", "CRITICAL"))
        self.assertEqual(report.total_score, 0)


class TestReviewTranslationIntegration(unittest.TestCase):
    def test_review_good_file(self):
        """Test review on a well-formatted Myanmar file."""
        good_text = "# အခန်း ၁\n\n## ခေါင်းစဉ်\n\nသူသည် တောင်ပေါ်သို့ တက်သွားသည်။\n\nနောက်တစ်နေ့တွင် မိုးရွာခဲ့သည်။"
        with tempfile.NamedTemporaryFile(suffix='.mm.md', mode='w', encoding='utf-8-sig', delete=False) as f:
            f.write(good_text)
            f.flush()
            report = review_translation(f.name, chapter=1, novel="test")
        os.unlink(f.name)
        self.assertGreaterEqual(report.total_score, 70)
        self.assertLess(len(report.critical_fixes), 3)

    def test_save_report_utf8sig(self):
        """Test report is saved with UTF-8-SIG encoding."""
        report = ReviewReport("test.mm.md", "test", 1, "single_stage", "padauk", 10)
        report.add_check(CheckResult("Myanmar Ratio", True, 0, "98%"))
        report.passed_checks.append("Test check")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_review_report(report, report_dir=tmpdir)
            self.assertTrue(Path(path).exists())
            content = Path(path).read_bytes()
            self.assertTrue(content.startswith(b'\xef\xbb\xbf'), "Should have BOM for utf-8-sig")


if __name__ == "__main__":
    unittest.main()
