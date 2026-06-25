"""Rule-based Myanmar (Burmese) syllable segmentation.

Myanmar script has no inter-word spaces and stacks consonants, so a raw
character count is a poor proxy for length, tokens, or "words". This module
segments text into orthographic syllables using the well-established *sylbreak*
rule set (Ye Kyaw Thu et al.):

    A syllable begins at a consonant / independent vowel / digit that is NOT
    preceded by the virama U+1039 (which stacks the following consonant onto the
    current syllable). Stacked clusters and trailing vowels/tones stay attached.

It is deterministic, dependency-free, and safe on mixed Myanmar/Latin text: runs
of non-Myanmar characters are emitted as their own tokens and never split.

Used by the fluency scorer, content-length metrics, and the QE re-ranker to
compare source vs. target length in a script-aware way instead of by raw chars.
"""

import re
from typing import List

# Onset characters — any of these *starts* a new syllable (unless stacked):
#   U+1000–U+1021  consonants က–အ
#   U+1023–U+1027  independent vowels (i, ii, u, uu, e)
#   U+1029, U+102A independent vowels (o, au)
#   U+103F         great sa ဿ
#   U+1040–U+1049  Myanmar digits ၀–၉
#   U+104C–U+104F  symbols / abbreviation marks
_ONSET = (
    "က-အ"
    "ဣ-ဧ"
    "ဩဪ"
    "ဿ"
    "၀-၉"
    "၌-၏"
)

# Virama (stacking, U+1039 ္): a consonant right AFTER it is stacked onto the
# current syllable — we must not break before such a consonant.
_VIRAMA = "္"
# Asat (U+103A ်): marks the PRECEDING consonant as a syllable-final coda — so a
# consonant FOLLOWED by asat is not a new onset and must not be broken before
# (without this, မြန်မာ wrongly splits as မြ/န်/မာ instead of မြန်/မာ).
_ASAT = "်"

# Insert a zero-width marker before every genuine onset, then split on it.
# Onset = an onset char that is neither stacked (preceded by virama) nor a coda
# consonant (immediately followed by asat or virama).
_ZWS = "​"
_BREAK_RE = re.compile(rf"(?<!{_VIRAMA})([{_ONSET}])(?![{_ASAT}{_VIRAMA}])")

# Any Myanmar-script codepoint (basic + Extended-A + Extended-B).
_MM_RE = re.compile(r"[က-႟ꩠ-ꩿꧠ-꧿]")


def segment_syllables(text: str) -> List[str]:
    """Split ``text`` into syllable tokens.

    Myanmar runs are split into orthographic syllables; contiguous non-Myanmar
    runs (Latin words, punctuation, whitespace) are returned as single tokens.
    Whitespace-only tokens are dropped.

    >>> segment_syllables("မြန်မာ")
    ['မြန်', 'မာ']
    """
    if not text:
        return []
    marked = _BREAK_RE.sub(_ZWS + r"\1", text)
    return [tok for tok in marked.split(_ZWS) if tok.strip()]


def count_syllables(text: str) -> int:
    """Number of Myanmar syllables in ``text`` (non-Myanmar tokens excluded)."""
    if not text:
        return 0
    return sum(1 for tok in segment_syllables(text) if _MM_RE.search(tok))


def syllable_length(text: str) -> int:
    """Script-aware length: Myanmar syllables + non-Myanmar (whitespace-split) words.

    A better unit than ``len(text)`` for comparing the size of a Myanmar
    translation against an English/Chinese source — one Burmese syllable is a
    rough analogue of one Latin word or one CJK character.
    """
    if not text:
        return 0
    mm = 0
    other_chars: List[str] = []
    for tok in segment_syllables(text):
        if _MM_RE.search(tok):
            mm += 1
        else:
            other_chars.append(tok)
    # Count non-Myanmar tokens as whitespace-delimited words (so "the cat" = 2).
    other_words = len("".join(other_chars).split())
    return mm + other_words
