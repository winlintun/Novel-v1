"""Relevance ranking for per-chunk glossary injection.

The memory layer already selects only glossary terms whose source appears in the
current chunk (text-aware injection) — a big win over a fixed chapter-wide
top-20. But when *more* terms match than the prompt budget allows, the surviving
set was chosen by metadata order (character-first, then chapter-introduced),
which ignores how relevant each term is to *this* chunk: a name mentioned five
times here could be dropped in favour of an early-chapter term mentioned once.

This module adds the missing signal — in-chunk frequency — while preserving the
deliberate design choices:

  1. character terms first (name-spelling consistency is the highest-value job),
  2. then most-mentioned-in-this-chunk (relevance),
  3. then earliest chapter_first_seen (established worldbuilding / consistency),
  4. then longer source term (more specific, less likely an incidental match).

So the cut keeps the terms the chunk actually leans on. Pure ranking — no I/O,
fully deterministic and testable.
"""

from __future__ import annotations

from typing import Optional


def _source_of(term: dict) -> str:
    return (term.get("source_term") or term.get("source") or "").strip()


def in_chunk_frequency(source_text: str, term: dict) -> int:
    """How many times the term's source token occurs in ``source_text`` (ci)."""
    s = _source_of(term).lower()
    if len(s) < 2:
        return 0
    return source_text.lower().count(s)


def rank_terms_by_relevance(
    source_text: str,
    terms: list[dict],
    limit: Optional[int] = None,
    *,
    prioritize_characters: bool = True,
) -> list[dict]:
    """Rank glossary ``terms`` for a chunk and optionally truncate to ``limit``.

    Args:
        source_text: The source chunk the terms will be injected for.
        terms: Glossary rows already filtered to those present in the chunk.
        limit: Keep at most this many (None / ≤0 = keep all).
        prioritize_characters: Keep character terms ahead of others (name
            consistency). Set False for a purely relevance-driven order.

    Returns:
        A new sorted (and possibly truncated) list; the input is not mutated.
    """
    src = source_text or ""

    def key(t: dict):
        is_char = 0 if (prioritize_characters and t.get("category") == "character") else 1
        freq = in_chunk_frequency(src, t)
        ch = t.get("chapter_first_seen")
        ch_rank = ch if ch else 999999  # NULL/unknown → last
        return (is_char, -freq, ch_rank, -len(_source_of(t)))

    ranked = sorted(terms, key=key)
    if limit and limit > 0:
        ranked = ranked[:limit]
    return ranked
