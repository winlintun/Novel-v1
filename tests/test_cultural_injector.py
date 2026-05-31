"""
Unit tests for the cultural_injector module.
Tests that structured cultural rule dicts are correctly matched at runtime.
"""

import unittest
from src.utils.cultural_injector import build_cultural_injection


class TestCulturalInjectionCN(unittest.TestCase):
    """Chinese → Myanmar cultural rule injection tests."""

    def test_cn_vocab_match_annotated(self):
        """Chinese term with parenthetical annotation matches correctly."""
        r = build_cultural_injection("魔头", "chinese")
        self.assertIn("VOCABULARY PRECISION", r)

    def test_cn_vocab_match_clean(self):
        """Chinese term without annotation matches correctly."""
        r = build_cultural_injection("纯洁", "chinese")
        self.assertIn("VOCABULARY PRECISION", r)

    def test_cn_idiom_match(self):
        """Chinese idiom found in source text."""
        r = build_cultural_injection("一石二鸟", "chinese")
        self.assertIn("IDIOMS", r)

    def test_cn_honorific_match(self):
        """Chinese honorific found in source text."""
        r = build_cultural_injection("师父", "chinese")
        self.assertIn("HONORIFICS", r)

    def test_cn_no_match(self):
        """Unrelated Chinese text returns empty."""
        r = build_cultural_injection("今天天气很好", "chinese")
        self.assertEqual(r, "")


class TestCulturalInjectionEN(unittest.TestCase):
    """English → Myanmar cultural rule injection tests."""

    def test_en_vocab_demon(self):
        """EN demon term matches via 'english' key."""
        r = build_cultural_injection("demon", "english")
        self.assertIn("VOCABULARY PRECISION", r)

    def test_en_vocab_purity(self):
        """EN purity term matches via 'english' key."""
        r = build_cultural_injection("purity", "english")
        self.assertIn("VOCABULARY PRECISION", r)

    def test_en_vocab_hate(self):
        """EN hate term matches via 'english' key (stemmed from 'hated')."""
        r = build_cultural_injection("hate", "english")
        self.assertIn("VOCABULARY PRECISION", r)

    def test_en_idiom_match(self):
        """EN idiom matches via keyword extraction."""
        r = build_cultural_injection("tango", "english")
        self.assertIn("IDIOMS", r)

    def test_en_cultivation_terms(self):
        """Cultivation terms from CULTURAL_RULES match."""
        r = build_cultural_injection("Golden Core cultivation Sect", "english")
        self.assertIn("CULTIVATION TERMS", r)
        self.assertIn("ရွှေဘောလုံး", r)

    def test_en_measure_words(self):
        """Measure words from CULTURAL_RULES match."""
        r = build_cultural_injection("The people and animals", "english")
        self.assertIn("MEASURE WORDS", r)
        self.assertIn("ယောက်", r)
        self.assertIn("ကောင်", r)

    def test_en_no_match(self):
        """Unrelated English text returns empty."""
        r = build_cultural_injection("The weather is nice today", "english")
        self.assertEqual(r, "")


class TestEdgeCases(unittest.TestCase):
    """Edge cases and guards."""

    def test_none_text(self):
        """None text returns empty string."""
        self.assertEqual(build_cultural_injection(None, "chinese"), "")

    def test_empty_text(self):
        """Empty text returns empty string."""
        self.assertEqual(build_cultural_injection("", "chinese"), "")

    def test_whitespace_text(self):
        """Whitespace-only text returns empty string."""
        self.assertEqual(build_cultural_injection("   ", "english"), "")

    def test_short_text_no_match(self):
        """Very short text with no keywords returns empty."""
        r = build_cultural_injection("a", "english")
        self.assertEqual(r, "")

    def test_mixed_lang_no_false_positive(self):
        """Myanmar text with no matching terms returns empty."""
        r = build_cultural_injection("မြန်မာစာကို ဘာသာပြန်ပါတယ်", "chinese")
        self.assertEqual(r, "")
