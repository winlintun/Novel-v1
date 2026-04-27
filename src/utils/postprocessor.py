"""
src/utils/postprocessor.py
Cleans raw LLM output before saving.
Strips: <think>, <answer>, HTML comments, non-Myanmar language leakage.
"""

import re
from typing import Optional, List


# Myanmar Unicode range: \u1000-\u109F (basic) + \uAA60-\uAA7F (extended)
_MYANMAR_PATTERN = re.compile(r"[\u1000-\u109F\uAA60-\uAA7F]")

# Tags from reasoning models (DeepSeek, Hunyuan, Qwen-thinking, etc.)
_TAG_PATTERNS: List[re.Pattern] = [
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"</?think>", re.IGNORECASE),
    re.compile(r"<answer>", re.IGNORECASE),
    re.compile(r"</answer>", re.IGNORECASE),
    re.compile(r"<!--.*?-->", re.DOTALL),               # HTML comments (metadata block)
]

# Stray header artifacts left by models
_HEADER_ARTIFACTS: List[re.Pattern] = [
    re.compile(r"^MYANMAR TRANSLMENT:.*$", re.MULTILINE),
    re.compile(r"^MYANMAR TRANSLATION:.*$", re.MULTILINE),
    re.compile(r"^TEXT TO TRANSLATE:.*$", re.MULTILINE),
    re.compile(r"^INPUT TEXT.*?:.*$", re.MULTILINE),
    re.compile(r"^Translation Progress:.*$", re.MULTILINE),
]

# Model reasoning/thinking process patterns (NOT actual translation output)
_REASONING_PATTERNS: List[re.Pattern] = [
    # Match "Here's a thinking process..." sections (common in Qwen outputs)
    re.compile(r"Here's a thinking process.*?(?=^\d+\s+\*\*Analyze|$)", re.DOTALL | re.MULTILINE),
    re.compile(r"Here's a thinking process.*?^(?=\d+\.|Here is|\*\*Burmese Draft|\*\*Myanmar Draft|# |\[|^[^\*a-zA-Z])", re.DOTALL | re.MULTILINE),
    # Match "Analyze the Request and Constraints" sections
    re.compile(r"^\d+\.\s+\*\*Analyze the Request and Constraints:\*\*.*?^(?=\d+\.|\*\*|$)", re.DOTALL | re.MULTILINE),
    # Match "Analyze the Glossary" sections
    re.compile(r"^\d+\.\s+\*\*Analyze the Glossary:\*\*.*?^(?=\d+\.|\*\*|$)", re.DOTALL | re.MULTILINE),
    # Match "Analyze the Source Text" sections
    re.compile(r"^\d+\.\s+\*\*Analyze the Source Text.*?\*\*.*?^(?=\d+\.|\*\*|$)", re.DOTALL | re.MULTILINE),
    # Match "Segment and Translate" sections (the analysis part, not the draft)
    re.compile(r"^\d+\.\s+\*\*Segment and Translate.*?\*\*.*?^(?=\*\*Burmese Draft|\*\*Myanmar Draft|\d+\.|Here is|$)", re.DOTALL | re.MULTILINE),
    # Match "Refinement" and "Drafting" analysis sections
    re.compile(r"^\s*\*\*(Refinement|Drafting|Drafting Focus|Focus):\*\*.*?^(?=\*\*Burmese|\*\*Myanmar|\d+\.|Here is|$)", re.DOTALL | re.MULTILINE),
    # Remove all lines starting with analysis markup
    re.compile(r"^\s*\*\s*\*Original:\*.*?$", re.MULTILINE),
    re.compile(r"^\s*\*\s*\*Key.*?\*.*?$", re.MULTILINE),
    re.compile(r"^\s*\*\s*\*Tone.*?\*.*?$", re.MULTILINE),
    re.compile(r"^\s*\*\s*\*Key elements.*?\*.*?$", re.MULTILINE),
    # Remove glossary checkboxes like "[○] Luo Qing = ..."
    re.compile(r"^\s*\[.\]\s+\w+\s+=.*?$", re.MULTILINE),
]

