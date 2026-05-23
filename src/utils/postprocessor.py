"""
src/utils/postprocessor.py
Cleans raw LLM output before saving.
Strips: <think>, <answer>, HTML comments, non-Myanmar language leakage.
"""

import re
from typing import Optional, List

# Import patterns from submodule (extracted for better organization)
from src.utils.postprocessor_patterns import (
    MYANMAR_PATTERN,
    TAG_PATTERNS,
    HEADER_ARTIFACTS,
    REASONING_PATTERNS,
    THAI_PATTERN,
    KHMER_PATTERN,
    BENGALI_PATTERN,
    INDIC_PATTERN,
    KOREAN_PATTERN,
    CHINESE_PATTERN,
    LATIN_WORD_PATTERN,
    ENGLISH_COMMON_WORDS,
)

# Backward compatibility: alias old underscore names for internal use
_MYANMAR_PATTERN = MYANMAR_PATTERN
_TAG_PATTERNS = TAG_PATTERNS
_HEADER_ARTIFACTS = HEADER_ARTIFACTS
_REASONING_PATTERNS = REASONING_PATTERNS
_THAI_PATTERN = THAI_PATTERN
_KHMER_PATTERN = KHMER_PATTERN
_BENGALI_PATTERN = BENGALI_PATTERN
_INDIC_PATTERN = INDIC_PATTERN
_KOREAN_PATTERN = KOREAN_PATTERN
_CHINESE_PATTERN = CHINESE_PATTERN
_LATIN_WORD_PATTERN = LATIN_WORD_PATTERN
_ENGLISH_COMMON_WORDS = ENGLISH_COMMON_WORDS


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
    Returns counts for Thai, Khmer, Bengali, Indic, Chinese, Korean, and English.
    Used for quality logging.
    """
    thai_count = len(_THAI_PATTERN.findall(text))
    khmer_count = len(_KHMER_PATTERN.findall(text))
    bengali_count = len(_BENGALI_PATTERN.findall(text))
    indic_count = len(_INDIC_PATTERN.findall(text))
    chinese_count = len(_CHINESE_PATTERN.findall(text))
    korean_count = len(_KOREAN_PATTERN.findall(text))
    latin_words = len(_LATIN_WORD_PATTERN.findall(text))
    english_common = len(_ENGLISH_COMMON_WORDS.findall(text))

    return {
        "thai_chars": thai_count,
        "khmer_chars": khmer_count,
        "bengali_chars": bengali_count,
        "indic_chars": indic_count,
        "chinese_chars": chinese_count,
        "korean_chars": korean_count,
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


def remove_thai_characters(text: str) -> str:
    """Remove all Thai characters from text."""
    return _THAI_PATTERN.sub("", text)


def remove_khmer_characters(text: str) -> str:
    """Remove all Khmer characters from text."""
    return _KHMER_PATTERN.sub("", text)


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
    Also handles bare numerals like '# ၃' followed by '## Title'.
    Split into proper markdown:
        # အခန်း ၁၂
        ## Title
        body text...
    
    Works on both multi-line and single-line (collapsed) text.
    """
    # NEW: Clean broken/empty headings BEFORE fixing format
    # Pattern: "# [ ]" or "# [ ] " with nothing after (corrupted from chunk boundary)
    text = re.sub(r'^#\s*\[\s*\]\s*$', '', text, flags=re.MULTILINE)
    # Pattern: Empty ## heading with nothing after
    text = re.sub(r'^##\s*$', '', text, flags=re.MULTILINE)
    # Pattern: ## with only whitespace
    text = re.sub(r'^##\s+\s*$', '', text, flags=re.MULTILINE)
    
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
    
    # Pattern 3: Bare numeral "# ၃" or "# 3" followed by "## Title" on next lines
    # Convert to "# အခန်း ၃" and "## Title" format
    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Check for bare numeral pattern: # [Myanmar numeral] or # [Arabic numeral]
        bare_num_match = re.match(r'^#\s+([\u1040-\u1049\d]+)$', stripped)
        if bare_num_match and i + 1 < len(lines):
            # Look for subtitle, skipping blank lines
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            
            # Check if the next non-blank line is a ## subtitle
            if j < len(lines):
                next_line = lines[j].strip()
                if next_line.startswith('## '):
                    # Convert to proper format: # အခန်း N: Title
                    num = bare_num_match.group(1)
                    title = next_line[3:].strip()  # Remove "## " prefix
                    result.append(f'# အခန်း {num}: {title}')
                    i = j + 1  # Skip to after the subtitle line
                    continue
        
        result.append(line)
        i += 1
    
    text = '\n'.join(result)

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


