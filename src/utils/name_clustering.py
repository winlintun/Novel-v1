"""Automatic clustering of Myanmar name-spelling variants → canonical form.

A small model transliterates the same romanized name inconsistently across a
chapter (ပိုင်ရှောင်ချန်း / ပိုင်ရှောင်ချီ / ဘိုင်ရှောင်ချန်း …). The existing
fixes for this are *manual*: a hand-maintained correction map and per-name fuzzy
passes. This module derives the variant→canonical map automatically:

  1. Collect candidate name tokens (Myanmar sequences in name positions).
  2. Cluster them by similarity using SequenceMatcher — which is Myanmar-safe,
     unlike char-set overlap (AGENTS.md Pattern 10) — via union-find.
  3. Pick each cluster's canonical form: the glossary target if a member matches
     one, otherwise the most frequent spelling.

The output is a ``{variant: canonical}`` dict suitable for plain substring
replacement (Burmese has no inter-word spaces), e.g. fed straight into
``glossary_enforcer.enforce_variants``. Conservative by design: singletons and
low-similarity pairs are never merged, so unrelated words are not corrupted.
"""

from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Optional

# Myanmar token immediately before a subject/object particle = likely a name.
# The char class excludes spaces and punctuation, so it stops at the word
# boundary on its own; the upper bound (24 codepoints) only caps runaway matches
# — Burmese names are long in codepoints because of stacked combining marks.
# Only TRUE grammatical particles anchor a name — not verbs. (Including verbs
# like ပြော/ဆို let a subject-marker က be swallowed into the name: in
# "ပိုင်ရှောင်ချီက ပြောသည်" the whole "ပိုင်ရှောင်ချီက" was wrongly captured.)
_NAME_CANDIDATE_RE = re.compile(
    r"([က-၉ၐ-႟]{2,24})\s*"
    r"(?:သည်|က|မှာ|ကို|၏|သို့|ထံ|နှင့်|တို့|အား)"
)


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def extract_name_candidates(text: str) -> Counter:
    """Return a Counter of Myanmar tokens appearing in name (pre-particle) positions."""
    if not text:
        return Counter()
    return Counter(_NAME_CANDIDATE_RE.findall(text))


def _canonical_set(glossary_terms: Optional[list[dict]]) -> dict[str, str]:
    """Map each glossary character target to itself (lookup of approved spellings)."""
    out: dict[str, str] = {}
    for t in glossary_terms or []:
        if t.get("category") and t.get("category") != "character":
            continue
        tgt = (t.get("target_term") or t.get("target") or "").strip()
        if len(tgt) >= 2:
            out[tgt] = tgt
    return out


def cluster_name_variants(
    text: str,
    glossary_terms: Optional[list[dict]] = None,
    *,
    threshold: float = 0.78,
    min_count: int = 1,
) -> dict[str, str]:
    """Build a ``{variant: canonical}`` map of name spellings found in ``text``.

    Args:
        text: Translated Myanmar text to scan.
        glossary_terms: Optional glossary rows; a cluster containing a known
            character target adopts that target as canonical.
        threshold: SequenceMatcher ratio above which two spellings are merged.
        min_count: Ignore candidate tokens occurring fewer than this many times.

    Returns:
        Mapping from each non-canonical variant to its cluster's canonical form.
        Only entries where ``variant != canonical`` are included.
    """
    counts = extract_name_candidates(text)
    approved = _canonical_set(glossary_terms)

    # Also seed with glossary targets so a variant clusters onto its canon even
    # if the canonical spelling itself never appears in the text.
    tokens = list({*counts.keys(), *approved.keys()})
    tokens = [t for t in tokens if counts.get(t, 0) >= min_count or t in approved]
    if len(tokens) < 2:
        return {}

    uf = _UnionFind(len(tokens))
    for i in range(len(tokens)):
        for j in range(i + 1, len(tokens)):
            a, b = tokens[i], tokens[j]
            # Length guard first (cheap) — names of very different length aren't variants.
            if abs(len(a) - len(b)) > 4:
                continue
            if SequenceMatcher(None, a, b).ratio() >= threshold:
                uf.union(i, j)

    # Group tokens by cluster root.
    clusters: dict[int, list[int]] = {}
    for idx in range(len(tokens)):
        clusters.setdefault(uf.find(idx), []).append(idx)

    variant_map: dict[str, str] = {}
    for members in clusters.values():
        if len(members) < 2:
            continue
        member_tokens = [tokens[m] for m in members]
        # Canonical: a glossary-approved member wins; else the most frequent
        # spelling (ties broken by longer = more complete name).
        canon = next((t for t in member_tokens if t in approved), None)
        if canon is None:
            canon = max(member_tokens, key=lambda t: (counts.get(t, 0), len(t)))
        for t in member_tokens:
            if t != canon:
                variant_map[t] = canon
    return variant_map
