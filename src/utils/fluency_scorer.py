#!/usr/bin/env python3
"""
Burmese Fluency Scorer — Reference-free fluency heuristic for Myanmar text.

Since reference translations are not available for BLEU/COMET scoring,
this module implements statistical and linguistic heuristics to evaluate
the naturalness and fluency of Myanmar prose output.

Scoring dimensions (0–100 composite):
  F1: Lexical Diversity    — Type-Token Ratio (TTR) — prevents repetitive output
  F2: Particle Diversity   — How many distinct Myanmar particles appear
  F3: Sentence Flow        — Sentence length variance + proper break punctuation
  F4: Syllable Richness    — Compound word density (multi-syllable token ratio)
  F5: Paragraph Rhythm     — Paragraph length variance (natural vs robotic)
  F6: Punctuation Health   — Proper use of ။ and ၊ (not all same ender)
  F7: Repetition Penalty   — Consecutive identical particle/word penalty

Usage:
  from src.utils.fluency_scorer import score_fluency, FluencyReport
  report = score_fluency(myanmar_text)
  print(f"Fluency Score: {report.composite_score}/100")
"""

import re
import math
from typing import List, Dict, Tuple
from dataclasses import dataclass, field


# ── Unicode Constants ──────────────────────────────────────────────
MYANMAR_CONSONANTS = set(range(0x1000, 0x1020)) | set(range(0x103F, 0x104A)) | {0x104C, 0x104D, 0x1050, 0x1051}
MYANMAR_COMBINING = set(range(0x102B, 0x1040)) | {0x1037}
MYANMAR_DIGITS = set(range(0x1040, 0x104A))
MYANMAR_PUNCTUATION = {'။', '၊'}

# Common Myanmar particles (postpositional markers)
PARTICLES = [
    'သည်', 'ကို', 'မှာ', '၏', 'ဖြင့်', '၍', 'ကဲ့သို့',
    'တယ်', 'ဘူး', 'မယ်', 'ရဲ့', 'နဲ့', 'ဝာ', 'လို့',
    'ရန်', 'အတွက်', 'မှ', 'သို့', 'နှင့်', 'ထံမှ',
    'အောက်', 'ထက်', 'ဘက်', 'ထဲ', 'ပေါ်', 'အား',
]

# Sentence-ending particles
SENTENCE_ENDERS = {'။', '၏', '၊'}


# ── Helper Functions ────────────────────────────────────────────────

def _is_myanmar(c: str) -> bool:
    """Check if character is Myanmar script."""
    cp = ord(c)
    return (0x1000 <= cp <= 0x109F) or (0xAA60 <= cp <= 0xAA7F) or (0xA9E0 <= cp <= 0xA9FF)


def _is_myanmar_word(word: str) -> bool:
    """Check if word contains only Myanmar and punctuation."""
    if not word or not word.strip():
        return False
    return any(_is_myanmar(c) for c in word)


def _count_syllables(word: str) -> int:
    """Count approximate syllables in a Myanmar word.

    Each consonant cluster followed by optional combining marks = 1 syllable.
    """
    count = 0
    in_cluster = False
    for c in word:
        cp = ord(c)
        if cp in MYANMAR_CONSONANTS:
            if not in_cluster:
                count += 1
                in_cluster = True
        elif cp in MYANMAR_COMBINING or cp in MYANMAR_DIGITS:
            in_cluster = False
        else:
            in_cluster = False
    return max(count, 1)


def _is_myanmar_syllable_block(c: str) -> bool:
    """Check if a character is part of a Myanmar syllable (consonant or combining)."""
    cp = ord(c)
    return cp in MYANMAR_CONSONANTS or cp in MYANMAR_COMBINING


# ── Data Class ──────────────────────────────────────────────────────

@dataclass
class FluencyReport:
    """Fluency scoring report."""
    composite_score: float = 0.0
    F1_lexical_diversity: float = 0.0
    F2_particle_diversity: float = 0.0
    F3_sentence_flow: float = 0.0
    F4_syllable_richness: float = 0.0
    F5_paragraph_rhythm: float = 0.0
    F6_punctuation_health: float = 0.0
    F7_repetition_penalty: float = 0.0

    total_words: int = 0
    unique_words: int = 0
    distinct_particles: int = 0
    sentence_count: int = 0
    avg_sentence_len: float = 0.0
    compound_word_ratio: float = 0.0
    paragraph_count: int = 0
    paragraph_length_variance: float = 0.0
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.composite_score >= 70

    @property
    def grade(self) -> str:
        s = self.composite_score
        if s >= 90:
            return "Excellent"
        elif s >= 80:
            return "Good"
        elif s >= 70:
            return "Adequate"
        elif s >= 50:
            return "Needs Improvement"
        else:
            return "Poor"