def fix_merged_headings(text: str) -> str:
    """Fix headings that are merged with following content without newline.
    
    The model may output '## Title"content' or '## Titlecontent' where
    the heading is directly concatenated with the paragraph text.
    This function separates them properly:
        ## Title
        
        content...
    
    Patterns handled:
    - '## မြန်မာစာသား"English...' → '## မြန်မာစာသား\n\n"English...'
    - '## မြန်မာစာသားမြန်မာ...' → '## မြန်မာစာသား\n\nမြန်မာ...'
    """
    lines = text.split('\n')
    result: list[str] = []
    
    for line in lines:
        stripped = line.strip()
        
        # Pattern: ## Heading"content or ## Heading'content or ## Heading(content
        # Look for ## followed by Myanmar text, then immediately a quote or content
        merged_match = re.match(r'^(##\s+[က-႟\uAA60-\uAA7F\uA9E0-\uA9FF][^"\'\(။\n]*)["\'\(](.+)', stripped)
        if merged_match:
            heading_part = merged_match.group(1).strip()
            content_part = merged_match.group(2)
            result.append(heading_part)
            result.append('')  # blank line
            # Re-add the quote that was consumed
            if stripped[len(heading_part):].startswith('"'):
                result.append('"' + content_part)
            elif stripped[len(heading_part):].startswith("'"):
                result.append("'" + content_part)
            elif stripped[len(heading_part):].startswith('('):
                result.append('(' + content_part)
            else:
                result.append(content_part)
            continue
        
        # Pattern: ## HeadingContent (no space between heading Myanmar text and content)
        # Detect if line starts with ## has Myanmar text but no clear boundary
        # and the line is very long (likely merged)
        if stripped.startswith('## ') and len(stripped) > 100:
            # Try to find boundary: look for sentence ender or quote followed by space
            # Pattern: ## မြန်မာ။content or ## မြန်မာ" content
            boundary_match = re.search(r'(["\'။]\s+|\s{2,})([\u1000-\u109F])', stripped)
            if boundary_match:
                split_pos = boundary_match.start()
                # Include the punctuation in heading
                if stripped[split_pos] in '"\'။':
                    split_pos = boundary_match.end() - 1  # Keep punctuation with heading
                heading_part = stripped[:split_pos].strip()
                content_part = stripped[split_pos:].strip()
                if heading_part and content_part:
                    result.append(heading_part)
                    result.append('')
                    result.append(content_part)
                    continue
        
        result.append(line)
    
    return '\n'.join(result)


def remove_placeholder_headings(text: str) -> str:
    """Remove placeholder headings like '## အခန်းခေါင်းစဉ်' that leak from prompts.
    
    These are template placeholders that should never appear in actual output:
    - ## အခန်းခေါင်းစဉ် (Chapter Title)
    - ## အခန်းခေါင်းစဉ်\n
    Also handles merged versions like '## အခန်းခေါင်းစဉ်အဘိုးကြီး...'
    """
    lines = text.split('\n')
    result: list[str] = []
    skip_next_empty = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Exact match: ## အခန်းခေါင်းစဉ် (with or without trailing content on same line)
        if stripped == '## အခန်းခေါင်းစဉ်':
            skip_next_empty = True
            continue
        
        # Merged placeholder: ## အခန်းခေါင်းစဉ်မြန်မာစာ... (heading merged with content)
        # Keep only the content part after the placeholder
        if stripped.startswith('## အခန်းခေါင်းစဉ်'):
            # Extract content after the placeholder
            content_after = stripped[len('## အခန်းခေါင်းစဉ်'):].strip()
            if content_after:
                result.append(content_after)
            skip_next_empty = True
            continue
        
        # Skip empty lines after removed placeholders
        if skip_next_empty and not stripped:
            skip_next_empty = False
            continue
        
        result.append(line)
    
    return '\n'.join(result)


def remove_checkbox_artifacts(text: str) -> str:
    """Remove checkbox/list artifacts that appear in output.
    
    Patterns:
    - '- []: [ ]' (empty checkbox with brackets)
    - '- []: content' (checkbox with content)
    - '- [ ]: ' (various checkbox formats)
    """
    lines = text.split('\n')
    result: list[str] = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip checkbox artifacts: - []: [ ], - []: content, - [ ]:, etc.
        if re.match(r'^-\s*\[\s*\]\s*:', stripped):
            continue
        
        # Skip checkbox with checkmark: - [x]:, - [✓]:, - [○]:, etc.
        if re.match(r'^-\s*\[[\sxoX✓✔○\-]*\]\s*:', stripped):
            continue
        
        result.append(line)
    
    return '\n'.join(result)


