"""Quality-Estimation re-ranking (best-of-N) for translation candidates.

A small local model is *stochastic*: re-sampling the same chunk yields outputs of
noticeably different quality. Instead of taking one greedy generation and patching
defects with rule-based retries, we can sample N candidates and keep the best one
under a reference-free quality estimator — the single biggest quality lever for
local-model MT (a.k.a. QE re-ranking / a poor-man's MBR decoding).

This module is the *scorer + selector*. It reuses the project's existing signals:
  • fluency  — :func:`fluency_scorer.score_fluency` (target naturalness, 0–100)
  • adequacy — optional cross-lingual fidelity in [0,1] (BGE-M3), supplied by caller
  • hard defects — placeholders, fused-Latin corruption, foreign-script leakage,
    truncation, degenerate loops, and gross length deficiency.

It is model-agnostic: :func:`select_best` scores ready-made candidates, and
:func:`generate_and_select` drives any ``generate_fn(i) -> str`` (e.g. an Ollama
call with a per-candidate seed), so it is fully unit-testable without a model.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional, Sequence

from src.utils.postprocessor import (
    myanmar_char_ratio,
    detect_language_leakage,
    detect_placeholder_marks,
    detect_latin_in_myanmar,
    looks_truncated,
    detect_compression_degeneration,
)
from src.utils.myanmar_syllable import syllable_length

logger = logging.getLogger(__name__)


def score_candidate(
    source_text: str,
    candidate: str,
    adequacy: Optional[float] = None,
) -> dict:
    """Score one candidate translation in [0, 1] (higher = better).

    Args:
        source_text: The source chunk (English/Chinese) — used for length checks.
        candidate: A cleaned Myanmar candidate translation.
        adequacy: Optional cross-lingual fidelity score in [0, 1] (e.g. from
            BGE-M3). When None, quality rests on fluency alone.

    Returns:
        ``{'score', 'quality', 'penalty', 'breakdown'}`` where ``breakdown`` lists
        the individual signals/penalties for logging.
    """
    breakdown: dict = {}

    if not candidate or not candidate.strip():
        return {"score": 0.0, "quality": 0.0, "penalty": 1.0,
                "breakdown": {"empty": True}}

    # ── Base quality: fluency (+ adequacy when available) ──
    try:
        from src.utils.fluency_scorer import score_fluency
        fluency = score_fluency(candidate).composite_score / 100.0
    except Exception:  # pragma: no cover - defensive
        fluency = 0.5
    breakdown["fluency"] = round(fluency, 3)

    if adequacy is not None:
        adq = max(0.0, min(1.0, float(adequacy)))
        quality = 0.6 * adq + 0.4 * fluency
        breakdown["adequacy"] = round(adq, 3)
    else:
        quality = fluency

    # ── Additive penalties for hard defects ──
    penalty = 0.0

    if detect_placeholder_marks(candidate):
        penalty += 0.5
        breakdown["placeholder"] = True
    if detect_latin_in_myanmar(candidate):
        penalty += 0.4
        breakdown["fused_latin"] = True

    leak = detect_language_leakage(candidate)
    if leak.get("chinese_chars", 0) > 0:
        penalty += 0.3
        breakdown["chinese_leak"] = leak["chinese_chars"]
    if leak.get("latin_words", 0) > 8:
        penalty += 0.2
        breakdown["english_leak"] = leak["latin_words"]

    if looks_truncated(candidate):
        penalty += 0.15
        breakdown["truncated"] = True

    comp = detect_compression_degeneration(candidate)
    if comp["severe"]:
        penalty += 0.5
        breakdown["loop"] = comp["ratio"]
    elif comp["degenerate"]:
        penalty += 0.15
        breakdown["repetitive"] = comp["ratio"]

    # Length adequacy: a candidate far shorter than the source likely dropped
    # content. Compared in script-aware units (Myanmar syllables vs source words).
    src_units = syllable_length(source_text)
    cand_units = syllable_length(candidate)
    if src_units >= 20:
        len_ratio = cand_units / src_units
        breakdown["len_ratio"] = round(len_ratio, 2)
        if len_ratio < 0.40:
            penalty += 0.25
        elif len_ratio < 0.60:
            penalty += 0.10

    score = max(0.0, quality - penalty)

    # Hard gate: sub-Myanmar output can never win (garbled/wrong-language).
    ratio = myanmar_char_ratio(candidate)
    breakdown["myanmar_ratio"] = round(ratio, 3)
    if ratio < 0.50:
        score *= ratio  # collapse toward 0

    return {"score": round(score, 4), "quality": round(quality, 4),
            "penalty": round(penalty, 4), "breakdown": breakdown}


def select_best(
    source_text: str,
    candidates: Sequence[str],
    adequacies: Optional[Sequence[Optional[float]]] = None,
) -> tuple[int, list[dict]]:
    """Pick the best candidate index. Returns ``(best_index, scored)``.

    ``scored`` is a list of per-candidate dicts (the :func:`score_candidate`
    output plus ``index``), ordered as given. Ties are broken toward the longer
    (more complete) candidate, then the earliest index.
    """
    if not candidates:
        return -1, []

    scored: list[dict] = []
    for i, cand in enumerate(candidates):
        adq = adequacies[i] if adequacies and i < len(adequacies) else None
        s = score_candidate(source_text, cand, adq)
        s["index"] = i
        s["length"] = syllable_length(cand or "")
        scored.append(s)

    best = max(scored, key=lambda s: (s["score"], s["length"], -s["index"]))
    return best["index"], scored


def generate_and_select(
    source_text: str,
    generate_fn: Callable[[int], str],
    n: int = 3,
    adequacy_fn: Optional[Callable[[str], float]] = None,
) -> dict:
    """Generate ``n`` candidates and return the best under QE scoring.

    Args:
        source_text: The source chunk.
        generate_fn: ``generate_fn(i)`` returns the i-th *cleaned* candidate.
            Callers typically vary the sampling seed by ``i`` so candidates differ
            without raising temperature (which corrupts Myanmar output).
        n: Number of candidates to draw (clamped to ≥ 1).
        adequacy_fn: Optional ``adequacy_fn(candidate) -> float in [0,1]``.

    Returns:
        ``{'best', 'best_index', 'candidates', 'scored'}``. Falls back to the
        first successful generation if scoring cannot rank anything.
    """
    n = max(1, n)
    candidates: list[str] = []
    adequacies: list[Optional[float]] = []
    for i in range(n):
        try:
            cand = generate_fn(i) or ""
        except Exception as e:
            logger.warning("Candidate %d generation failed: %s", i, e)
            cand = ""
        candidates.append(cand)
        if adequacy_fn is not None and cand.strip():
            try:
                adequacies.append(adequacy_fn(cand))
            except Exception:  # pragma: no cover - defensive
                adequacies.append(None)
        else:
            adequacies.append(None)

    best_index, scored = select_best(source_text, candidates, adequacies)
    if best_index < 0:
        return {"best": "", "best_index": -1, "candidates": candidates, "scored": []}

    if len(candidates) > 1:
        logger.info(
            "QE re-rank: chose candidate %d/%d (score=%.3f) over %s",
            best_index, n, scored[best_index]["score"],
            [s["score"] for s in scored],
        )
    return {"best": candidates[best_index], "best_index": best_index,
            "candidates": candidates, "scored": scored}