# Thai Unicode range — should never appear in Myanmar output
_THAI_PATTERN = re.compile(r"[\u0E00-\u0E7F]+")

# Chinese characters — should not remain in translated output body
_CHINESE_PATTERN = re.compile(r"[\u4E00-\u9FFF\u3400-\u4DBF]+")

# English/Latin characters — should be minimized in Myanmar output
# Allows markdown syntax (*, _, #, etc.) but detects words
_LATIN_WORD_PATTERN = re.compile(r"[a-zA-Z]{3,}")  # 3+ letter Latin words

# English common words that indicate language drift
_ENGLISH_COMMON_WORDS = re.compile(
    r'\b(the|and|for|are|but|not|you|all|can|had|her|was|one|our|out|day|get|has|him|his|how|its|may|new|now|old|see|two|who|boy|did|she|use|her|way|many|oil|sit|set|run|eat|far|sea|eye|ago|off|too|any|say|man|try|ask|end|why|let|put|far|few|did|she|try|way|own|say|too|old|tell|very|when|much|would|there|their|what|said|each|which|will|about|could|other|after|first|never|these|think|where|being|every|great|might|shall|still|those|while|this|that|with|from|they|have|were|been|time|than|them|into|just|like|over|also|back|only|know|take|year|good|some|come|make|well|look|down|most|long|find|here|both|made|part|even|more|such|work|life|right|through|during|before|between|should|however|something|someone|because|without|another|nothing|everything|everyone|really|always|around|another|within|another|himself|herself|itself|myself|yourself|themselves|yourselves|ourselves)\b',
    re.IGNORECASE
)


def strip_reasoning_tags(text: str) -> str:
    """Remove <think>...</think> and <answer> tags from reasoning model output."""
    for pattern in _TAG_PATTERNS:
        text = pattern.sub("", text)
    return text


def strip_header_artifacts(text: str) -> str:
    """Remove stray metadata lines injected by the model or assembler."""
    for pattern in _HEADER_ARTIFACTS:
        text = pattern.sub("", text)
    return text


def strip_reasoning_process(text: str) -> str:
    """
    Remove 'thinking process' sections that models output before the actual translation.
    These are NOT part of the translation - they're the model's internal analysis.
    """
    # First pass: remove large reasoning blocks
    for pattern in _REASONING_PATTERNS:
        text = pattern.sub("", text)
    
    # Second pass: clean up remaining analysis lines and markers
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        original_line = line
        
        # Remove "**Burmese Draft:**" or "**Myanmar Draft:**" markers with optional leading bullet
        # Pattern: optional whitespace, optional bullet (* or -), optional whitespace, **Label:**, whitespace
        line = re.sub(r'^\s*[\*\-]?\s*\*\*Burmese Draft:\*\*\s*', '', line, flags=re.IGNORECASE)
        line = re.sub(r'^\s*[\*\-]?\s*\*\*Myanmar Draft:\*\*\s*', '', line, flags=re.IGNORECASE)
        # Also handle single-asterisk variant: *   *Burmese Draft:* 
        line = re.sub(r'^\s*\*\s*\*Burmese Draft:\*\s*', '', line, flags=re.IGNORECASE)
        line = re.sub(r'^\s*\*\s*\*Myanmar Draft:\*\s*', '', line, flags=re.IGNORECASE)
        
        # Skip lines that are just analysis markers (no actual Myanmar content)
        if re.match(r'^\s*[\*\-]?\s*\*+[^\u1000-\u109F]*\*+\s*$', original_line):
            continue
        # Skip lines with only "Refinement:", "Drafting:", etc. labels
        if re.match(r'^\s*[\*\-]?\s*\*+(Refinement|Drafting|Drafting Focus|Focus):\*+\s*$', original_line, re.IGNORECASE):
            continue
        # Skip analysis lines like "*   *Refinement:* Needs high literary tone." (no Myanmar text)
        if re.match(r'^\s*\*\s*\*(Refinement|Drafting|Focus|Key Concepts|Key elements|Tone):\*.*$', original_line, re.IGNORECASE):
            # Check if line has Myanmar text
            if not re.search(r'[\u1000-\u109F]', original_line):
                continue
        # Skip "Here's the actual Myanmar translation:" preamble
        if re.match(r'^Here.*?Myanmar translation[:;]', line, re.IGNORECASE):
            continue
        # Skip "Here's the actual translation:" preamble  
        if re.match(r'^Here.*?actual translation[:;]', line, re.IGNORECASE):
            continue
        
        # Keep the line (now cleaned of markers)
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def detect_language_leakage(text: str) -> dict[str, int]:
    """
    Count non-Myanmar language characters in output.
    Returns counts for Thai, Chinese, and English.
    Used for quality logging.
    """
    thai_count = len(_THAI_PATTERN.findall(text))
    chinese_count = len(_CHINESE_PATTERN.findall(text))
    latin_words = len(_LATIN_WORD_PATTERN.findall(text))
    english_common = len(_ENGLISH_COMMON_WORDS.findall(text))
    
    return {
        "thai_chars": thai_count,
        "chinese_chars": chinese_count,
        "latin_words": latin_words,
        "english_common_words": english_common,
        "has_english": latin_words > 0 or english_common > 0,
    }


