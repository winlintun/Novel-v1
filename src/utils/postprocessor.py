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
    re.compile(r"^\s*\*\s+\*Original:\*.*?$", re.MULTILINE),
    re.compile(r"^\s*\*\s+\*Key.*?\*.*?$", re.MULTILINE),
    re.compile(r"^\s*\*\s+\*Tone.*?\*.*?$", re.MULTILINE),
    re.compile(r"^\s*\*\s+\*Key elements.*?\*.*?$", re.MULTILINE),
    # Remove glossary checkboxes like "[○] Luo Qing = ..."
    re.compile(r"^\s*\[.\]\s+\w+\s+=.*?$", re.MULTILINE),
    # NEW: Remove "Glossary Check & Term Mapping" sections (padauk-gemma format)
    re.compile(r"^\d+\.\s+\*\*Glossary Check & Term Mapping:\*\*.*?^(?=\d+\.|\*\*|$)", re.DOTALL | re.MULTILINE),
    # NEW: Remove "Translation Strategy" sections
    re.compile(r"^\d+\.\s+\*\*Translation Strategy.*?\*\*.*?^(?=\d+\.|\*\*|$)", re.DOTALL | re.MULTILINE),
    # NEW: Remove bullet points with term mappings like "*   Fang Yuan = ..."
    re.compile(r"^\s*\*\s+\w+\s+=\s+.*?(?:\(.*?\))*$", re.MULTILINE),
    # NEW: Remove "Drafting:" and "Refinement:" inline markers
    re.compile(r"\*Drafting:\*|\*Refinement:\*", re.MULTILINE),
    # NEW: Remove parenthetical notes like "(This is already provided...)"
    re.compile(r"\(This is.*?\)", re.MULTILINE | re.IGNORECASE),
    # NEW: Remove lines with only bullet markers and no Myanmar
    re.compile(r"^\s*\*\s*$", re.MULTILINE),
    # PADAUK-GEMMA: Glossary comparison garbage lines
    # Pattern: *:* A . "မြန်မာစကားလုံး" is . "နောက်ထပ်" is .
    re.compile(r"^\s*\*[\s:]*\*.*?\"[\u1000-\u109F]+\".*?(?:is|be|of|on|a|an|the)\b.*$", re.MULTILINE),
    # Pattern: * :* , .  or  * :* . .  (short garbage fragments)
    re.compile(r"^\s*\*[\s:]*\*[\s,.]*$", re.MULTILINE),
    # Pattern: *:* to /. "word" is ...
    re.compile(r"^\s*\*[\s:]*\*.*?to\s*/\.\s*.*$", re.MULTILINE),
]

# Thai Unicode range — should never appear in Myanmar output
_THAI_PATTERN = re.compile(r"[\u0E00-\u0E7F]+")

# Bengali Unicode range — should never appear in Myanmar output
_BENGALI_PATTERN = re.compile(r"[\u0980-\u09FF]+")

# Tamil and other Indic scripts — should never appear in Myanmar output
# Tamil (U+0B80-U+0BFF), Telugu (U+0C00-U+0C7F), Kannada (U+0C80-U+0CFF)
# Malayalam (U+0D00-U+0D7F), Sinhala (U+0D80-U+0DFF), Devanagari (U+0900-U+097F)
# Gujarati (U+0A80-U+0AFF), Oriya (U+0B00-U+0B7F), Gurmukhi (U+0A00-U+0A7F)
_INDIC_PATTERN = re.compile(
    r"[\u0900-\u097F\u0A00-\u0A7F\u0A80-\u0AFF\u0B00-\u0B7F\u0B80-\u0BFF"
    r"\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F\u0D80-\u0DFF]+"
)

