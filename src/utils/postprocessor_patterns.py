"""
Postprocessor Patterns - Regex patterns for cleaning LLM output.
Extracted from postprocessor.py for better organization.
"""

import re
from typing import List, Pattern

# Myanmar Unicode range: U+1000-U+109F (basic) + U+AA60-U+AA7F (Extended-A) + U+A9E0-U+A9FF (Extended-B)
MYANMAR_PATTERN = re.compile(r"[\u1000-\u109F\uAA60-\uAA7F\uA9E0-\uA9FF]")

# Tags from reasoning models (DeepSeek, Hunyuan, Qwen-thinking, etc.)
TAG_PATTERNS: List[Pattern] = [
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"</?think>", re.IGNORECASE),
    re.compile(r"<answer>", re.IGNORECASE),
    re.compile(r"</answer>", re.IGNORECASE),
    re.compile(r"<!--.*?-->", re.DOTALL),
]

# Stray header artifacts left by models
HEADER_ARTIFACTS: List[Pattern] = [
    re.compile(r"^MYANMAR TRANSLMENT:.*$", re.MULTILINE),
    re.compile(r"^MYANMAR TRANSLATION:.*$", re.MULTILINE),
    re.compile(r"^TEXT TO TRANSLATE:.*$", re.MULTILINE),
    re.compile(r"^INPUT TEXT.*?:.*$", re.MULTILINE),
    re.compile(r"^Translation Progress:.*$", re.MULTILINE),
]

# Model reasoning/thinking process patterns (NOT actual translation output)
REASONING_PATTERNS: List[Pattern] = [
    re.compile(r"Here's a thinking process.*?(?=^\d+\s+\*\*Analyze|$)", re.DOTALL | re.MULTILINE),
    re.compile(r"Here's a thinking process.*?^(?=\d+\.|Here is|\*\*Burmese Draft|\*\*Myanmar Draft|# |\[|^[^\*a-zA-Z])", re.DOTALL | re.MULTILINE),
    re.compile(r"^\d+\.\s+\*\*Analyze the Request and Constraints:\*\*.*?^(?=\d+\.|\*\*|$)", re.DOTALL | re.MULTILINE),
    re.compile(r"^\d+\.\s+\*\*Analyze the Glossary:\*\*.*?^(?=\d+\.|\*\*|$)", re.DOTALL | re.MULTILINE),
    re.compile(r"^\d+\.\s+\*\*Analyze the Source Text.*?\*\*.*?^(?=\d+\.|\*\*|$)", re.DOTALL | re.MULTILINE),
    re.compile(r"^\d+\.\s+\*\*Segment and Translate.*?\*\*.*?^(?=\*\*Burmese Draft|\*\*Myanmar Draft|\d+\.|Here is|$)", re.DOTALL | re.MULTILINE),
    re.compile(r"^\s*\*\*(Refinement|Drafting|Drafting Focus|Focus):\*\*.*?^(?=\*\*Burmese|\*\*Myanmar|\d+\.|Here is|$)", re.DOTALL | re.MULTILINE),
    re.compile(r"^\s*\*\s+\*Original:\*.*?$", re.MULTILINE),
    re.compile(r"^\s*\*\s+\*Key.*?\*.*?$", re.MULTILINE),
    re.compile(r"^\s*\*\s+\*Tone.*?\*.*?$", re.MULTILINE),
    re.compile(r"^\s*\*\s+\*Key elements.*?\*.*?$", re.MULTILINE),
    re.compile(r"^\s*\[.\]\s+\w+\s+=.*?$", re.MULTILINE),
    re.compile(r"^\d+\.\s+\*\*Glossary Check & Term Mapping:\*\*.*?^(?=\d+\.|\*\*|$)", re.DOTALL | re.MULTILINE),
    re.compile(r"^\d+\.\s+\*\*Translation Strategy.*?\*\*.*?^(?=\d+\.|\*\*|$)", re.DOTALL | re.MULTILINE),
    re.compile(r"^\s*\*\s+\w+\s+=\s+.*?(?:\(.*?\))*$", re.MULTILINE),
    re.compile(r"\*Drafting:\*|\*Refinement:\*", re.MULTILINE),
    re.compile(r"\(This is.*?\)", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*\*\s*$", re.MULTILINE),
    re.compile(r"^\s*\*[\s:]*\*.*?\"[\u1000-\u109F]+\".*?(?:is|be|of|on|a|an|the)\b.*$", re.MULTILINE),
    re.compile(r"^\s*\*[\s:]*\*[\s,.]*$", re.MULTILINE),
    re.compile(r"^\s*\*[\s:]*\*.*?to\s*/\.\s*.*$", re.MULTILINE),
    re.compile(r"^\s*-\s*\[[\w\s]+\]:\s.*(?:to|of|a|an|the|is|are)\b.*$", re.MULTILINE),
    re.compile(r"^\s*-\s*\[\s*\]\s*$", re.MULTILINE),
]

# Thai Unicode range - should never appear in Myanmar output
THAI_PATTERN = re.compile(r"[\u0E00-\u0E7F]+")

# Bengali Unicode range - should never appear in Myanmar output
BENGALI_PATTERN = re.compile(r"[\u0980-\u09FF]+")

# Tamil and other Indic scripts - should never appear in Myanmar output
INDIC_PATTERN = re.compile(
    r"[\u0900-\u097F\u0A00-\u0A7F\u0A80-\u0AFF\u0B00-\u0B7F\u0B80-\u0BFF"
    r"\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F\u0D80-\u0DFF]+"
)

# Korean Hangul characters - should not appear in Myanmar output
KOREAN_PATTERN = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF\u3000-\u303F]+")

# Chinese characters - should not remain in translated output body
CHINESE_PATTERN = re.compile(r"[\u4E00-\u9FFF\u3400-\u4DBF]+")

# English/Latin characters - should be minimized in Myanmar output
LATIN_WORD_PATTERN = re.compile(r"[a-zA-Z]{3,}")

# English common words that indicate language drift
ENGLISH_COMMON_WORDS = re.compile(
    r'\b(the|and|for|are|but|not|you|all|can|had|her|was|one|our|out|day|get|has|him|his|how|its|may|new|now|old|see|two|who|boy|did|she|use|her|way|many|oil|sit|set|run|eat|far|sea|eye|ago|off|too|any|say|man|try|ask|end|why|let|put|far|few|did|she|try|way|own|say|too|old|tell|very|when|much|would|there|their|what|said|each|which|will|about|could|other|after|first|never|these|think|where|being|every|great|might|shall|still|those|while|this|that|with|from|they|have|were|been|time|than|them|into|just|like|over|also|back|only|know|take|year|good|some|come|make|well|look|down|most|long|find|here|both|made|part|even|more|such|work|life|right|through|during|before|between|should|however|something|someone|because|without|another|nothing|everything|everyone|really|always|around|another|within|another|himself|herself|itself|myself|yourself|themselves|yourselves|ourselves)\b',
    re.IGNORECASE
)