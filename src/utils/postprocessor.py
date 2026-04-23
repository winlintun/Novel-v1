"""
src/utils/postprocessor.py
Cleans raw LLM output before saving.
Strips: <think>, <answer>, HTML comments, non-Myanmar language leakage.
"""

import re
from typing import Optional


# Myanmar Unicode range: \u1000-\u109F (basic) + \uAA60-\uAA7F (extended)
_MYANMAR_PATTERN = re.compile(r"[\u1000-\u109F\uAA60-\uAA7F]")

# Tags from reasoning models (DeepSeek, Hunyuan, Qwen-thinking, etc.)
_TAG_PATTERNS: list[re.Pattern] = [
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"</?think>", re.IGNORECASE),
    re.compile(r"<answer>", re.IGNORECASE),
    re.compile(r"</answer>", re.IGNORECASE),
    re.compile(r"<!--.*?-->", re.DOTALL),               # HTML comments (metadata block)
]

# Stray header artifacts left by models
_HEADER_ARTIFACTS: list[re.Pattern] = [
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
    Returns counts for Thai and Chinese.
    Used for quality logging.
    """
    return {
        "thai_chars": len(_THAI_PATTERN.findall(text)),
        "chinese_chars": len(_CHINESE_PATTERN.findall(text)),
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
    """
    leakage = detect_language_leakage(text)
    ratio = myanmar_char_ratio(text)

    report = {
        "chapter": chapter,
        "myanmar_ratio": round(ratio, 3),
        "thai_chars_leaked": leakage["thai_chars"],
        "chinese_chars_leaked": leakage["chinese_chars"],
        "status": "APPROVED" if ratio >= 0.70 and leakage["thai_chars"] == 0 else "NEEDS_REVIEW",
    }
    return report