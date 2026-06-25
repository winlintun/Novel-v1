#!/usr/bin/env python3
"""Tests for src/utils/glossary_ranking.py — per-chunk relevance ranking."""

import unittest

from src.utils.glossary_ranking import (
    in_chunk_frequency,
    rank_terms_by_relevance,
)


def _term(source, category="general", chapter=None):
    return {"source_term": source, "category": category, "chapter_first_seen": chapter}


class TestInChunkFrequency(unittest.TestCase):
    def test_counts_occurrences_case_insensitive(self):
        text = "Bai Xiaochun met Bai Xiaochun again, BAI XIAOCHUN smiled."
        self.assertEqual(in_chunk_frequency(text, _term("Bai Xiaochun")), 3)

    def test_short_source_ignored(self):
        self.assertEqual(in_chunk_frequency("a a a", _term("a")), 0)


class TestRankTermsByRelevance(unittest.TestCase):
    def test_characters_come_first(self):
        text = "The sword sect elder spoke about the sword and the sect."
        terms = [
            _term("sword", "object", chapter=1),
            _term("elder", "character", chapter=5),
        ]
        ranked = rank_terms_by_relevance(text, terms)
        self.assertEqual(ranked[0]["source_term"], "elder")  # character wins

    def test_in_chunk_frequency_breaks_within_category(self):
        # Both non-character; the one mentioned more in the chunk ranks higher
        # even though it was introduced in a LATER chapter.
        text = "spirit spirit spirit stone"
        terms = [
            _term("stone", "object", chapter=1),   # 1 mention, early chapter
            _term("spirit", "object", chapter=9),  # 3 mentions, late chapter
        ]
        ranked = rank_terms_by_relevance(text, terms)
        self.assertEqual(ranked[0]["source_term"], "spirit")

    def test_limit_keeps_most_relevant(self):
        text = "dragon dragon dragon phoenix tiger"
        terms = [
            _term("tiger", "object", chapter=1),
            _term("phoenix", "object", chapter=1),
            _term("dragon", "object", chapter=8),
        ]
        ranked = rank_terms_by_relevance(text, terms, limit=1)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["source_term"], "dragon")  # most relevant survives the cut

    def test_does_not_mutate_input(self):
        terms = [_term("a-term", "object", 1), _term("b-term", "object", 2)]
        before = list(terms)
        rank_terms_by_relevance("a-term b-term", terms)
        self.assertEqual(terms, before)

    def test_chapter_tiebreak_when_equal_frequency(self):
        # Equal frequency (both once) → earlier chapter wins.
        text = "alpha beta"
        terms = [
            _term("beta", "object", chapter=9),
            _term("alpha", "object", chapter=2),
        ]
        ranked = rank_terms_by_relevance(text, terms)
        self.assertEqual(ranked[0]["source_term"], "alpha")


if __name__ == "__main__":
    unittest.main()