# ── Scoring Functions ───────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """Tokenize Myanmar text into words using spaces and punctuation as delimiters."""
    tokens = re.split(r'[\s၊။\-\—\n\r\t]+', text)
    return [t.strip() for t in tokens if t.strip() and _is_myanmar_word(t)]


def _score_lexical_diversity(tokens: List[str]) -> Tuple[float, int, int, List[str]]:
    """F1: Type-Token Ratio — measures vocabulary variety.

    High TTR (>0.6): Rich, varied vocabulary (good for literary text)
    Low TTR (<0.3): Repetitive, robotic output (hallmark of LLM loops)

    A reference-free alternative to BLEU that catches "the cat sat on the mat
    the cat sat on the mat" style repetition.
    """
    issues: List[str] = []
    if len(tokens) < 10:
        return 50.0, 0, 0, ["Text too short to evaluate lexical diversity"]

    total = len(tokens)
    unique = len(set(tokens))
    ttr = unique / total if total > 0 else 0

    if ttr >= 0.65:
        score = min(100.0, ttr * 130)
    elif ttr >= 0.45:
        score = ttr * 100 + 15
    elif ttr >= 0.30:
        score = ttr * 80 + 20
        issues.append(f"Low lexical diversity (TTR={ttr:.2f}) — vocabulary may be repetitive")
    else:
        score = ttr * 60 + 10
        issues.append(f"Very low lexical diversity (TTR={ttr:.2f}) — likely robotic/hallucinating output")

    return score, total, unique, issues


def _score_particle_diversity(tokens: List[str]) -> Tuple[float, int, List[str]]:
    """F2: Particle diversity — how many different Myanmar particles appear.

    Natural Myanmar prose uses a variety of postpositional particles.
    Robot output tends to use only 1-2 particles repeatedly.
    """
    issues: List[str] = []
    particle_counts: Dict[str, int] = {}

    for token in tokens:
        for particle in PARTICLES:
            if particle in token or token == particle:
                particle_counts[particle] = particle_counts.get(particle, 0) + 1

    distinct = len(particle_counts)

    if distinct >= 8:
        score = min(100.0, distinct * 10 + 20)
    elif distinct >= 5:
        score = distinct * 10 + 25
    elif distinct >= 3:
        score = distinct * 10 + 30
        issues.append(f"Only {distinct} distinct particles — prose may feel flat")
    else:
        score = distinct * 15 + 5
        issues.append(f"Too few particle types ({distinct}) — robotic output suspected")

    return score, distinct, issues


def _score_sentence_flow(text: str) -> Tuple[float, int, float, List[str]]:
    """F3: Sentence flow — length variance + ender variety.

    Natural prose has varied sentence lengths. Robot output has uniform lengths.
    Checks for proper ။/၏ sentence enders vs missing enders.
    """
    issues: List[str] = []
    sentences = re.split(r'[။၏၊\n]+', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 3]

    if len(sentences) < 2:
        return 30.0, len(sentences), 0, ["Too few sentences to evaluate flow"]

    lengths = [len(s) for s in sentences]
    avg_len = sum(lengths) / len(lengths)
    variance = sum((len_val - avg_len) ** 2 for len_val in lengths) / len(lengths)
    std_dev = math.sqrt(variance)

    # Count sentences ending with proper Myanmar enders
    lines = text.split('\n')
    content_lines = [
        ln.strip() for ln in lines
        if ln.strip() and not ln.strip().startswith('#') and not ln.strip().startswith('---')
    ]
    ended = sum(1 for ln in content_lines if ln and ln[-1] in SENTENCE_ENDERS)
    ender_ratio = ended / len(content_lines) if content_lines else 1.0

    score = 0.0

    # Length variance: natural text has std_dev between 8 and 80 chars
    if 15 <= std_dev <= 70:
        score += 45
    elif 8 <= std_dev <= 100:
        score += 30
        issues.append(f"Sentence lengths are somewhat uniform (std={std_dev:.0f} chars)")
    else:
        score += 15
        issues.append(f"Sentence lengths are too uniform (std={std_dev:.0f} chars) — robotic")

    # Average length: 30-120 chars is natural for Myanmar prose
    if 30 <= avg_len <= 120:
        score += 25
    elif 15 <= avg_len <= 200:
        score += 15
        issues.append(f"Average sentence length ({avg_len:.0f} chars) is outside natural range")
    else:
        score += 8
        issues.append(f"Average sentence length ({avg_len:.0f} chars) is abnormal")

    # Ender ratio
    if ender_ratio >= 0.85:
        score += 30
    elif ender_ratio >= 0.60:
        score += 15
        issues.append(f"Only {ender_ratio:.0%} lines end with proper sentence-ending punctuation")
    else:
        score += 5
        issues.append(f"Most lines ({1-ender_ratio:.0%}) lack sentence-ending punctuation — truncation")

    return score, len(sentences), std_dev, issues