def myanmar_char_ratio(text: str) -> float:
    """Return ratio of Myanmar Unicode characters to total non-whitespace chars."""
    non_ws = text.replace(" ", "").replace("\n", "").replace("\t", "")
    if not non_ws:
        return 0.0
    myanmar_count = len(_MYANMAR_PATTERN.findall(non_ws))
    return myanmar_count / len(non_ws)


def remove_chinese_characters(text: str) -> str:
    """Remove all Chinese characters from text."""
    return _CHINESE_PATTERN.sub("", text)


def remove_latin_words(text: str) -> str:
    """Remove Latin/English word leakage from Myanmar output."""
    # Remove 3+ letter Latin words (but preserve markdown syntax like **, *)
    text = _LATIN_WORD_PATTERN.sub("", text)
    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def clean_output(raw: str, aggressive: bool = False) -> str:
    """
    Full postprocessing pipeline. Apply in order:
    1. Strip reasoning tags (<think>, etc.)
    2. Strip reasoning process (model's analysis sections)
    3. Strip header artifacts
    4. Remove Chinese characters (model leakage) - only if aggressive=True
    5. Remove Latin words (English/German leakage) - only if aggressive=True
    6. Collapse 3+ blank lines → 2
    7. Strip leading/trailing whitespace
    
    Args:
        raw: Raw LLM output
        aggressive: If True, aggressively remove all Chinese/Latin characters.
                   If False (default), only strip tags and artifacts to prevent
                   over-processing that could corrupt Myanmar output (per need_fix.md).
    
    Returns:
        Cleaned text
    """
    text = strip_reasoning_tags(raw)
    text = strip_reasoning_process(text)
    text = strip_header_artifacts(text)
    
    # Fixed: Only aggressively remove Chinese/Latin if explicitly requested
    # Per need_fix.md: Over-aggressive post-processing can corrupt Myanmar script output
    if aggressive:
        text = remove_chinese_characters(text)
        text = remove_latin_words(text)
    else:
        # Light cleanup: only remove obvious leakage patterns, not all Latin/Chinese
        # This preserves intentional mixed content (like pinyin names in parentheses)
        pass
    
    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse excess blank lines
    text = text.strip()
    return text


