#!/usr/bin/env python3
"""Tests for src/utils/myanmar_syllable.py — rule-based syllable segmentation."""

import unittest

from src.utils.myanmar_syllable import (
    segment_syllables,
    count_syllables,
    syllable_length,
)


class TestSegmentSyllables(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(segment_syllables(""), [])

    def test_simple_word(self):
        # မြန်မာ = "Myanmar" → two syllables မြန် / မာ
        self.assertEqual(segment_syllables("မြန်မာ"), ["မြန်", "မာ"])

    def test_coda_consonant_not_split(self):
        # ကင်း (kin) is ONE syllable: the င is a coda (followed by asat), not an onset.
        self.assertEqual(segment_syllables("ကင်း"), ["ကင်း"])

    def test_two_syllables_with_codas(self):
        # ကင်ပွန်း → ကင် / ပွန်း
        self.assertEqual(segment_syllables("ကင်ပွန်း"), ["ကင်", "ပွန်း"])

    def test_stacked_cluster_stays_together(self):
        # မန္တလေး (Mandalay): the ္ stacks တ onto န → မန္တ / လေး
        self.assertEqual(segment_syllables("မန္တလေး"), ["မန္တ", "လေး"])

    def test_medial_stays_attached(self):
        # ကြ (k + medial ra) is one syllable
        self.assertEqual(segment_syllables("ကြီး"), ["ကြီး"])

    def test_latin_run_is_single_token(self):
        toks = segment_syllables("abcမာ")
        self.assertIn("abc", toks)
        self.assertIn("မာ", toks)


class TestCounts(unittest.TestCase):
    def test_count_syllables_myanmar_only(self):
        self.assertEqual(count_syllables("မြန်မာ"), 2)

    def test_count_excludes_latin(self):
        # Latin token is not a Myanmar syllable
        self.assertEqual(count_syllables("hello မာ"), 1)

    def test_syllable_length_mixes_words_and_syllables(self):
        # 2 Myanmar syllables + 2 English words
        self.assertEqual(syllable_length("the cat မြန်မာ"), 4)

    def test_length_empty(self):
        self.assertEqual(syllable_length(""), 0)
        self.assertEqual(count_syllables(""), 0)


if __name__ == "__main__":
    unittest.main()
