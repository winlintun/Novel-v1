#!/usr/bin/env python3
"""Tests for the new output-quality algorithm modules:
compression degeneration, content alignment (fallback path), name clustering.
"""

import unittest

from src.utils.postprocessor import detect_compression_degeneration
from src.utils.content_alignment import (
    find_dropped_content,
    split_source_sentences,
    split_target_sentences,
)
from src.utils.name_clustering import (
    extract_name_candidates,
    cluster_name_variants,
)


class TestCompressionDegeneration(unittest.TestCase):
    def test_short_text_not_checked(self):
        r = detect_compression_degeneration("မြန်မာ")
        self.assertFalse(r["checked"])
        self.assertFalse(r["degenerate"])

    def test_natural_prose_not_degenerate(self):
        # Varied, NON-duplicated Myanmar prose (~0.33 ratio) must not be flagged.
        para = (
            "သူသည် တောင်ပေါ်သို့ တက်သွားပြီး ဝေးကွာသော မြို့တော်ကို လှမ်းကြည့်လိုက်သည်။ "
            "လေပြင်းတိုက်ခတ်နေသော်လည်း သူ၏ စိတ်ဓာတ်မှာ ကြံ့ခိုင်လျက်ရှိ၏။ "
            "နောက်တစ်နေ့တွင် ခရီးဆက်ရန် ပြင်ဆင်ထားသည်။ ထိုညတွင် ကြယ်များ တောက်ပနေသည်။ "
            "မြစ်ရေသည် တိတ်ဆိတ်စွာ စီးဆင်းနေပြီး ငှက်များ အသံပြုနေကြသည်။ "
            "သူ၏ ရင်ထဲတွင် မျှော်လင့်ချက်သစ်များ ဖြစ်ပေါ်လာသည်။"
        )
        r = detect_compression_degeneration(para)
        self.assertTrue(r["checked"])
        self.assertFalse(r["severe"])
        self.assertFalse(r["degenerate"])

    def test_looping_text_flagged_severe(self):
        # A pathological loop compresses extremely well.
        loop = "ထို့နောက် သူသည် ပြန်လာသည်။ " * 60
        r = detect_compression_degeneration(loop)
        self.assertTrue(r["checked"])
        self.assertTrue(r["severe"])
        self.assertTrue(r["degenerate"])


class TestContentAlignmentFallback(unittest.TestCase):
    def test_sentence_splitters(self):
        src = "He walked away. She stayed behind! Why did they leave?"
        self.assertEqual(len(split_source_sentences(src)), 3)
        tgt = "သူ ထွက်သွားသည်။ သူမ ကျန်ရစ်ခဲ့သည်။"
        self.assertEqual(len(split_target_sentences(tgt)), 2)

    def test_graceful_fallback_without_embedder(self):
        # Passing a None embedder that also can't be loaded → checked=False, no crash.
        r = find_dropped_content(
            "He walked away slowly into the night.",
            "သူ ညဘက်ထဲသို့ ဖြည်းဖြည်းချင်း လျှောက်သွားသည်။",
            embedder=_FailingEmbedder(),
        )
        self.assertFalse(r["checked"])
        self.assertEqual(r["dropped"], [])

    def test_with_fake_embedder_detects_drop(self):
        # Fake embedder: identical sentences → sim 1.0; unmatched source → low sim.
        emb = _KeywordEmbedder()
        src = "The dragon roared loudly. The hero drew his sword bravely."
        # Translation only covers the first sentence.
        tgt = "နဂါးသည် ကျယ်လောင်စွာ ဟောက်လိုက်သည်။"
        r = find_dropped_content(src, tgt, embedder=emb, threshold=0.5)
        self.assertTrue(r["checked"])
        self.assertLess(r["coverage"], 1.0)
        self.assertGreaterEqual(len(r["dropped"]), 1)


class TestNameClustering(unittest.TestCase):
    def test_extract_candidates(self):
        text = "ပိုင်ရှောင်ချန်းသည် လာသည်။ ပိုင်ရှောင်ချီက ပြောသည်။"
        cands = extract_name_candidates(text)
        self.assertIn("ပိုင်ရှောင်ချန်း", cands)
        self.assertIn("ပိုင်ရှောင်ချီ", cands)

    def test_variant_maps_to_frequent_form(self):
        # Canonical spelling appears twice, variant once → variant maps to canonical.
        text = (
            "ပိုင်ရှောင်ချန်းသည် လာသည်။ "
            "ပိုင်ရှောင်ချီက ပြောသည်။ "
            "ပိုင်ရှောင်ချန်းကို မြင်သည်။"
        )
        vmap = cluster_name_variants(text)
        self.assertEqual(vmap.get("ပိုင်ရှောင်ချီ"), "ပိုင်ရှောင်ချန်း")

    def test_glossary_target_wins_as_canonical(self):
        text = (
            "ပိုင်ရှောင်ချီသည် လာသည်။ "
            "ပိုင်ရှောင်ချီက ပြောသည်။ "
            "ပိုင်ရှောင်ချန်းကို မြင်သည်။"
        )
        glossary = [{"category": "character", "target_term": "ပိုင်ရှောင်ချန်း"}]
        vmap = cluster_name_variants(text, glossary)
        # Even though the variant is more frequent, the glossary target is canonical.
        self.assertEqual(vmap.get("ပိုင်ရှောင်ချီ"), "ပိုင်ရှောင်ချန်း")

    def test_unrelated_words_not_merged(self):
        text = "မောင်မောင်သည် လာသည်။ ကျောင်းသားက ပြောသည်။"
        vmap = cluster_name_variants(text)
        self.assertEqual(vmap, {})


# ── Test doubles for content alignment ──────────────────────────────

class _FailingEmbedder:
    def encode(self, texts):
        raise RuntimeError("model unavailable")


class _KeywordEmbedder:
    """Tiny deterministic embedder: bag-of-keywords cosine in a shared space.

    Maps a few EN/MY keyword pairs to the same axis so an aligned sentence pair
    scores high and an unmatched source sentence scores ~0 — enough to exercise
    find_dropped_content without the real BGE-M3 model.
    """
    # axis index per concept; EN and MY keywords share an axis.
    _VOCAB = {
        "dragon": 0, "roared": 1, "loudly": 2,
        "နဂါး": 0, "ဟောက်": 1, "ကျယ်လောင်": 2,
        "hero": 3, "sword": 4, "bravely": 5,
    }

    def encode(self, texts):
        import numpy as np
        dim = 6
        vecs = []
        for t in texts:
            v = np.zeros(dim, dtype=float)
            for kw, ax in self._VOCAB.items():
                if kw in t:
                    v[ax] += 1.0
            n = np.linalg.norm(v)
            if n > 0:
                v = v / n
            vecs.append(v)
        return np.asarray(vecs)


if __name__ == "__main__":
    unittest.main()
