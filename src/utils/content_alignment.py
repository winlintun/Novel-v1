"""Embedding-based source↔translation sentence alignment for content-loss.

Surface metrics (character-count ratio, paragraph counts) can only *guess* that
content was dropped — they cannot say *which* sentence is missing, and they are
fooled by the fact that Myanmar is more compact than English. This module embeds
source and target sentences into BGE-M3's shared multilingual space and, for
every source sentence, finds its best-matching target sentence. Source sentences
with no good match are reported as concrete dropped/mistranslated content, which
is directly actionable (re-translate just that span).

It degrades gracefully: when ``sentence-transformers`` / the BGE-M3 model are not
available (e.g. CI), :func:`find_dropped_content` returns ``checked=False`` and
callers fall back to the character-ratio heuristic.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _strip_noise(text: str) -> str:
    text = (text or "").replace("﻿", "").replace("​", "")
    text = re.sub(r"(?m)^\s*#.*$", " ", text)        # markdown headings
    text = re.sub(r"\[[0-9၀-၉]+\]", " ", text)       # footnote markers [1]/[၁]
    return text


def split_source_sentences(text: str) -> list[str]:
    """Split English/Chinese source into sentences for alignment."""
    text = _strip_noise(text)
    parts = re.split(r"(?<=[.!?。！？])\s+|\n{2,}", text)
    return [p.strip() for p in parts if len(p.strip()) >= 12]


def split_target_sentences(text: str) -> list[str]:
    """Split Myanmar target into sentences (terminator ။, breaks)."""
    text = _strip_noise(text)
    parts = re.split(r"(?<=။)\s*|\n{2,}", text)
    return [p.strip() for p in parts if len(p.strip()) >= 6]


# Process-level singleton: the BGE-M3 model is ~2GB and this runs per chapter
# in the live review path, so we must NOT rebuild/reload it on every call. The
# sentinel distinguishes "not tried yet" from "tried and failed" (cached as None)
# so a missing model is never re-attempted on every chunk.
_UNSET = object()
_EMBEDDER = _UNSET


def _load_embedder():
    """Best-effort lazy load of the shared BGE-M3 embedder; None if unavailable.

    The embedder instance is cached for the process lifetime (including a failed
    load as None) — a fresh load per chapter would reload the multi-GB model.
    """
    global _EMBEDDER
    if _EMBEDDER is _UNSET:
        try:
            from src.dataset_alignment.embedder import BGEEmbedder
            _EMBEDDER = BGEEmbedder()
        except Exception as e:  # pragma: no cover - depends on optional deps
            logger.debug("Content-alignment embedder unavailable: %s", e)
            _EMBEDDER = None
    return _EMBEDDER


def find_dropped_content(
    source_text: str,
    translated_text: str,
    embedder: Optional[Any] = None,
    threshold: float = 0.45,
) -> dict:
    """Identify source sentences with no adequate translation (dropped content).

    Args:
        source_text: English/Chinese source.
        translated_text: Myanmar translation.
        embedder: An object exposing ``encode(list[str]) -> ndarray`` of
            L2-normalized embeddings. If None, one is lazily loaded; if that
            fails, the check degrades to ``checked=False``.
        threshold: Cosine-similarity floor below which a source sentence counts
            as dropped/mistranslated.

    Returns:
        dict with keys:
          ``checked``   — False if no embedder / not enough sentences.
          ``coverage``  — fraction of source sentences adequately covered (0–1).
          ``n_source``  — source sentence count.
          ``dropped``   — list of ``{'source', 'best_sim'}`` for missing content.
          ``added``     — list of ``{'target', 'best_sim'}`` (likely hallucination).
    """
    result: dict = {"checked": False, "coverage": 1.0, "n_source": 0,
                    "dropped": [], "added": []}

    src_sents = split_source_sentences(source_text)
    tgt_sents = split_target_sentences(translated_text)
    result["n_source"] = len(src_sents)
    if not src_sents or not tgt_sents:
        return result

    emb = embedder if embedder is not None else _load_embedder()
    if emb is None:
        return result

    try:
        import numpy as np
        src_emb = np.asarray(emb.encode(src_sents))
        tgt_emb = np.asarray(emb.encode(tgt_sents))
        if src_emb.size == 0 or tgt_emb.size == 0:
            return result
        # Embeddings are L2-normalized → dot product is cosine similarity.
        sim = src_emb @ tgt_emb.T
    except Exception as e:  # pragma: no cover - runtime/model errors
        logger.debug("Content-alignment failed (non-fatal): %s", e)
        return result

    src_best = sim.max(axis=1)
    dropped = [
        {"source": src_sents[i][:90], "best_sim": round(float(b), 3)}
        for i, b in enumerate(src_best) if b < threshold
    ]
    tgt_best = sim.max(axis=0)
    added = [
        {"target": tgt_sents[j][:90], "best_sim": round(float(b), 3)}
        for j, b in enumerate(tgt_best) if b < threshold
    ]

    covered = sum(1 for b in src_best if b >= threshold)
    result.update(
        checked=True,
        coverage=round(covered / len(src_sents), 3),
        dropped=dropped,
        added=added,
    )
    return result
