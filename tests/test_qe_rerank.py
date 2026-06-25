#!/usr/bin/env python3
"""Tests for src/utils/qe_rerank.py — QE re-ranking / best-of-N selection."""

import unittest

from src.utils.qe_rerank import score_candidate, select_best, generate_and_select

# A clean, fluent Myanmar paragraph (varied vocabulary, proper enders).
GOOD = (
    "သူသည် တောင်ပေါ်သို့ တက်သွားပြီး ဝေးကွာသော မြို့တော်ကို လှမ်းကြည့်လိုက်သည်။ "
    "လေပြင်းတိုက်ခတ်နေသော်လည်း သူ၏ စိတ်ဓာတ်မှာ ကြံ့ခိုင်လျက်ရှိ၏။ "
    "နောက်တစ်နေ့တွင် ခရီးဆက်ရန် ပြင်ဆင်ထားသည်။"
)
SOURCE = (
    "He climbed up the mountain and gazed at the distant capital city. "
    "Though a strong wind was blowing, his spirit remained firm. "
    "The next day, he prepared to continue his journey."
)


class TestScoreCandidate(unittest.TestCase):
    def test_empty_is_zero(self):
        s = score_candidate(SOURCE, "")
        self.assertEqual(s["score"], 0.0)

    def test_placeholder_penalised(self):
        good = score_candidate(SOURCE, GOOD)["score"]
        bad = score_candidate(SOURCE, GOOD + " ?? ?? ??")["score"]
        self.assertLess(bad, good)

    def test_chinese_leak_penalised(self):
        good = score_candidate(SOURCE, GOOD)["score"]
        leaked = score_candidate(SOURCE, GOOD + " 修炼者 出现了")["score"]
        self.assertLess(leaked, good)

    def test_loop_penalised(self):
        loop = "ထို့နောက် သူသည် ပြန်လာသည်။ " * 40
        self.assertLess(score_candidate(SOURCE, loop)["score"],
                        score_candidate(SOURCE, GOOD)["score"])

    def test_adequacy_raises_score(self):
        low = score_candidate(SOURCE, GOOD, adequacy=0.2)["score"]
        high = score_candidate(SOURCE, GOOD, adequacy=0.95)["score"]
        self.assertGreater(high, low)


class TestSelectBest(unittest.TestCase):
    def test_picks_clean_over_leaked(self):
        leaked = GOOD + " 出现 dragon network platform system"
        idx, scored = select_best(SOURCE, [leaked, GOOD])
        self.assertEqual(idx, 1)
        self.assertEqual(len(scored), 2)

    def test_picks_complete_over_truncated(self):
        truncated = "သူသည် တောင်ပေါ်သို့ တက်သွားပြီး ဝေးကွာသော မြို့တော်ကို လှမ်းကြ"
        idx, _ = select_best(SOURCE, [truncated, GOOD])
        self.assertEqual(idx, 1)

    def test_empty_candidates(self):
        idx, scored = select_best(SOURCE, [])
        self.assertEqual(idx, -1)
        self.assertEqual(scored, [])

    def test_adequacy_breaks_tie_between_similar(self):
        # Two near-identical clean candidates; the one with higher adequacy wins.
        idx, _ = select_best(SOURCE, [GOOD, GOOD], adequacies=[0.3, 0.9])
        self.assertEqual(idx, 1)


class TestGenerateAndSelect(unittest.TestCase):
    def test_drives_generate_fn_and_picks_best(self):
        leaked = GOOD + " 出现了 system platform"
        candidates = [leaked, GOOD, ""]
        out = generate_and_select(SOURCE, lambda i: candidates[i], n=3)
        self.assertEqual(out["best"], GOOD)
        self.assertEqual(out["best_index"], 1)
        self.assertEqual(len(out["scored"]), 3)

    def test_handles_generation_exception(self):
        def gen(i):
            if i == 0:
                raise RuntimeError("model failed")
            return GOOD

        out = generate_and_select(SOURCE, gen, n=2)
        self.assertEqual(out["best"], GOOD)
        self.assertEqual(out["best_index"], 1)

    def test_single_candidate(self):
        out = generate_and_select(SOURCE, lambda i: GOOD, n=1)
        self.assertEqual(out["best"], GOOD)
        self.assertEqual(out["best_index"], 0)


if __name__ == "__main__":
    unittest.main()
