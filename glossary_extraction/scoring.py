"""Score and rank candidate glossary terms."""

import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

CAPTURE_KEYWORDS = {
    "title_honorific": ["master", "elder", "brother", "sister", "lord", "lady"],
    "technique": ["art", "technique", "skill", "method", "saber", "sword", "fist"],
    "cultivation_concept": ["heavenly", "earth", "divine", "demonic", "qi", "soul"],
    "location": ["city", "mountain", "sea", "realm", "pavilion", "palace"],
}


def score_candidate(candidate: dict, total_chapters: int = 1) -> dict:
    """Score a candidate term based on frequency, length, and category signals.

    Returns the candidate dict with 'score' added.
    """
    freq = candidate.get("frequency", 1)
    source = candidate.get("source_term", "")
    category = candidate.get("category", "general")
    contexts = candidate.get("contexts", [])

    freq_score = min(1.0, freq / 20)

    length_score = min(1.0, len(source) / 20)

    category_score = 0.5
    cat_keywords = CAPTURE_KEYWORDS.get(category, [])
    if cat_keywords:
        source_lower = source.lower()
        matches = sum(1 for kw in cat_keywords if kw in source_lower)
        if matches:
            category_score = 0.8 + matches * 0.05

    context_score = 0.0
    if contexts:
        non_identical = sum(
            1 for c in contexts if SequenceMatcher(None, source, c).ratio() < 0.9
        )
        context_score = min(0.5, non_identical * 0.1)

    chapter_score = min(0.2, total_chapters * 0.05)

    score = (
        freq_score * 0.4
        + length_score * 0.1
        + category_score * 0.2
        + context_score * 0.2
        + chapter_score * 0.1
    )

    candidate["score"] = round(score, 4)
    candidate["score_components"] = {
        "freq_score": round(freq_score, 4),
        "length_score": round(length_score, 4),
        "category_score": round(category_score, 4),
        "context_score": round(context_score, 4),
        "chapter_score": round(chapter_score, 4),
    }
    return candidate


def rank_candidates(
    candidates: list[dict],
    min_score: float = 0.3,
    max_results: int = 100,
) -> list[dict]:
    scored = [score_candidate(c) for c in candidates]
    scored.sort(key=lambda c: c["score"], reverse=True)
    return [c for c in scored if c["score"] >= min_score][:max_results]