def _score_syllable_richness(tokens: List[str]) -> Tuple[float, float, List[str]]:
    """F4: Syllable richness — compound word ratio.

    Natural Myanmar literary text has many multi-syllable compound words
    (e.g., ဝိညာဉ်စွမ်းအား vs single syllable လာ).

    Ratio of words with ≥2 syllables to total words. Higher = more natural.
    """
    issues: List[str] = []
    if len(tokens) < 5:
        return 50.0, 0.0, ["Too few tokens to evaluate syllable richness"]

    multi_syllable = sum(1 for t in tokens if _count_syllables(t) >= 2)
    ratio = multi_syllable / len(tokens) if tokens else 0

    if ratio >= 0.40:
        score = min(100.0, ratio * 150 + 20)
    elif ratio >= 0.25:
        score = ratio * 120 + 25
        issues.append(f"Compound word ratio ({ratio:.1%}) is low — prose may be simplistic")
    elif ratio >= 0.10:
        score = ratio * 80 + 35
        issues.append(f"Very low compound word ratio ({ratio:.1%}) — single-syllable dominance")
    else:
        score = ratio * 50 + 20
        issues.append(f"Almost no compound words ({ratio:.1%}) — likely not literary prose")

    return score, ratio, issues


def _score_paragraph_rhythm(text: str) -> Tuple[float, int, float, List[str]]:
    """F5: Paragraph rhythm — length variance between paragraphs.

    Natural text has varied paragraph lengths. Uniform lengths = robotic.
    """
    issues: List[str] = []
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    if len(paragraphs) < 2:
        return 30.0, len(paragraphs), 0, ["Only one paragraph — can't evaluate rhythm"]

    lengths = [len(p) for p in paragraphs]
    avg_len = sum(lengths) / len(lengths)
    variance = sum((len_val - avg_len) ** 2 for len_val in lengths) / len(lengths)
    std_dev = math.sqrt(variance)

    if std_dev > avg_len * 0.3 and avg_len > 50:
        score = min(100.0, 60 + std_dev * 0.2)
    elif std_dev > avg_len * 0.15:
        score = 50 + std_dev * 0.3
        issues.append("Paragraph lengths are somewhat uniform")
    else:
        score = max(10.0, 30 + std_dev * 0.5)
        issues.append("Paragraph lengths are very uniform — robotic output suspected")

    return score, len(paragraphs), std_dev, issues


def _score_punctuation_health(text: str) -> Tuple[float, List[str]]:
    """F6: Punctuation health — proper use of Myanmar enders.

    Natural Myanmar text uses both ။ (section ender) and ၊ (clause separator).
    Robot output often uses only one type or drops them entirely.
    """
    issues: List[str] = []
    major_count = text.count('။')
    minor_count = text.count('၊')

    total = major_count + minor_count

    if total == 0:
        return 10.0, ["No Myanmar punctuation found — text may be untranslated or garbled"]

    # Natural ratio: major:minor ≈ 1:3 to 3:1
    score = 0.0

    # Punctuation density: should be ~1 ender per 25-80 chars
    char_count = sum(1 for c in text if not c.isspace())
    chars_per_punc = char_count / total if total > 0 else float('inf')

    if 20 <= chars_per_punc <= 100:
        score += 50
    elif 10 <= chars_per_punc <= 150:
        score += 35
        issues.append(f"Punctuation density ({chars_per_punc:.0f} chars/punc) is outside ideal range")
    else:
        score += 15
        issues.append(f"Punctuation density ({chars_per_punc:.0f} chars/punc) is abnormal")

    # Both ။ and ၊ should appear
    if major_count >= 2 and minor_count >= 2:
        score += 30
    elif major_count >= 1 and minor_count >= 1:
        score += 20
        issues.append("Very few punctuation marks — possible output degradation")
    else:
        score += 5
        if major_count == 0:
            issues.append("Missing ။ (section ender) — every Myanmar sentence needs ။")
        if minor_count == 0:
            issues.append("Missing ၊ (clause separator) — dialogue and lists need ၊")

    # ။ should not appear consecutively (double ender symptom)
    if '။။' not in text:
        score += 20
    else:
        score += 5
        issues.append("Consecutive ။။ detected — sentence boundary corruption")

    return score, issues