def remove_inline_markdown_artifacts(text: str) -> str:
    """Remove markdown formatting that appears inline within paragraphs.
    
    The model sometimes hallucinates markdown syntax mid-paragraph:
    - "## " appearing in the middle of a sentence
    - "- " list markers appearing mid-paragraph
    - These are NOT proper headings/lists, just formatting leaks
    
    Detection criteria for fake headings:
    - Line starts with "## " but is NOT:
      - The first content line after chapter heading
      - A proper short subtitle (typically < 50 chars)
      - Followed by blank line (proper heading format)
    - Line is very long (> 80 chars) suggesting it's actually paragraph text
    
    Detection criteria for fake list items:
    - Line starts with "- " but contains full sentence structure
    - Part of continuous paragraph flow (not a real list)
    """
    lines = text.split('\n')
    result: list[str] = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Pattern 1: Fake ## heading mid-content
        # Real headings are: short, followed by blank line, near top
        # Fake headings are: long (>80 chars), mid-content, part of paragraph flow
        if stripped.startswith('## ') and len(stripped) > 80:
            # Check if previous line was blank (proper heading) or content (fake)
            prev_is_blank = (i == 0) or (not lines[i-1].strip())
            next_is_blank = (i == len(lines) - 1) or (not lines[i+1].strip() if i + 1 < len(lines) else True)
            
            # If surrounded by content (no blank lines), it's a fake heading
            if not prev_is_blank or not next_is_blank:
                # Remove the "## " prefix and add as regular content
                cleaned_line = stripped[3:].strip()  # Remove "## "
                if cleaned_line:
                    result.append(cleaned_line)
                continue
        
        # Pattern 2: Fake list item "- " mid-paragraph
        # Real list items are typically short and standalone
        # Fake ones are long sentences that start with "- " and have full sentence structure
        if re.match(r'^-\s+', stripped) and len(stripped) > 60:
            # Check if it looks like a paragraph sentence (has sentence ender, multiple words)
            has_sentence_ender = '။' in stripped
            word_count = len(stripped.split())
            
            # If it's a long sentence with proper structure, it's likely a fake list item
            if has_sentence_ender and word_count > 6:
                # Remove the "- " prefix
                cleaned_line = re.sub(r'^-\s+', '', stripped)
                if cleaned_line:
                    result.append(cleaned_line)
                continue
        
        result.append(line)
    
    return '\n'.join(result)


def check_paragraph_count(source: str, translation: str, tolerance: float = 0.15) -> dict:
    """Check if translation has significantly fewer paragraphs than source.
    
    The AI translator sometimes compresses or skips content. This validator
    flags chapters where the paragraph count differs by more than the tolerance.
    
    Args:
        source: Original source text
        translation: Translated text
        tolerance: Maximum allowed ratio of missing paragraphs (0.15 = 15%)
    
    Returns:
        Dict with 'pass' (bool), 'source_count', 'trans_count', 'missing_count', 'ratio'
    """
    def count_paragraphs(text: str) -> int:
        """Count non-empty paragraphs."""
        return len([p for p in text.split('\n\n') if p.strip()])
    
    src_count = count_paragraphs(source)
    trans_count = count_paragraphs(translation)
    
    if src_count == 0:
        return {"pass": True, "source_count": 0, "trans_count": 0, "missing_count": 0, "ratio": 1.0}
    
    missing = max(0, src_count - trans_count)
    ratio = trans_count / src_count
    passed = ratio >= (1.0 - tolerance)
    
    return {
        "pass": passed,
        "source_count": src_count,
        "trans_count": trans_count,
        "missing_count": missing,
        "ratio": round(ratio, 3),
    }