def validate_output(text: str, chapter: int) -> dict:
    """
    Run quality checks on cleaned output.
    Returns a report dict for logging.
    
    Status levels:
    - APPROVED: >70% Myanmar, no Thai/Chinese, minimal English
    - NEEDS_REVIEW: Some issues but usable
    - REJECTED: Critical issues (Thai/Chinese detected or <30% Myanmar)
    """
    leakage = detect_language_leakage(text)
    ratio = myanmar_char_ratio(text)
    
    # Determine status - Chinese characters = automatic REJECT
    if leakage["thai_chars"] > 0:
        status = "REJECTED"
    elif leakage["chinese_chars"] > 0:
        status = "REJECTED"
    elif ratio < 0.30:
        status = "REJECTED"
    elif ratio < 0.70 or leakage["latin_words"] > 5:
        status = "NEEDS_REVIEW"
    else:
        status = "APPROVED"

    report = {
        "chapter": chapter,
        "myanmar_ratio": round(ratio, 3),
        "thai_chars_leaked": leakage["thai_chars"],
        "chinese_chars_leaked": leakage["chinese_chars"],
        "latin_words_found": leakage["latin_words"],
        "english_common_words": leakage["english_common_words"],
        "status": status,
    }
    return report


def is_valid_myanmar_syllable(text: str) -> bool:
    """
    Check if text contains valid Myanmar syllable structure.
    Myanmar syllables follow: consonant + (medial) + (vowel) + (tone)
    Returns ratio of valid syllables to total Myanmar characters.
    """
    if not text:
        return 0.0
    
    # Myanmar consonants (basic range)
    _MYANMAR_CONSONANTS = re.compile(r'[\u1000-\u1021]')
    
    # Common valid Myanmar patterns (simplified check)
    # Look for consonant followed by optional modifiers
    _VALID_SYLLABLE = re.compile(
        r'[\u1000-\u1021]'  # Consonant
        r'[\u1039\u103A]?'   # Optional: virama/asat
        r'[\u102D-\u1030\u1032\u1036\u1037\u1038]*'  # Optional: vowels/tone
    )
    
    myanmar_chars = len(_MYANMAR_PATTERN.findall(text))
    if myanmar_chars == 0:
        return 0.0
    
    valid_syllables = len(_VALID_SYLLABLE.findall(text))
    # Rough estimate: each syllable should have ~1-3 characters
    # If ratio is too low, text may be garbled
    return min(valid_syllables / (myanmar_chars * 0.3), 1.0) if myanmar_chars > 0 else 0.0


def detect_repetition(text: str, threshold: int = 3) -> dict:
    """
    Detect repetitive patterns in Myanmar text.

    Args:
        text: Text to analyze
        threshold: Number of repetitions to flag as problematic

    Returns:
        Dictionary with repetition metrics
    """
    from collections import Counter

    # Split into sentences (Myanmar uses ။ as period)
    sentences = [s.strip() for s in re.split(r'[။\n]+', text) if s.strip()]

    if not sentences:
        return {"has_repetition": False, "repeated_phrases": [], "unique_ratio": 1.0}

    # Count exact duplicates
    sentence_counts = Counter(sentences)

    repeated = []
    for sentence, count in sentence_counts.items():
        if count >= threshold:
            repeated.append({
                "sentence": sentence[:50] + "..." if len(sentence) > 50 else sentence,
                "count": count
            })

    # Calculate unique ratio
    unique_ratio = len(set(sentences)) / len(sentences) if sentences else 1.0

    return {
        "has_repetition": len(repeated) > 0,
        "repeated_sentences": repeated,
        "unique_ratio": unique_ratio
    }


def check_repetition(text: str, threshold: float = 0.35) -> bool:
    """
    Check if text has excessive sentence repetition.

    Args:
        text: Translated text to check
        threshold: Ratio of repeated sentences to trigger warning (0.35 = 35%)

    Returns:
        True if repetition ratio exceeds threshold
    """
    from collections import Counter

    if not text or len(text) < 100:
        return False

    # Split on Myanmar sentence ending (။) or newlines
    sentences = [s.strip() for s in re.split(r'[။\n]+', text)
                 if len(s.strip()) > 10]

    if len(sentences) < 5:  # Too short to analyze
        return False

    counts = Counter(sentences)
    repeated = sum(c for c in counts.values() if c > 1)

    repetition_ratio = repeated / len(sentences)
    return repetition_ratio > threshold