def _score_repetition_penalty(tokens: List[str]) -> Tuple[float, List[str]]:
    """F7: Repetition penalty — consecutively repeated identical words/particles.

    Detects model hallucination loops (e.g., 'သည် သည် သည်').
    """
    issues: List[str] = []
    if len(tokens) < 3:
        return 100.0, ["Too few tokens for repetition check"]

    consecutive_repeats = 0
    for i in range(len(tokens) - 2):
        if tokens[i] == tokens[i + 1] == tokens[i + 2]:
            consecutive_repeats += 1

    if consecutive_repeats == 0:
        return 100.0, []

    penalty = min(consecutive_repeats * 15, 80)
    score = 100.0 - penalty
    issues.append(
        f"{consecutive_repeats} consecutive word repetition(s) — "
        f"hallucination loop detected"
    )
    return score, issues


# ── Main Scoring Function ───────────────────────────────────────────

def score_fluency(text: str) -> FluencyReport:
    """Score the fluency of Myanmar translation text using heuristic measures.

    Args:
        text: Myanmar text to evaluate

    Returns:
        FluencyReport with composite score and per-dimension breakdown

    Weights:
        F1 - Lexical Diversity:    20%  (vocabulary variety)
        F2 - Particle Diversity:    15%  (particle variety)
        F3 - Sentence Flow:         20%  (length variance, enders)
        F4 - Syllable Richness:     15%  (compound word ratio)
        F5 - Paragraph Rhythm:      10%  (paragraph variance)
        F6 - Punctuation Health:    10%  (punctuation usage)
        F7 - Repetition Penalty:    10%  (hallucination sentinel)
    """
    report = FluencyReport()

    tokens = _tokenize(text)
    report.total_words = len(tokens)
    report.unique_words = len(set(tokens))

    # F1: Lexical Diversity (20%)
    f1_score, total, unique, f1_issues = _score_lexical_diversity(tokens)
    report.F1_lexical_diversity = f1_score
    report.issues.extend(f1_issues)

    # F2: Particle Diversity (15%)
    f2_score, distinct, f2_issues = _score_particle_diversity(tokens)
    report.F2_particle_diversity = f2_score
    report.distinct_particles = distinct
    report.issues.extend(f2_issues)

    # F3: Sentence Flow (20%)
    f3_score, sent_count, std_dev, f3_issues = _score_sentence_flow(text)
    report.F3_sentence_flow = f3_score
    report.sentence_count = sent_count
    report.avg_sentence_len = sum(len(s.split()) for s in text.split('။')) / max(sent_count, 1)
    report.issues.extend(f3_issues)

    # F4: Syllable Richness (15%)
    f4_score, ratio, f4_issues = _score_syllable_richness(tokens)
    report.F4_syllable_richness = f4_score
    report.compound_word_ratio = ratio
    report.issues.extend(f4_issues)

    # F5: Paragraph Rhythm (10%)
    f5_score, para_count, para_std, f5_issues = _score_paragraph_rhythm(text)
    report.F5_paragraph_rhythm = f5_score
    report.paragraph_count = para_count
    report.paragraph_length_variance = para_std
    report.issues.extend(f5_issues)

    # F6: Punctuation Health (10%)
    f6_score, f6_issues = _score_punctuation_health(text)
    report.F6_punctuation_health = f6_score
    report.issues.extend(f6_issues)

    # F7: Repetition Penalty (10%)
    f7_score, f7_issues = _score_repetition_penalty(tokens)
    report.F7_repetition_penalty = f7_score
    report.issues.extend(f7_issues)

    # Composite score (weighted)
    weights = {
        'F1': 0.20, 'F2': 0.15, 'F3': 0.20,
        'F4': 0.15, 'F5': 0.10, 'F6': 0.10, 'F7': 0.10,
    }
    composite = (
        f1_score * weights['F1'] +
        f2_score * weights['F2'] +
        f3_score * weights['F3'] +
        f4_score * weights['F4'] +
        f5_score * weights['F5'] +
        f6_score * weights['F6'] +
        f7_score * weights['F7']
    )
    report.composite_score = round(composite, 1)

    # Generate recommendations
    if report.composite_score < 70:
        if f1_score < 60:
            report.recommendations.append(
                "Increase vocabulary variety — output is too repetitive. "
                "Try lowering temperature or increasing top_p."
            )
        if f3_score < 60:
            report.recommendations.append(
                "Improve sentence flow — vary sentence lengths and ensure "
                "proper ။ sentence enders on every line."
            )
        if f7_score < 80:
            report.recommendations.append(
                "Fix hallucination loops — increase repeat_penalty to 1.2+ "
                "and reduce temperature to 0.2."
            )
        if f6_score < 50:
            report.recommendations.append(
                "Fix punctuation — ensure every Myanmar sentence ends with ။ "
                "and clauses use ၊ where appropriate."
            )

    return report


def score_fluency_quick(text: str) -> float:
    """Quick fluency score convenience wrapper. Returns composite_score only."""
    return score_fluency(text).composite_score
