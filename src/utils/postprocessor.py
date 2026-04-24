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


def clean_output(raw: str) -> str:
    """
    Full postprocessing pipeline. Apply in order:
    1. Strip reasoning tags
    2. Strip header artifacts
    3. Collapse 3+ blank lines → 2
    4. Strip leading/trailing whitespace
    """
    text = strip_reasoning_tags(raw)
    text = strip_header_artifacts(text)
    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse excess blank lines
    text = text.strip()
    return text


def validate_output(text: str, chapter: int) -> dict:
    """
    Run quality checks on cleaned output.
    Returns a report dict for logging.
    
    Status levels:
    - APPROVED: >70% Myanmar, no Thai, minimal English
    - NEEDS_REVIEW: Some issues but usable
    - REJECTED: Critical issues (Thai detected or <30% Myanmar)
    """
    leakage = detect_language_leakage(text)
    ratio = myanmar_char_ratio(text)
    
    # Determine status
    if leakage["thai_chars"] > 0:
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