#!/usr/bin/env python3
"""Tests for src/training/dataset_builder.py — ChatML build + chapter split."""

import json
import tempfile
import unittest
from pathlib import Path

from src.training.dataset_builder import (
    to_chatml,
    build_splits,
    write_splits,
    SYSTEM_PROMPT,
)


def _pair(novel, ch, en, my):
    return {"novel": novel, "chapter_no": ch, "en_text": en, "my_text": my}


# A quality-passing EN→MY pair (Myanmar long enough, length ratio in band).
_EN = "He climbed the mountain and gazed at the distant capital city below."
_MY = "သူသည် တောင်ပေါ်သို့ တက်ပြီး အောက်ဘက်ရှိ ဝေးကွာသော မြို့တော်ကို ကြည့်လိုက်သည်။"


class TestToChatml(unittest.TestCase):
    def test_structure(self):
        rec = to_chatml(_EN, _MY)
        roles = [m["role"] for m in rec["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant"])
        self.assertEqual(rec["messages"][0]["content"], SYSTEM_PROMPT)
        self.assertIn("Translate to Myanmar", rec["messages"][1]["content"])
        self.assertEqual(rec["messages"][2]["content"], _MY)


class TestBuildSplits(unittest.TestCase):
    def test_holdout_chapters_go_to_test(self):
        pairs = []
        for ch in range(1, 11):  # chapters 1..10
            pairs.append(_pair("novelA", ch, _EN, _MY))
        splits = build_splits(pairs, holdout_chapters=3, val_fraction=0.0)
        # last 3 chapter numbers (8,9,10) → test (3 pairs); rest → train (7)
        self.assertEqual(len(splits["test"]), 3)
        self.assertEqual(len(splits["train"]), 7)

    def test_per_novel_holdout(self):
        pairs = []
        for ch in range(1, 6):
            pairs.append(_pair("A", ch, _EN, _MY))
            pairs.append(_pair("B", ch, _EN, _MY))
        splits = build_splits(pairs, holdout_chapters=2, val_fraction=0.0)
        # 2 holdout chapters per novel × 2 novels = 4 test pairs
        self.assertEqual(len(splits["test"]), 4)

    def test_val_fraction(self):
        pairs = [_pair("A", ch, _EN, _MY) for ch in range(1, 101)]
        splits = build_splits(pairs, holdout_chapters=10, val_fraction=0.1)
        # 90 train-pool pairs → 10% val = 9
        self.assertEqual(len(splits["val"]), 9)
        self.assertEqual(len(splits["train"]), 81)
        self.assertEqual(len(splits["test"]), 10)

    def test_quality_filter_drops_bad_pairs(self):
        good = _pair("A", 1, _EN, _MY)
        # Myanmar far too short vs English → omission, should be filtered out.
        bad = _pair("A", 2, _EN, "ဟုတ်")
        splits = build_splits([good, bad], holdout_chapters=0, val_fraction=0.0)
        self.assertEqual(len(splits["train"]), 1)

    def test_no_test_leakage_into_train(self):
        pairs = [_pair("A", ch, f"{_EN} {ch}", _MY) for ch in range(1, 6)]
        splits = build_splits(pairs, holdout_chapters=2, val_fraction=0.0)
        test_texts = {m["content"] for rec in splits["test"] for m in rec["messages"]}
        train_texts = {m["content"] for rec in splits["train"] for m in rec["messages"]}
        # user prompts differ per chapter; no overlap between train and test users
        self.assertTrue(test_texts.isdisjoint(train_texts - {SYSTEM_PROMPT,
                        splits["train"][0]["messages"][2]["content"]}))


class TestWriteSplits(unittest.TestCase):
    def test_writes_valid_jsonl(self):
        pairs = [_pair("A", ch, _EN, _MY) for ch in range(1, 6)]
        splits = build_splits(pairs, holdout_chapters=1, val_fraction=0.0)
        with tempfile.TemporaryDirectory() as d:
            counts = write_splits(splits, d)
            self.assertEqual(counts["test"], 1)
            train_file = Path(d) / "train.jsonl"
            self.assertTrue(train_file.exists())
            for line in train_file.read_text(encoding="utf-8").splitlines():
                obj = json.loads(line)  # must be valid JSON
                self.assertIn("messages", obj)


if __name__ == "__main__":
    unittest.main()