def check_name_consistency(text: str, glossary_terms: dict[str, str]) -> list[dict]:
    """Detect multiple spellings of the same character name in translated text.
    
    For each glossary term, finds all occurrences in the text and checks
    if there are variant spellings that might indicate inconsistency.
    
    Args:
        text: Translated Myanmar text
        glossary_terms: Dict mapping source_term -> target_term (approved translations)
    
    Returns:
        List of dicts with 'source', 'expected', 'found_variants', 'locations'
    """
    issues = []
    
    for source, expected_target in glossary_terms.items():
        if not expected_target or len(expected_target) < 2:
            continue
        
        # Find all occurrences of the expected target
        locations = []
        start = 0
        while True:
            idx = text.find(expected_target, start)
            if idx == -1:
                break
            locations.append(idx)
            start = idx + 1
        
        if not locations:
            continue
        
        # Check for similar-looking variants (potential misspellings)
        # Look for Myanmar sequences near the expected length that appear
        # in similar contexts (before သည်/က/မှာ particles)
        import re
        name_pattern = re.compile(
            r'([\u1000-\u109F]{2,8})\s*(?:သည်|က|မှာ|ကို|၏|ပြော|ကြည့်|ရပ်|သွား|လာ)',
            re.MULTILINE
        )
        
        found_names = set()
        for match in name_pattern.finditer(text):
            candidate = match.group(1)
            # Check if candidate is similar to expected (same length, some overlap)
            if (abs(len(candidate) - len(expected_target)) <= 2
                and len(set(candidate) & set(expected_target)) >= min(len(candidate), len(expected_target)) * 0.5):
                found_names.add(candidate)
        
        # If we found variants that aren't the expected target, flag it
        variants = found_names - {expected_target}
        if variants:
            issues.append({
                "source": source,
                "expected": expected_target,
                "found_variants": list(variants),
                "occurrences": len(locations),
            })
    
    return issues


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


# Myanmar consonant range: U+1000-U+1021 (က-အ) + independent vowels U+1023-U+102A
_MYANMAR_CONSONANT = r'[\u1000-\u1021\u1023-\u102A]'

# Known compounds containing ထို as a syllable (protected from replacement)
# Sorted by length descending so "ထိုက်တန်" is protected before "ထိုက်"
_COMPOUND_PROTECT = {
    'ထိုက်တန်': '__MYAN_DESERVE__',
    'ထိုင်':    '__MYAN_SIT__',
    'ထိုင်း':   '__MYAN_THAI__',
    'ထိုး':    '__MYAN_STAB__',
    'ထိုက်':   '__MYAN_WORTHY__',
}


def replace_archaic_words(text: str) -> str:
    """Replace archaic Myanmar words with modern alternatives.
    
    Archaic → Modern:
        ဤ (this) → ဒီ
        ထို (that) → အဲဒီ
        သင်သည် (you) → မင်း
    
    Uses a compound-exclusion approach: temporarily protects known
    Myanmar compound words that contain ထို as a syllable (ထိုင်=sit,
    ထိုး=stab, etc.) from replacement, then replaces all remaining
    standalone ထို (determiner "that") with အဲဒီ.
    
    The old regex approach (lookahead for consonant) was too conservative
    — it failed to replace ထို when followed by ANY consonant, even when
    the consonant starts a new word (e.g. ထိုလူငယ် → that youth, NOT a compound).
    """
    if not text:
        return text

    # ── Step 1: Protect known compounds (temporary placeholders) ──
    for comp, guard in _COMPOUND_PROTECT.items():
        text = text.replace(comp, guard)

    # ── Step 2: Replace standalone archaic words ──
    text = re.sub(r'(?<!' + _MYANMAR_CONSONANT + r')ဤ(?![\u1039])', 'ဒီ', text)
    text = re.sub(r'(?<!' + _MYANMAR_CONSONANT + r')ထို(?![\u1039])', 'အဲဒီ', text)
    text = re.sub(
        r'(?<!' + _MYANMAR_CONSONANT + r')သင်သည်(?![\u1039])',
        'မင်း', text
    )

    # ── Step 3: Restore protected compounds ──
    for comp, guard in _COMPOUND_PROTECT.items():
        text = text.replace(guard, comp)

    # ── Step 4: Fix ထို့ variants that became အဲဒီ့ (tone mark issue) ──
    text = re.sub(r'အဲဒီ့(?=[' + _MYANMAR_CONSONANT[1:-1] + r'])', 'အဲဒီ', text)

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


# Universal loanword patterns — English words transliterated into Myanmar
# These apply to ALL Chinese novels translated via English source
LOANWORD_REPLACEMENTS = {
    # English loanwords → Myanmar native equivalents
    'ပလက်ဖောင်း': 'စင်မြင့်',      # platform → stage
    'ကွန်ရက်': 'ပိုက်ကွန်',         # network → net (cultivation context)
}

# Forbidden hallucinated patterns — delete entirely
FORBIDDEN_HALLUCINATIONS = [
    # Patterns observed as model hallucinations with no source equivalent
    'ဘုံတာအို',
]