# Korean Hangul characters — should not appear in Myanmar output
_KOREAN_PATTERN = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF\u3000-\u303F]+")

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
    skip_section = False

    for line in lines:
        original_line = line
        stripped = line.strip()

        # Detect section headers to skip (numbered sections with **)
        if re.match(r'^\s*\d+\.\s+\*\*.*?:\*\*', original_line):
            skip_section = True
            continue

        # If we were skipping a section and hit a blank line or new section, stop skipping
        if skip_section and (not stripped or re.match(r'^\s*\d+\.\s+', line)):
            skip_section = False
            if not stripped:
                continue

        # Skip lines within analysis sections
        if skip_section:
            continue

        # Skip lines that are just bullet points without Myanmar content
        if re.match(r'^\s*\*\s*\w+\s*=', original_line):
            continue

        # Skip lines with only analysis markers (no actual Myanmar content)
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

        # Remove "**Burmese Draft:**" or "**Myanmar Draft:**" markers with optional leading bullet
        line = re.sub(r'^\s*[\*\-]?\s*\*\*Burmese Draft:\*\*\s*', '', line, flags=re.IGNORECASE)
        line = re.sub(r'^\s*[\*\-]?\s*\*\*Myanmar Draft:\*\*\s*', '', line, flags=re.IGNORECASE)
        # Also handle single-asterisk variant: *   *Burmese Draft:*
        line = re.sub(r'^\s*\*\s*\*Burmese Draft:\*\s*', '', line, flags=re.IGNORECASE)
        line = re.sub(r'^\s*\*\s*\*Myanmar Draft:\*\s*', '', line, flags=re.IGNORECASE)

        # Remove standalone bullet points at start of line (keeping Myanmar content)
        line = re.sub(r'^\s*\*\s+', '', line)

        # Remove inline *Drafting:* and *Refinement:* markers
        line = re.sub(r'\*Drafting:\*|\*Refinement:\*', '', line, flags=re.IGNORECASE)

        # Remove parenthetical English explanations
        line = re.sub(r'\(This is.*?\)', '', line, flags=re.IGNORECASE)
        line = re.sub(r'\(.*?\)', '', line)  # Remove all parenthetical content

        # Skip padauk-gemma glossary comparison garbage lines (*:* pattern)
        # These look like: *:* "word" is . "other" is .
        # Or: * :* , .  (short garbage fragments with English)
        # NOTE: requires colon between asterisks to avoid matching **bold** markdown
        if re.match(r'^\s*\*[\s:]*:[\s:]*\*', original_line):
            continue

        # Skip empty lines or lines with only whitespace
        if not line.strip():
            continue

        # Keep the line (now cleaned of markers)
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def detect_language_leakage(text: str) -> dict[str, int]:
    """
    Count non-Myanmar language characters in output.
    Returns counts for Thai, Bengali, Indic, Chinese, and English.
    Used for quality logging.
    """
    thai_count = len(_THAI_PATTERN.findall(text))
    bengali_count = len(_BENGALI_PATTERN.findall(text))
    indic_count = len(_INDIC_PATTERN.findall(text))
    chinese_count = len(_CHINESE_PATTERN.findall(text))
    latin_words = len(_LATIN_WORD_PATTERN.findall(text))
    english_common = len(_ENGLISH_COMMON_WORDS.findall(text))

    return {
        "thai_chars": thai_count,
        "bengali_chars": bengali_count,
        "indic_chars": indic_count,
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


def remove_bengali_characters(text: str) -> str:
    """Remove all Bengali characters from text."""
    return _BENGALI_PATTERN.sub("", text)


def remove_indic_characters(text: str) -> str:
    """Remove all Indic-script characters (Tamil, Telugu, Kannada, etc.) from text."""
    return _INDIC_PATTERN.sub("", text)


def remove_korean_characters(text: str) -> str:
    """Remove all Korean Hangul characters from text."""
    return _KOREAN_PATTERN.sub("", text)


def remove_latin_words(text: str) -> str:
    """Remove Latin/English word leakage from Myanmar output."""
    # Remove 3+ letter Latin words (but preserve markdown syntax like **, *)
    text = _LATIN_WORD_PATTERN.sub("", text)
    # Clean up extra horizontal whitespace (spaces/tabs) but preserve newlines
    # Using [^\S\n]+ collapses runs of horizontal whitespace only,
    # leaving paragraph breaks (\\n\\n) intact
    text = re.sub(r'[^\S\n]+', ' ', text)
    return text.strip()


def fix_chapter_heading_format(text: str) -> str:
    """Fix chapter headings that are concatenated on a single line.
    
    The model may output '# အခန်း ၁၂ ## Title text' (H1 + H2 + body
    all on one line). Or '# အခန်း ၁၇: Title' (colon-separated).
    Split into proper markdown:
        # အခန်း ၁၂
        ## Title
        body text...
    
    Works on both multi-line and single-line (collapsed) text.
    """
    # Pattern 1: "# အခန်း N ## subtitle body..." — H1 + H2 on one line
    text = re.sub(
        r'(#\s+အခန်း\s+[\u1040-\u1049\d]+.*?)\s*##\s+',
        r'\1\n\n## ',
        text
    )

    # Pattern 2: "# အခန်း N: Title" — colon-separated (no H2 marker)
    text = re.sub(
        r'^(#\s+အခန်း\s+[\u1040-\u1049\d]+)\s*:\s*(.+)',
        r'\1\n\n## \2',
        text,
        flags=re.MULTILINE
    )

    return text


def _split_into_lines_if_needed(text: str) -> str:
    """Recover paragraph structure from single-line collapsed text.
    
    If remove_latin_words collapsed all whitespace to spaces (old bug),
    this function restores newlines by splitting at chapter heading
    boundaries and Myanmar sentence-enders (။).
    """
    if '\n' in text:
        return text  # Already has line breaks

    # Split at each '# အခန်း N' to restore heading boundaries
    text = re.sub(
        r'(#\s+အခန်း\s+[\u1040-\u1049\d]+\s*)',
        r'\n\1',
        text
    )

    # Split after Myanmar sentence-ending marker ။ followed by space
    # to restore paragraph/sentence boundaries
    text = re.sub(r'(။)\s+', r'\1\n\n', text)

    return text.strip()


def remove_duplicate_headings(text: str) -> str:
    """Remove duplicate chapter headings within the body.
    
    The translator may repeat '# အခန်း N ## Title' at the start of
    every chunk. Keep only the first occurrence and skip its associated
    subtitle line and blank spacer lines.

    Uses prefix matching: '# အခန်း ၁၃: Title A' and '# အခန်း ၁၃'
    are both treated as the same chapter heading block.
    
    Also handles bare '# အခန်း' without a number (model truncation).
    """
    seen_chapters: set[str] = set()
    seen_bare_heading = False
    lines = text.split('\n')
    result: list[str] = []
    in_duplicate_block = False

    for line in lines:
        stripped = line.strip().lstrip('\ufeff')

        # Detect chapter heading: '# အခန်း N...' or bare '# အခန်း'
        heading_match = re.match(
            r'^(#\s+အခန်း(?:\s+[\u1040-\u1049\d]+)?)',
            stripped
        )
        if heading_match:
            chapter_prefix = heading_match.group(1)
            # Check if bare heading '# အခန်း' (no number)
            is_bare = chapter_prefix.rstrip() == '# အခန်း'
            if is_bare:
                # If we've already seen ANY chapter heading, bare heading is duplicate
                if seen_bare_heading or seen_chapters:
                    in_duplicate_block = True
                    continue
                seen_bare_heading = True
                in_duplicate_block = False
                result.append(line)
                continue

            if chapter_prefix in seen_chapters:
                in_duplicate_block = True
                continue
            # New numbered chapter heading
            in_duplicate_block = False
            seen_chapters.add(chapter_prefix)
            result.append(line)
        elif in_duplicate_block:
            # Skip subtitle (## ...), spacer lines (---, blank), and heading variant lines
            if stripped.startswith('## ') or not stripped or stripped.startswith('---'):
                continue
            # Reached body text — exit skip mode and keep this line
            in_duplicate_block = False
            result.append(line)
        else:
            result.append(line)

    return '\n'.join(result)


def detect_potential_hallucinations(text: str, known_terms: Optional[set] = None) -> List[str]:
    """Detect Myanmar proper names that may be LLM hallucinations.
    
    Compares proper-name-like sequences against a set of known glossary 
    target terms. Names found in the text but NOT in the glossary are
    flagged for human review.
    
    A 'proper name' is a 2-8 Myanmar-syllable sequence that appears
    repeatedly (2+ times) at sentence boundaries — common for named
    characters and places.
    
    Args:
        text: Translated Myanmar text
        known_terms: Set of approved Myanmar target terms from glossary
        
    Returns:
        List of potentially hallucinated name strings
    """
    if known_terms is None:
        known_terms = set()

    # Extract 2-8 character Myanmar sequences that appear multiple times
    # at the start of sentences (common position for proper names in narration)
    from collections import Counter

    # Find Myanmar sequences that could be names: 2-8 chars long, appearing
    # after sentence-enders or paragraph starts
    candidates = re.findall(
        r'(?:^|\n|[။]\s+|၊\s+)([\u1000-\u109F]{2,8})\s+(?:သည်|က|မှာ|ကို|၏|၌)',
        text,
        re.MULTILINE
    )

    counts = Counter(candidates)

    # A name candidate must appear at least 2 times (to filter noise)
    warnings = []
    for name, count in counts.items():
        if count >= 2 and name not in known_terms:
            # Also filter common non-name words
            common_words = {
                'တစ်ခု', 'တစ်ယောက်', 'အခါ', 'သူတို့', 'တစ်ဦး',
                'ကျွန်တော်', 'တစ်ချိန်', 'တစ်ခါ', 'ဒီအတွက်',
                'တစ်စုံ', 'ဘယ်သူ', 'ဘယ်လို', 'အဲဒီ', 'ဒါပေမယ့်',
                'သူတို့ရဲ့', 'ဘာဖြစ်', 'အဲဒီမှာ', 'အဲဒါ',
                'ဘယ်လောက်', 'ဒီလို', 'ဒါဟာ', 'ဒါကြောင့်',
                'အဲဒီအခါ', 'သို့သော်', 'ထို့ကြောင့်', 'အလွန်',
                'သူသည်', 'ဒါပေမဲ့', 'ထိုအခါ', 'တစ်ခုမှာ',
            }
            if name in common_words:
                continue
            warnings.append(name)

    return warnings


def replace_archaic_words(text: str) -> str:
    """Replace archaic Myanmar words with modern alternatives.
    
    Archaic → Modern:
        ဤ (this) → ဒီ
        ထို (that) → အဲဒီ
        သင်သည် (you) → မင်း
    
    Uses Myanmar-specific word boundaries (not \\b which breaks on
    combining marks in Unicode Myanmar). Only replaces when the
    archaic word is NOT followed by another Myanmar consonant letter
    (possibly with intervening combining marks), meaning it's
    a standalone word, not part of a compound like ထိုင်ခိုင်း.
    """
    if not text:
        return text

    # Myanmar consonant range: U+1000-U+1021 (က-အ) + independent vowels U+1023-U+102A
    # Combining marks: virama U+1039, asat U+103A, vowels U+102C-1032, tones U+1036-1038
    _MYANMAR_CONSONANT = r'[\u1000-\u1021\u1023-\u102A]'
    _MYANMAR_COMBINING = r'[\u1039\u103A\u102C-\u1032\u1036-\u1038]*'

    # Lookbehind: NOT preceded by a Myanmar consonant letter
    # Lookahead: NOT followed by (combining marks + consonant) — i.e. standalone

    # ဤ → ဒီ
    text = re.sub(
        r'(?<!' + _MYANMAR_CONSONANT + r')ဤ(?!' + _MYANMAR_COMBINING + _MYANMAR_CONSONANT + r')',
        'ဒီ', text
    )
    # ထို → အဲဒီ
    text = re.sub(
        r'(?<!' + _MYANMAR_CONSONANT + r')ထို(?!' + _MYANMAR_COMBINING + _MYANMAR_CONSONANT + r')',
        'အဲဒီ', text
    )
    # သင်သည် → မင်း
    text = re.sub(
        r'(?<!' + _MYANMAR_CONSONANT + r')သင်သည်(?!' + _MYANMAR_COMBINING + _MYANMAR_CONSONANT + r')',
        'မင်း', text
    )
    return text


def undo_archaic_corruptions(text: str) -> str:
    """Fix corruptions caused by the old \\b-based replace_archaic_words().
    
    The old regex corrupted compound words like:
        ထိုင်၍ → အဲဒီင်၍  (\\bထို\\b matched inside ထိုင်)
        ထိုင်းပြီး → အဲဒီင်းပြီး
        စိုထိုင်းပြီး → စိုအဲဒီင်းပြီး
    
    Undo: အဲဒီင → ထိုင (restore the original consonant cluster)
    Also handles အဲဒီ followed directly by combining marks.
    """
    if not text:
        return text

    # Fix 1: အဲဒီ directly followed by Myanmar combining mark → replace with ထို
    text = re.sub(r'အဲဒီ(?=[\u1039\u103A\u102C-\u1032\u1036-\u1038])', 'ထို', text)

    # Fix 2: အဲဒီင → ထိုင (restores ထိုင်, ထိုင်း, etc. from compound corruptions)
    text = re.sub(r'အဲဒီင', 'ထိုင', text)

    # Fix 3: အဲဒီဟ → ထိုဟ (for ထိုဟန် etc.)
    text = re.sub(r'အဲဒီဟ', 'ထိုဟ', text)

    return text


def fix_degraded_placeholders(text: str) -> str:
    """Fix degraded placeholders: 【??】 → 【?term?】.
    
    Also handle variants like 【?】, 【??】, 【???】.
    """
    if not text:
        return text
    # Replace any degraded 【?*】 pattern with standard 【?term?】
    text = re.sub(r'【\?+\s*】', '【?term?】', text)
    return text


def strip_translated_metadata(text: str) -> str:
    """Remove Myanmar-translated translator/editor credit lines from output.
    
    The model sometimes translates English credit lines like
    'Translator: Skyfarrow Editor: Skyfarrow' into Myanmar:
    'ဘာသာပြန်သူ- ... တည်းဖြတ်သူ- ...'
    
    Also handles standalone credit markers.
    """
    if not text:
        return text
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        # Detect Myanmar credit lines (model-translated metadata)
        if re.match(r'^ဘာသာပြန်သူ[-:]', stripped, re.IGNORECASE):
            continue
        if re.match(r'^တည်းဖြတ်သူ[-:]', stripped, re.IGNORECASE):
            continue
        result.append(line)
    return '\n'.join(result)


def ensure_markdown_readability(text: str) -> str:
    """Ensure output has proper paragraph separation for readability.
    
    - Adds blank lines between consecutive content paragraphs that lack them
    - Preserves existing blank lines (does not remove them)
    - Proper heading spacing: blank line before and after H1/H2
    - No more than 2 consecutive blank lines
    """
    if not text:
        return text

    lines = text.split('\n')
    result: list[str] = []
    in_blank_run = False

    for line in lines:
        stripped = line.strip()
        is_blank = not stripped

        # Handle blank lines: allow up to 2 consecutive blanks
        if is_blank:
            if in_blank_run and result and result[-1] == '':
                # Already have 1 blank, this makes 2 -> skip
                continue
            if result and result[-1] != '':
                result.append('')
            in_blank_run = True
            continue

        in_blank_run = False

        # Detect headings
        is_heading = stripped.startswith('#')

        # Add blank line before heading if previous line was content
        if is_heading and result and result[-1] != '':
            result.append('')

        result.append(stripped)

        # Add blank line after H1 heading
        if stripped.startswith('# ') and not stripped.startswith('## '):
            result.append('')

    # Post-pass: add blank lines between consecutive non-heading content paragraphs
    # that are NOT already separated by blank lines
    final: list[str] = []
    for i, line in enumerate(result):
        if i > 0 and line and result[i-1] and line != '' and result[i-1] != '':
            # Two consecutive content lines without blank between them
            prev_is_heading = result[i-1].startswith('#')
            curr_is_heading = line.startswith('#')
            if not prev_is_heading and not curr_is_heading:
                final.append('')
        final.append(line)

    # Remove leading/trailing blanks
    while final and final[0] == '':
        final.pop(0)
    while final and final[-1] == '':
        final.pop()

    return '\n'.join(final)


def stitch_chunk_boundaries(text: str) -> str:
    """Stitch sentences cut at chunk boundaries.
    
    When chunks are joined with '\n\n', a sentence that was split at the
    chunk boundary gets a paragraph break in the middle. This function
    detects and joins such fragments.

    Two strategies:
    1. Next line starts with medial character (mid-word continuation)
    2. Line ends without sentence-ender AND is short (< SHORT_LINE_THRESHOLD → truncation),
       next line contains Myanmar content AND isn't a heading/separator
    """
    # Threshold below which a line ending without sentence-ender is
    # considered likely truncated at a chunk boundary (vs a legit short line)
    SHORT_LINE_THRESHOLD = 150

    _ENDER_SET = {'။', '၊', '"', '\u201d', "'", '!', '?', '၏'}
    _SEPARATORS = ('---', '***', '===')
    _MYANMAR_RE = re.compile(r'[\u1000-\u109F]')

    def _has_myanmar(s: str) -> bool:
        return bool(_MYANMAR_RE.search(s))

    def _is_ender(line: str) -> bool:
        stripped = line.rstrip()
        if not stripped:
            return False
        return stripped[-1] in _ENDER_SET

    def _is_medial_continuation(line: str) -> bool:
        """Line starts with medial/vowel tone that indicates mid-word continuation."""
        if not line:
            return False
        code = ord(line[0])
        return (0x102C <= code <= 0x1032 or
                code in (0x1036, 0x1037, 0x1038, 0x1039, 0x103A))

    def _is_short_truncated(line: str) -> bool:
        """Line ends without sentence-ender and is relatively short (< threshold)."""
        stripped = line.rstrip()
        return len(stripped) < SHORT_LINE_THRESHOLD and not _is_ender(stripped) and _has_myanmar(stripped)

    lines = text.split('\n')
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            result.append('')
            i += 1
            continue

        is_separator = any(stripped.startswith(s) for s in _SEPARATORS)
        if is_separator:
            result.append(stripped)
            i += 1
            continue

        # Check for truncated sentence at chunk boundary
        if not _is_ender(stripped) and i + 1 < len(lines):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                next_content = lines[j].strip()
                if (next_content
                    and not next_content.startswith('#')
                    and not any(next_content.startswith(s) for s in _SEPARATORS)
                    and not next_content[0].isdigit()
                    and next_content[0] not in '*-'):
                    # Strategy 1: next line starts with medial character (continuation)
                    if _is_medial_continuation(next_content):
                        result.append(stripped + next_content)
                        i = j + 1
                        continue
                    # Strategy 2: line is short and ends without ender (likely truncation)
                    if _is_short_truncated(stripped) and _has_myanmar(next_content):
                        result.append(stripped + next_content)
                        i = j + 1
                        continue

        result.append(stripped)
        i += 1

    return '\n'.join(result)


def clean_output(raw: str, aggressive: bool = False) -> str:
    """
    Full postprocessing pipeline. Apply in order:
    1. Strip reasoning tags (<think>, etc.)
    2. Strip reasoning process (model's analysis sections)
    3. Strip header artifacts
    4. Strip translated metadata lines (credit: ဘာသာပြန်သူ- etc.)
    5. Stitch chunk boundary fragments (join truncated sentences)
    6. Remove Chinese/Bengali leakage (Bengali ALWAYS, Latin only if aggressive)
    7. Fix degraded placeholders: 【??】 → 【?term?】
    8. Replace archaic words: ဤ→ဒီ, ထို→အဲဒီ
    9. Collapse 3+ blank lines → 2
    10. Fix chapter heading format (# X ## Y → proper markdown)
    11. Remove duplicate chapter headings
    12. Ensure markdown readability (paragraph breaks, heading spacing)
    13. Strip leading/trailing whitespace
    
    Args:
        raw: Raw LLM output
        aggressive: If True, also remove Latin/English words.
    
    Returns:
        Cleaned text
    """
    text = strip_reasoning_tags(raw)
    text = strip_reasoning_process(text)
    text = strip_header_artifacts(text)

    # Remove Myanmar-translated metadata lines (translator/editor credit)
    text = strip_translated_metadata(text)

    # Stitch fragments at chunk boundaries
    text = stitch_chunk_boundaries(text)

    # Always strip Chinese, Bengali, and other Indic scripts (unambiguous garbage)
    text = remove_chinese_characters(text)
    text = remove_bengali_characters(text)
    text = remove_indic_characters(text)
    text = remove_korean_characters(text)

    # Only remove Latin words if aggressive mode
    if aggressive:
        text = remove_latin_words(text)

    # Fix degraded placeholders
    text = fix_degraded_placeholders(text)

    # Undo corruptions from old \b-based archaic word replacement (pre-existing)
    text = undo_archaic_corruptions(text)

    # Replace archaic Myanmar words with modern equivalents
    text = replace_archaic_words(text)

    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse excess blank lines
    text = _split_into_lines_if_needed(text)  # recover structure from collapsed text
    text = fix_chapter_heading_format(text)
    text = remove_duplicate_headings(text)
    text = ensure_markdown_readability(text)  # proper paragraph breaks, heading spacing
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

    # Determine status - Chinese, Bengali, Indic characters = automatic REJECT
    if leakage.get("thai_chars", 0) > 0:
        status = "REJECTED"
    elif leakage.get("bengali_chars", 0) > 0:
        status = "REJECTED"
    elif leakage.get("indic_chars", 0) > 0:
        status = "REJECTED"
    elif leakage.get("chinese_chars", 0) > 0:
        status = "REJECTED"
    elif ratio < 0.30:
        status = "REJECTED"
    elif ratio < 0.70 or leakage.get("latin_words", 0) > 5:
        status = "NEEDS_REVIEW"
    else:
        status = "APPROVED"

    report = {
        "chapter": chapter,
        "myanmar_ratio": round(ratio, 3),
        "thai_chars_leaked": leakage.get("thai_chars", 0),
        "bengali_chars_leaked": leakage.get("bengali_chars", 0),
        "indic_chars_leaked": leakage.get("indic_chars", 0),
        "chinese_chars_leaked": leakage.get("chinese_chars", 0),
        "latin_words_found": leakage.get("latin_words", 0),
        "english_common_words": leakage.get("english_common_words", 0),
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


class Postprocessor:
    """
    Postprocessor class wrapper for the postprocessing functions.
    Provides a clean() method for compatibility with the pipeline orchestrator.
    """

    def __init__(self, aggressive: bool = False):
        """
        Initialize the postprocessor.

        Args:
            aggressive: If True, aggressively remove all Chinese/Latin characters.
        """
        self.aggressive = aggressive

    def clean(self, text: str) -> str:
        """
        Clean the raw LLM output.

        Args:
            text: Raw text from LLM

        Returns:
            Cleaned text
        """
        return clean_output(text, aggressive=self.aggressive)
