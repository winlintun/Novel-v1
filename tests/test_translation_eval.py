#!/usr/bin/env python3
"""Tests for src/utils/translation_eval.py — chrF reference-based evaluation."""

import unittest

from src.utils.translation_eval import (
    strip_for_eval,
    compute_chrf,
    evaluate_corpus,
    _chapter_no,
)

try:
    import sacrebleu  # noqa: F401
    _HAS_SACREBLEU = True
except Exception:
    _HAS_SACREBLEU = False


class TestHelpers(unittest.TestCase):
    def test_strip_removes_headings(self):
        out = strip_for_eval("# အခန်း ၁\n\nသူသည် လာသည်။")
        self.assertNotIn("#", out)
        self.assertIn("သူသည်", out)

    def test_chapter_number_parsing(self):
        self.assertEqual(_chapter_no("a-will-eternal_chapter_001.md"), 1)
        self.assertEqual(_chapter_no("a-will-eternal_chapter_0001.md"), 1)
        self.assertIsNone(_chapter_no("intro.md"))


@unittest.skipUnless(_HAS_SACREBLEU, "sacrebleu not installed")
class TestChrf(unittest.TestCase):
    def test_identical_is_perfect(self):
        text = "သူသည် တောင်ပေါ်သို့ တက်သွားပြီး မြို့တော်ကို ကြည့်လိုက်သည်။"
        self.assertAlmostEqual(compute_chrf(text, text), 100.0, places=1)

    def test_different_is_lower(self):
        a = "သူသည် တောင်ပေါ်သို့ တက်သွားသည်။"
        b = "မိုးရွာနေသော ညဥ့်တွင် ငှက်များ အသံပြုကြသည်။"
        self.assertLess(compute_chrf(a, b), 60.0)

    def test_partial_overlap_is_middling(self):
        ref = "သူသည် တောင်ပေါ်သို့ တက်သွားပြီး မြို့တော်ကို ကြည့်လိုက်သည်။"
        hyp = "သူသည် တောင်ပေါ်သို့ တက်သွားသည်။"  # shorter, same opening
        score = compute_chrf(hyp, ref)
        self.assertGreater(score, 30.0)
        self.assertLess(score, 100.0)

    def test_corpus_aggregates(self):
        hyps = ["သူသည် လာသည်။", "မိုးရွာသည်။"]
        refs = ["သူသည် လာသည်။", "မိုးရွာသည်။"]
        out = evaluate_corpus(hyps, refs)
        self.assertTrue(out["checked"])
        self.assertEqual(out["n"], 2)
        self.assertAlmostEqual(out["corpus_chrf"], 100.0, places=1)


if __name__ == "__main__":
    unittest.main()