def replace_loanwords(text: str) -> str:
    """Replace English loanwords transliterated into Myanmar with native equivalents.
    
    Universal rules applied to ALL Chinese novels translated via English source.
    """
    if not text:
        return text
    
    for loanword, replacement in LOANWORD_REPLACEMENTS.items():
        text = text.replace(loanword, replacement)
    
    # Delete hallucinated terms entirely
    for hallucination in FORBIDDEN_HALLUCINATIONS:
        text = text.replace(hallucination, '')
    
    return text


def check_ordinal_numbers(text: str) -> list[dict]:
    """Check for incorrect ordinal number translations.
    
    Common error: model shifts ordinals by +1
    - 9th translated as 10th (ဆယ်ခုမြောက် instead of နဝမ)
    - 10th translated as 11th (ဆယ့်တစ်ခုမြောက် instead of ဒသမ)
    
    Returns list of issues found with location and fix recommendation.
    """
    if not text:
        return []
    
    issues = []
    
    # Wrong ordinal forms that indicate +1 shift error
    wrong_ordinals = {
        'ဆယ်ခုမြောက်': {'expected': 'နဝမ', 'meaning': '9th (wrong: wrote 10th)'},
        'ဆယ့်တစ်ခုမြောက်': {'expected': 'ဒသမ', 'meaning': '10th (wrong: wrote 11th)'},
        'ဆယ့်နှစ်ခုမြောက်': {'expected': 'ဧကာဒသမ', 'meaning': '11th (wrong: wrote 12th)'},
    }
    
    for wrong, info in wrong_ordinals.items():
        if wrong in text:
            # Find line numbers where this occurs
            lines = text.split('\n')
            for i, line in enumerate(lines, 1):
                if wrong in line:
                    issues.append({
                        'line': i,
                        'found': wrong,
                        'expected': info['expected'],
                        'meaning': info['meaning'],
                    })
    
    return issues


def check_content_completeness(source: str, translation: str) -> dict:
    """Check if translation has missing content compared to source.
    
    Compares:
    - Paragraph count
    - Dialogue line count (lines starting with quotes)
    - Key sentence presence (sentences with proper names)
    
    Returns dict with pass/fail and detailed metrics.
    """
    def count_paragraphs(text: str) -> int:
        return len([p.strip() for p in text.split('\n\n') if p.strip()])
    
    def count_dialogues(text: str) -> int:
        return len([l.strip() for l in text.split('\n')
                    if l.strip().startswith(('"', '"', '"'))])
    
    src_paras = count_paragraphs(source)
    trans_paras = count_paragraphs(translation)
    src_dialogues = count_dialogues(source)
    trans_dialogues = count_dialogues(translation)
    
    # Extract proper names (Myanmar sequences before particles)
    _NAME_PATTERN = re.compile(r'([\u1000-\u109F]{2,8})\s*(?:သည်|က|မှာ|ကို|၏)')
    src_names = set(_NAME_PATTERN.findall(source))
    trans_names = set(_NAME_PATTERN.findall(translation))
    missing_names = src_names - trans_names
    
    para_ratio = trans_paras / src_paras if src_paras > 0 else 1.0
    dialogue_ratio = trans_dialogues / src_dialogues if src_dialogues > 0 else 1.0
    
    # Pass if translation has ≥85% of source paragraphs and ≥80% of dialogues
    passed = para_ratio >= 0.85 and dialogue_ratio >= 0.80
    
    return {
        'pass': passed,
        'source_paragraphs': src_paras,
        'trans_paragraphs': trans_paras,
        'missing_paragraphs': max(0, src_paras - trans_paras),
        'paragraph_ratio': round(para_ratio, 3),
        'source_dialogues': src_dialogues,
        'trans_dialogues': trans_dialogues,
        'missing_dialogues': max(0, src_dialogues - trans_dialogues),
        'dialogue_ratio': round(dialogue_ratio, 3),
        'missing_names': list(missing_names)[:10],  # cap at 10 for readability
    }


def check_latin_script(text: str) -> list[dict]:
    """Detect untranslated Latin/English letters in Myanmar output.
    
    Returns list of issues with line numbers and the Latin text found.
    """
    if not text:
        return []
    
    issues = []
    # Match Latin letters + digits that are NOT part of markdown syntax
    _LATIN_PATTERN = re.compile(r'[A-Za-z][A-Za-z0-9]{0,10}')
    
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        # Skip markdown syntax, URLs, and code blocks
        stripped = line.strip()
        if stripped.startswith('```') or stripped.startswith('http'):
            continue
        
        # Find Latin sequences
        for match in _LATIN_PATTERN.finditer(line):
            word = match.group()
            # Skip single letters that might be Myanmar romanization markers
            if len(word) >= 2:
                issues.append({
                    'line': i,
                    'text': word,
                    'context': line[max(0, match.start()-20):match.end()+20],
                })
    
    return issues


def check_particle_repetition(text: str, max_per_paragraph: int = 2) -> list[dict]:
    """Check for excessive particle repetition in Myanmar text.
    
    AGENTS.md rule: same particle appears ≤ 2× per paragraph.
    Common overused particles: သည်, က, မှာ, ကို, ၏, တယ်
    
    Returns list of issues with paragraph number, particle, and count.
    """
    if not text:
        return []
    
    # Particles to check for overuse
    PARTICLES = ['သည်', 'က', 'မှာ', 'ကို', '၏', 'တယ်', 'ဘူး', 'မယ်', 'ပြီ']
    
    issues = []
    paragraphs = [p for p in text.split('\n\n') if p.strip()]
    
    for para_idx, para in enumerate(paragraphs, 1):
        for particle in PARTICLES:
            count = para.count(particle)
            if count > max_per_paragraph:
                # Get a snippet of the paragraph for context
                snippet = para[:100] + '...' if len(para) > 100 else para
                issues.append({
                    'paragraph': para_idx,
                    'particle': particle,
                    'count': count,
                    'max_allowed': max_per_paragraph,
                    'snippet': snippet,
                })
    
    return issues


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
    8. Replace loanwords: ပလက်ဖောင်း→စင်မြင့်, delete hallucinations
    9. Replace archaic words: ဤ→ဒီ, ထို→အဲဒီ
    10. Collapse 3+ blank lines → 2
    11. Fix chapter heading format (# X ## Y → proper markdown)
    12. Remove duplicate chapter headings
    13. Ensure markdown readability (paragraph breaks, heading spacing)
    14. Strip leading/trailing whitespace
    
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

    # Always strip non-Myanmar scripts (unambiguous garbage)
    # Thai (U+0E00-U+0E7F), Khmer (U+1780-U+17FF), Bengali, Indic, Chinese, Korean
    text = remove_thai_characters(text)
    text = remove_khmer_characters(text)
    text = remove_chinese_characters(text)
    text = remove_bengali_characters(text)
    text = remove_indic_characters(text)
    text = remove_korean_characters(text)

    # Only remove Latin words if aggressive mode
    if aggressive:
        text = remove_latin_words(text)

    # Fix degraded placeholders
    text = fix_degraded_placeholders(text)

    # Replace English loanwords transliterated into Myanmar + delete hallucinations
    text = replace_loanwords(text)

    # Undo corruptions from old \b-based archaic word replacement (pre-existing)
    text = undo_archaic_corruptions(text)

    # Replace archaic Myanmar words with modern equivalents
    text = replace_archaic_words(text)

    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse excess blank lines
    text = _split_into_lines_if_needed(text)  # recover structure from collapsed text
    text = fix_chapter_heading_format(text)
    text = remove_duplicate_headings(text)
    text = fix_merged_headings(text)  # Fix headings merged with content
    text = remove_placeholder_headings(text)  # Remove placeholder headings like ## အခန်းခေါင်းစဉ်
    text = remove_checkbox_artifacts(text)  # Remove checkbox artifacts
    text = remove_inline_markdown_artifacts(text)  # Remove ## and - markers mid-paragraph
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

    # Determine status - Any non-Myanmar script = automatic REJECT
    if leakage.get("thai_chars", 0) > 0:
        status = "REJECTED"
    elif leakage.get("khmer_chars", 0) > 0:
        status = "REJECTED"
    elif leakage.get("bengali_chars", 0) > 0:
        status = "REJECTED"
    elif leakage.get("indic_chars", 0) > 0:
        status = "REJECTED"
    elif leakage.get("chinese_chars", 0) > 0:
        status = "REJECTED"
    elif leakage.get("korean_chars", 0) > 0:
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
        "khmer_chars_leaked": leakage.get("khmer_chars", 0),
        "bengali_chars_leaked": leakage.get("bengali_chars", 0),
        "indic_chars_leaked": leakage.get("indic_chars", 0),
        "chinese_chars_leaked": leakage.get("chinese_chars", 0),
        "korean_chars_leaked": leakage.get("korean_chars", 0),
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
