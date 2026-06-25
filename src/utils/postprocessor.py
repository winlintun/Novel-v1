"""
src/utils/postprocessor.py
Cleans raw LLM output before saving.
Strips: <think>, <answer>, HTML comments, non-Myanmar language leakage.
"""

import re
from functools import lru_cache
from difflib import SequenceMatcher

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
    JAPANESE_KANA_PATTERN,
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
_JAPANESE_KANA_PATTERN = JAPANESE_KANA_PATTERN
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
    # Fast path: skip all 27 patterns if no reasoning markers present
    if '<think>' not in text and '**' not in text[:500] and '(This is' not in text:
        return text

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

        # Remove FictionEditor / pipeline stage labels that leaked into output
        # e.g., **[ပြင်ဆင်ထားသော စာသား]** or **ပြင်ဆင်ထားသော စာသား ( ):** 
        line = re.sub(r'\*{1,2}\[ပြင်ဆင်ထားသော စာသား\]\*{1,2}\s*', '', line)
        line = re.sub(r'\*{1,2}ပြင်ဆင်ထားသော စာသား\s*\([^)]*\):\*{1,2}\s*', '', line)

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

        # Remove only parenthetical English explanations (NOT literary asides)
        line = re.sub(r'\(This is.*?\)', '', line, flags=re.IGNORECASE)

        # Skip padauk-gemma glossary comparison garbage lines (*:* pattern)
        # These look like: *:* "word" is . "other" is .
        # Or: * :* , .  (short garbage fragments with English)
        # NOTE: requires colon between asterisks to avoid matching **bold** markdown
        if re.match(r'^\s*\*[\s:]*:[\s:]*\*', original_line):
            continue

        # Skip short English-only garbage lines (model entropy spikes)
        # e.g., "at as . Xu 't of ." — Latin words but no Myanmar content
        if re.search(r'[a-zA-Z]', stripped) and not re.search(r'[\u1000-\u109F\uAA60-\uAA7F\uA9E0-\uA9FF]', stripped):
            if len(stripped) < 30:
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
    japanese_count = len(_JAPANESE_KANA_PATTERN.findall(text))
    latin_words = len(_LATIN_WORD_PATTERN.findall(text))
    english_common = len(_ENGLISH_COMMON_WORDS.findall(text))

    return {
        "thai_chars": thai_count,
        "khmer_chars": khmer_count,
        "bengali_chars": bengali_count,
        "indic_chars": indic_count,
        "chinese_chars": chinese_count,
        "korean_chars": korean_count,
        "japanese_chars": japanese_count,
        "latin_words": latin_words,
        "english_common_words": english_common,
        "has_english": latin_words > 0 or english_common > 0,
    }


@lru_cache(maxsize=256)
def myanmar_char_ratio(text: str) -> float:
    """Return ratio of Myanmar Unicode characters to total non-whitespace chars.

    Cached: the same text is checked ~7+ times per chunk across different stages.
    """
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


def remove_japanese_kana(text: str) -> str:
    """Remove all Japanese kana (Hiragana/Katakana) from text.

    Kana leaks into Myanmar output for untranslated terms (e.g. a stray 'い').
    CJK ideographs are handled separately by remove_chinese_characters().
    """
    return _JAPANESE_KANA_PATTERN.sub("", text)


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


def separate_heading_from_body(text: str) -> str:
    """Split a chapter heading that is glued to body text on the same line.

    The model frequently emits the chapter heading concatenated directly to the
    first sentence with NO newline, and repeats it at the start of every chunk:

        '# အခန်း ၁၁သူတို့သည် သုံးယောက်စီပါသော အဖွဲ့လေးဖွဲ့...'

    Downstream `remove_duplicate_headings` and the final heading-injection block
    are line-based: they treat the whole line as a (duplicate) heading and delete
    it — silently taking the real first sentence with it. (Observed: chapter 12
    lost all 5 chunk-opening sentences this way, including dialogue.)

    Force a paragraph break immediately after the heading number so the body text
    lands on its own line and survives heading dedup/injection. Only splits when
    real (non-heading, non-digit) content is glued after the number; a heading
    already followed by whitespace/newline or a '##'/':' subtitle is left for
    fix_chapter_heading_format to handle.
    """
    return re.sub(
        r'(^|\n)(#\s*အခန်း\s*[၀-၉\d]+)[ \t]*(?=[^\s\d၀-၉#:])',
        r'\1\2\n\n',
        text,
    )


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


def normalize_character_names(text: str, glossary_terms: list[dict]) -> str:
    """Normalize character name spellings to glossary-approved forms.

    For each glossary character term, finds all variant spellings in the
    translated text and replaces them with the approved target_term.
    Uses SequenceMatcher for Myanmar-safe similarity comparison
    (per AGENTS.md Pattern 10 — char-set overlap is unsafe for Myanmar text).

    Args:
        text: Translated Myanmar text
        glossary_terms: List of glossary term dicts (must have 'target_term' or 'target',
                       and 'category' == 'character')

    Returns:
        Text with all character names normalized to approved forms
    """
    if not text or not glossary_terms:
        return text

    # Filter to character terms only, with valid targets
    char_terms = []
    for t in glossary_terms:
        target = t.get('target_term') or t.get('target', '')
        source = t.get('source_term') or t.get('source', '')
        cat = t.get('category', '')
        if target and len(target) >= 2 and cat == 'character':
            char_terms.append((source, target))

    if not char_terms:
        return text

    # Normalize longer names first: a full name (ပိုင်ရှောင်ချန်း) must be fixed
    # before its short form (ရှောင်ချန်း), or the short-form pass can partially
    # rewrite the middle of the full name and corrupt it.
    char_terms.sort(key=lambda st: len(st[1]), reverse=True)

    for source, target in char_terms:
        target_present = target in text
        # Previously: `if target not in text: continue` — this disabled normalization
        # exactly when the model produced ONLY wrong spellings (e.g. ch12 had
        # ရှူချင်း/ရှူးချင်း but never the canonical ရွှီချင်း), which is the case we
        # most need to fix. Now we still scan for variants and map them to canon.
        # Safety: short names (≤3 syllables) collide with common words, so without
        # the canonical form present as confirmation we skip them (e.g. Lei→လဲ့ vs
        # the everyday word လေး="four"); and we use a stricter similarity threshold.
        if not target_present and len(target) < 4:
            continue
        variant_threshold = 0.70 if target_present else 0.75

        # Find all Myanmar sequences of similar length to the target that appear
        # in similar grammatical positions (before particles). The capture window
        # is intentionally wider than ±1 char: a small model drops/garbles a final
        # syllable (e.g. ပိုင်ရှောင်ချီ for ပိုင်ရှောင်ချန်း, a 2-char gap) which a
        # ±1 window never even captured. We widen to ~±one syllable and let the
        # SequenceMatcher threshold below — the real precision guard — reject
        # genuine non-matches.
        expected_len = len(target)
        lo = max(3, expected_len - 4)
        hi = expected_len + 2
        pattern = re.compile(
            rf'(?:^|[\s"\u201C\u201D\u201E\u104A\u104B\u104C\u104D\u104E\u104F(])([\u1000-\u1049\u1050-\u109F]{{{lo},{hi}}})\s*(?:သည်|က|မှာ|ကို|၏|ပြော|ကြည့်|ရပ်|သွား|လာ|\s|။)',
            re.MULTILINE
        )

        # Collect unique candidates that are close to the target
        # Uses SequenceMatcher for Myanmar-safe similarity
        candidates = set()
        for match in pattern.finditer(text):
            candidate = match.group(1)
            if candidate == target:
                continue
            # Length delta check first (fast filter)
            max_length_delta = 2 if expected_len <= 5 else 3
            if abs(len(candidate) - expected_len) > max_length_delta:
                continue
            # SequenceMatcher ratio — safe for Myanmar text (AGENTS.md Pattern 10)
            ratio = SequenceMatcher(None, candidate, target).ratio()
            if ratio >= variant_threshold:  # threshold for name variants
                candidates.add(candidate)

        # Replace variants (longest first to avoid partial replacement issues)
        for variant in sorted(candidates, key=len, reverse=True):
            text = text.replace(variant, target)

    return text


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
    Also handles standalone "??" used as subject placeholder (model collapse).
    """
    if not text:
        return text
    # Replace any degraded 【?*】 pattern with standard 【?term?】
    text = re.sub(r'【\?+\s*】', '【?term?】', text)
    # Fix standalone "??" as subject: "?? သည်" → "【?character?】" 
    # (model uses ?? when it doesn't know the character name)
    text = re.sub(r'\?\?\s+(သည်|က|မှာ|တို့)', '【?character?】 \\1', text)
    # Fix "??" at start of a line
    text = re.sub(r'^\?\?', '【?character?】', text, flags=re.MULTILINE)
    return text


# Universal loanword patterns — English words transliterated into Myanmar
# These apply to ALL Chinese novels translated via English source
LOANWORD_REPLACEMENTS = {
    # English loanwords → Myanmar native equivalents
    'ပလက်ဖောင်း': 'စင်မြင့်',      # platform → stage
    'ကွန်ရက်': 'ပိုက်ကွန်',         # network → net (cultivation context)
}

# Hallucinated term corrections — model produces non-word compounds
# These are NOT loanwords but model hallucinations that must be corrected
HALLUCINATED_TERM_CORRECTIONS = {
    'ကျင့်တည်းဆိုင်': 'ကျင့်ကြံ',      # "cultivation" hallucinated compound → correct term
    'ကျင့်တည်းဆိုင်ဖို့': 'ကျင့်ကြံရန်',  # conjugated form
    'ညစ်ဂျေး': 'ညစ်ကျေး',              # "impurities/filth" — misspelled ဂျေး → ကျေး
    'နဲဒီ': 'ဒီ',                          # non-standard dialect → standard ဒီ
    'ခါရမ်းစွာ': 'ယိုင်းယိုင်',            # "staggered" — hallucinated non-word
    'ဉာဏ်ထက်မြတ်သူ': 'လိမ္မာပါးမာသူ',  # "quick-witted" → not "superior intellect"
    'ထာ၀ရအသက်ရှည်ခြင်းလမ်းစဉ်': 'နတ်ကျင့်ခြင်းလမ်းစဉ်',  # "immortal cultivation" — must keep ကျင့်
    'ခေါင်းညှိတ်ပေး': 'ပခုံးကို ပုတ်ပေး',  # "patted on shoulder" not "nodded head"
    'လေးတစ်ကောင်': 'သိုးကျားငယ်လေး',    # "baby eagle" not just "a bird"
    'အခိုက်အတန့်': 'အခြေနေ',            # "situations" (neutral) not "crises/hardships"
    'ဒီအိစ့်ဝုဒ်': 'အီးစ်ဝုဒ်',           # English transliteration cleanup
}

# Forbidden hallucinated patterns — delete entirely
FORBIDDEN_HALLUCINATIONS = [
    # Patterns observed as model hallucinations with no source equivalent
    'ဘုံတာအို',
]


def replace_loanwords(text: str) -> str:
    """Replace English loanwords and hallucinated terms with correct Myanmar equivalents.
    
    Universal rules applied to ALL Chinese novels translated via English source.
    Also corrects model-hallucinated non-word compounds.
    """
    if not text:
        return text
    
    for loanword, replacement in LOANWORD_REPLACEMENTS.items():
        text = text.replace(loanword, replacement)
    
    for wrong, correct in HALLUCINATED_TERM_CORRECTIONS.items():
        text = text.replace(wrong, correct)
    
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
    
    # Dialogue openers. NOTE: the three literals here used to all be the ASCII
    # straight quote (U+0022), so curly-quoted Myanmar dialogue ("…") was never
    # counted — undercounting trans_dialogues to ~0 and falsely failing the
    # completeness gate. Match the same opener set the rest of the module uses
    # (see _QUOTED_SPAN): straight, curly double/single, and CJK corner bracket.
    _DIALOGUE_OPENERS = ('"', '“', '‘', '「')

    def count_dialogues(text: str) -> int:
        return len([line.strip() for line in text.split('\n')
                    if line.strip().startswith(_DIALOGUE_OPENERS)])
    
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


_LATIN_IN_MYANMAR_PATTERN = re.compile(
    r'[က-႟]+[A-Za-z]+|[A-Za-z]+[က-႟]+'
)


def detect_latin_in_myanmar(text: str) -> list[str]:
    """Detect Latin letters fused directly to a Myanmar cluster (no space).

    This is the signature of decoding/postprocessing corruption — e.g. the
    syllable 'ဟန်' emitted as 'ဟ' + Latin 'an' ('ဟan'). It is deliberately
    distinct from a free-standing romanized proper noun (which is space-
    delimited and may be legitimate): we match ONLY Latin runs glued straight
    onto Myanmar, so a real name on its own does not trip it.

    The word-count Latin check tolerates a handful of "words" and so scores
    'ဟan' as acceptable; this returns it as a hard defect.

    Returns the list of offending fragments (e.g. ['ဟan']); empty if clean.
    """
    if not text:
        return []
    return _LATIN_IN_MYANMAR_PATTERN.findall(text)


# Placeholder marks a model emits when it cannot resolve a token (most often a
# cross-lingual name like "Bai Xiaochun" → "??"). These are never valid Myanmar
# prose, so their presence is a hard defect.
_PLACEHOLDER_PATTERN = re.compile(r'\?{2,}|？{2,}|【\?+】|<unk>|\bUNK\b')


def detect_placeholder_marks(text: str) -> list[str]:
    """Detect unresolved-token placeholders (e.g. '??', '？？', '<unk>').

    The model emits these when it cannot resolve a token on the fly — typically
    a proper noun it failed to transliterate. They must never survive into final
    output, so this is treated as a hard defect (retry, then reject).
    """
    if not text:
        return []
    return _PLACEHOLDER_PATTERN.findall(text)


# Noun → numeral-classifier combinations that are semantically wrong. Burmese
# uses noun-specific classifiers; pairing a village (ရွာ/ကျေးရွာ) with ကျောင်း
# (the classifier for schools/monasteries/buildings) is a decoding error — the
# observed bug "ကျေးရွာလေးတစ်ကျောင်း" (should be …တစ်ရွာ). Patterns are tight
# (\S{0,8}, no spaces) so a legitimately co-occurring noun+building across a
# space is not flagged. Each entry: (label, compiled_pattern, correct_form).
_CLASSIFIER_ERROR_RULES = [
    ("village", re.compile(r'(?:ကျေးရွာ|ရွာ)\S{0,8}ကျောင်း'), "…တစ်ရွာ"),
]


def detect_classifier_errors(text: str) -> list[str]:
    """Detect semantically wrong noun→numeral-classifier pairings.

    Returns a list of '<label>: <matched fragment> (use <correct>)' strings;
    empty if clean. Deliberately conservative (a tiny curated rule set with
    tight, space-free windows) to avoid false-positive rejections.
    """
    if not text:
        return []
    out: list[str] = []
    for label, pat, correct in _CLASSIFIER_ERROR_RULES:
        for m in pat.finditer(text):
            out.append(f"{label}: '{m.group()}' (use {correct})")
    return out


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


# Characters that legitimately end a complete Myanmar paragraph/chunk:
# ။ sentence end, ၏ literary genitive-final, closing quotes, ellipsis,
# exclamation/question, and closing brackets/placeholder markers.
_COMPLETE_ENDINGS = '။…”’"\'!?.）)]】'


def looks_truncated(text: str) -> bool:
    """Heuristic: did the model stop mid-output (hit its token limit) rather than finish?

    Complete Myanmar prose and dialogue end with a sentence terminator (။), a closing
    quote, ellipsis, or terminal punctuation. Output that ends on a bare word, particle,
    or partial syllable is almost always a truncated generation — e.g. chapter 12's
    chunks ended with 'ကြောက်ရွံ့မှုများ' and 'မြင်သောအခ' (cut mid-word), both with no ။.

    Returns True if the final content line does not end with a completion marker.
    A trailing heading or a purely structural line ('***', '---') counts as complete.
    """
    if not text or not text.strip():
        return False  # empty output is a different failure mode, handled elsewhere
    lines = [ln for ln in text.rstrip().splitlines() if ln.strip()]
    if not lines:
        return False
    last_line = lines[-1].strip()
    # A trailing heading or markdown divider is not a truncation signal.
    if last_line.startswith('#') or set(last_line) <= set('*-_= '):
        return False
    return last_line[-1] not in _COMPLETE_ENDINGS


def check_sentence_completion(text: str) -> list[dict]:
    """Detect incomplete sentences ending with Myanmar particles without sentence enders.

    Report issue 4.3: Lines ending with (၏|သည်|သော|ကို) without ္။
    These indicate truncation — the model stopped mid-sentence.

    Returns list of issues with line number and truncated text.
    """
    if not text:
        return []

    issues = []
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        # Check for lines ending with a possessive/attributive particle but no sentence ender
        # Uses alternation to avoid character class decomposing multi-codepoint particles.
        # E.g., "သည်" = U+101E U+103A — a character class would match '်' (U+103A) alone.
        # No lookbehind needed: if line ends with ္။ before the particle, the alternation won't match.
        if re.search(r'(၏|သည်|သော|ကို|မှာ)$', stripped):
            # Skip headings and short lines (likely not truncated)
            if not stripped.startswith('#') and len(stripped) > 10:
                issues.append({
                    'line': i,
                    'text': stripped[-60:],
                    'issue': 'incomplete_sentence',
                })
    return issues


def detect_ngram_repetition(text: str, n: int = 4, max_repeats: int = 3) -> dict:
    """Detect n-gram repetition in Myanmar text.

    Report issue 4.1: If any n-gram appears more than max_repeats times,
    flag for review regardless of Myanmar ratio.

    Args:
        text: Text to analyze
        n: Gram size (default 4 characters)
        max_repeats: Max allowed occurrences before flagging

    Returns:
        Dict with repetition metrics
    """
    if not text or len(text) < n * max_repeats:
        return {"has_repetition": False, "repeated_ngrams": []}

    from collections import Counter

    # Extract n-grams (character-level for Myanmar)
    ngrams = [text[i:i+n] for i in range(len(text) - n + 1)]
    # Filter to only Myanmar-containing n-grams
    myanmar_ngrams = [g for g in ngrams if re.search(r'[\u1000-\u109F]', g)]

    if not myanmar_ngrams:
        return {"has_repetition": False, "repeated_ngrams": []}

    counts = Counter(myanmar_ngrams)
    repeated = []
    for gram, count in counts.most_common(20):
        if count > max_repeats:
            repeated.append({
                "ngram": gram,
                "count": count,
            })

    return {
        "has_repetition": len(repeated) > 0,
        "repeated_ngrams": repeated,
    }


def detect_compression_degeneration(text: str, min_chars: int = 200) -> dict:
    """Flag degenerate / looping output via its zlib compression ratio.

    Coherent prose carries moderate redundancy and compresses to roughly 30–60%
    of its original size. When a small model falls into a repetition loop — even
    a *paraphrased* or drifting one that exact n-gram counting misses — the
    output becomes far more compressible. A very low ratio is therefore a strong,
    cheap degeneration signal that complements :func:`detect_ngram_repetition`
    (exact loops) and the fluency TTR check.

    ratio = compressed_bytes / original_bytes (lower = more repetitive).

    Thresholds are deliberately VERY conservative. Myanmar UTF-8 is byte-heavy
    and naturally redundant: real Burmese prose measures ~0.33 and *falls further
    on longer text* (zlib's dictionary grows), so a tight threshold would falsely
    flag good chapters. A genuine degenerate loop, by contrast, sits near ~0.02–
    0.10. We therefore only fire on the egregious case and leave mild/partial
    repetition to :func:`detect_ngram_repetition` and the fluency TTR check, which
    catch it without the length sensitivity.

    Returns ``{'checked', 'ratio', 'degenerate', 'severe', 'chars'}``.
    ``checked`` is False for text shorter than ``min_chars`` (ratio is unreliable
    on tiny inputs because the zlib header dominates).
    """
    import zlib

    body = text.strip() if text else ""
    n = len(body)
    if n < min_chars:
        return {"checked": False, "ratio": 1.0, "degenerate": False,
                "severe": False, "chars": n}

    raw = body.encode("utf-8")
    comp = zlib.compress(raw, 6)
    ratio = len(comp) / max(len(raw), 1)

    # < 0.10 ≈ pathological loop; 0.10–0.15 ≈ strongly repetitive. Natural Myanmar
    # prose (~0.33, lower for long chapters) stays comfortably clear of both.
    severe = ratio < 0.10
    degenerate = ratio < 0.15
    return {"checked": True, "ratio": round(ratio, 3), "degenerate": degenerate,
            "severe": severe, "chars": n}


def check_source_aligned_ordinals(source: str, translation: str) -> list[dict]:
    """Compare ordinal numbers between source and translation for +1 shift errors.

    Report issue 4.2: Source says '9th stage' → translation says '10th stage'.
    Extracts ordinal patterns from both and flags mismatches.

    Args:
        source: Source English/Chinese text
        translation: Myanmar translation text

    Returns:
        List of issues with source ordinal and mismatched translation ordinal
    """
    issues = []

    # English ordinal patterns: 1st, 2nd, 3rd, 4th, ... 9th, 10th, etc.
    _EN_ORDINAL = re.compile(r'(\d+)(st|nd|rd|th)', re.IGNORECASE)
    en_ordinals = _EN_ORDINAL.findall(source)

    # Chinese ordinal patterns: 第N (e.g., 第九 = 9th, 第10 = 10th)
    _CN_ORDINAL = re.compile(r'第(\d+)')
    cn_ordinals = _CN_ORDINAL.findall(source)

    if not en_ordinals and not cn_ordinals:
        return issues

    # Myanmar ordinal patterns: နဝမ (9th), ဒသမ (10th), ဧကာဒသမ (11th), etc.
    _MM_ORDINAL = re.compile(
        r'(ပထမ|ဒုတိယ|တတိယ|စတုတ္ထ|ပဉ္စမ|ဆဋ္ဌမ|သတ္တမ|အဋ္ဌမ|နဝမ|ဒသမ|ဧကာဒသမ|ဒွါဒသမ)'
    )
    mm_ordinals = _MM_ORDINAL.findall(translation)

    # Mapping English ordinals to their numeric values
    en_num_map = {
        '1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5,
        '6th': 6, '7th': 7, '8th': 8, '9th': 9, '10th': 10,
        '11th': 11, '12th': 12,
    }

    # Mapping Myanmar ordinals to their numeric values
    mm_num_map = {
        'ပထမ': 1, 'ဒုတိယ': 2, 'တတိယ': 3, 'စတုတ္ထ': 4, 'ပဉ္စမ': 5,
        'ဆဋ္ဌမ': 6, 'သတ္တမ': 7, 'အဋ္ဌမ': 8, 'နဝမ': 9, 'ဒသမ': 10,
        'ဧကာဒသမ': 11, 'ဒွါဒသမ': 12,
    }

    # Positional matching: compare i-th English ordinal to i-th Myanmar ordinal
    # to avoid false cross-product mismatches (e.g., "1st, 2nd" vs "ပထမ, ဒုတိယ")
    for i, (num_str, suffix) in enumerate(en_ordinals):
        full = num_str + suffix
        expected_num = en_num_map.get(full.lower())
        if expected_num is None:
            continue

        if i < len(mm_ordinals):
            mm_ord = mm_ordinals[i]
            actual_num = mm_num_map.get(mm_ord)
            if actual_num and actual_num != expected_num:
                issues.append({
                    'source': full,
                    'expected_ordinal': expected_num,
                    'found_ordinal': mm_ord,
                    'found_numeric': actual_num,
                    'meaning': f"Source says '{full}' ({expected_num}) but translation has '{mm_ord}' ({actual_num})",
                })

    # Chinese ordinal patterns: 第N (e.g., 第9 = 9th, 第12 = 12th)
    for i, num_str in enumerate(cn_ordinals):
        try:
            expected_num = int(num_str)
        except ValueError:
            continue

        # Shift index by en_ordinals count for positional matching
        mm_idx = len(en_ordinals) + i
        if mm_idx < len(mm_ordinals):
            mm_ord = mm_ordinals[mm_idx]
            actual_num = mm_num_map.get(mm_ord)
            if actual_num and actual_num != expected_num:
                issues.append({
                    'source': f'第{num_str}',
                    'expected_ordinal': expected_num,
                    'found_ordinal': mm_ord,
                    'found_numeric': actual_num,
                    'meaning': f"Source says '第{num_str}' ({expected_num}) but translation has '{mm_ord}' ({actual_num})",
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


def remove_consecutive_duplicates(text: str, threshold: float = 0.92) -> str:
    """
    Remove consecutive duplicate or near-duplicate lines/sentences.
    
    The model sometimes enters repetition loops, outputting the same
    sentence or paragraph 3-7 times in a row. This function detects
    consecutive lines with identical or near-identical Myanmar text
    and keeps only the first occurrence.
    
    Uses SequenceMatcher for similarity (safe for Myanmar text — not
    char-set overlap which gives false positives on shared particles).
    
    Args:
        text: Input text
        threshold: Similarity above this triggers dedup (0.92 = 92%)
        
    Returns:
        Text with consecutive duplicates removed
    """
    if not text:
        return text
    
    lines = text.split('\n')
    if len(lines) < 2:
        return text
    
    result = [lines[0]]
    for i in range(1, len(lines)):
        current = lines[i].strip()
        if not current:
            result.append(lines[i])
            continue
        # Compare against last kept non-empty line
        prev = result[-1].strip()
        if not prev:
            result.append(lines[i])
            continue
        # Skip short lines (headings, separators)
        if len(current) < 15 or len(prev) < 15:
            result.append(lines[i])
            continue
        # Check similarity
        ratio = SequenceMatcher(None, prev, current).ratio()
        if ratio < threshold:
            result.append(lines[i])
        # else: skip — consecutive duplicate
    
    return '\n'.join(result)


def _arabic_to_myanmar_num(num: int) -> str:
    """Convert Arabic numeral to Myanmar numeral string.
    E.g., 6 → '၆', 12 → '၁၂', 1847 → '၁၈၄၇'
    """
    mm_digits = ['၀', '၁', '၂', '၃', '၄', '၅', '၆', '၇', '၈', '၉']
    return ''.join(mm_digits[int(d)] for d in str(num))


def fix_foreign_punctuation(text: str) -> str:
    """Replace/strip Arabic-block punctuation the model occasionally leaks.

    NOTE: the Myanmar little-section mark ၊ (U+104A) and section mark ။ (U+104B)
    are CORRECT Myanmar punctuation and must be preserved. The leak we fix is the
    Arabic comma ، (U+060C) and friends (Arabic block U+0600–U+06FF), which look
    similar but are foreign. ، / ؛ map to the Myanmar comma ၊; other stray Arabic
    punctuation is dropped.
    """
    if not text:
        return text
    text = text.replace('،', '၊').replace('؛', '၊')   # Arabic comma/semicolon → Myanmar ၊
    text = re.sub(r'[؀-ۿ]', '', text)          # drop any remaining Arabic-block chars
    return text


def fix_double_terminator_punct(text: str) -> str:
    """Drop a Myanmar sentence terminator (။/၊) wedged against ! or ?.

    The model often emits "…မှာပါ။!" (literary terminator + exclamation), a
    register/punctuation artifact. The intended mark is the ! or ? alone, so we
    keep that and drop the adjacent ။/၊ on either side.
    """
    if not text:
        return text
    text = re.sub(r'[။၊]\s*([!?！？])', r'\1', text)   # ။! → !
    text = re.sub(r'([!?！？])\s*[။၊]', r'\1', text)   # !။ → !
    return text


# Quoted spans = dialogue; register normalization must skip them (characters
# speak colloquially). Handles straight and curly double quotes + single curly.
_QUOTED_SPAN = re.compile(r'"[^"]*"|“[^”]*”|‘[^’]*’|「[^」]*」')

# Narration-only colloquial → literary swaps. Composes AFTER replace_archaic_words
# (which globally modernizes ထို→အဲဒီ): in narration we swap back to the literary
# register the human corpus uses, while dialogue keeps the modern colloquial forms.
_NARRATION_LITERARY_SUBS = [
    ("သူ့ရဲ့", "သူ၏"),    # colloquial possessive → literary (drop redundant ့)
    ("သူမရဲ့", "သူမ၏"),
    ("ရဲ့", "၏"),          # generic possessive particle
    ("အဲဒီ", "ထို"),       # demonstrative "that"
]


def _literary_narration(segment: str) -> str:
    for old, new in _NARRATION_LITERARY_SUBS:
        segment = segment.replace(old, new)
    return segment


def normalize_register(text: str) -> str:
    """Push NARRATION toward literary register; leave DIALOGUE untouched.

    The model leaks colloquial markers (ရဲ့, အဲဒီ) into literary narration, which
    breaks the historical tone of the human corpus. We rewrite those markers to
    their literary forms (၏, ထို) ONLY outside quoted spans, so characters still
    speak colloquially in dialogue. Scene-aware and deliberately conservative (a
    small curated map, no risky sentence-final တယ်→သည် surgery) to avoid
    grammatical damage. Idempotent.
    """
    if not text:
        return text
    out: list[str] = []
    last = 0
    for m in _QUOTED_SPAN.finditer(text):
        out.append(_literary_narration(text[last:m.start()]))  # narration before quote
        out.append(m.group())                                   # dialogue verbatim
        last = m.end()
    out.append(_literary_narration(text[last:]))
    return ''.join(out)


def clean_output(raw: str, aggressive: bool = False, chapter: int = 0) -> str:
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
    14. ALWAYS inject correct chapter heading from filename (fixes LLM hallucination)
    15. Normalize character names to glossary-approved forms
    16. Strip leading/trailing whitespace
    
    Args:
        raw: Raw LLM output
        aggressive: If True, also remove Latin/English words.
        chapter: Correct chapter number (from filename). The heading is ALWAYS
                 forced to this value, overriding any hallucinated heading.
    
    Returns:
        Cleaned text
    """
    text = raw.replace('\ufeff', '')
    text = strip_reasoning_tags(text)
    text = strip_reasoning_process(text)
    text = strip_header_artifacts(text)

    # Remove Myanmar-translated metadata lines (translator/editor credit)
    text = strip_translated_metadata(text)

    # Stitch fragments at chunk boundaries
    text = stitch_chunk_boundaries(text)

    # Always strip non-Myanmar scripts (unambiguous garbage)
    # Thai (U+0E00-U+0E7F), Khmer (U+1780-U+17FF), Bengali, Indic, Chinese, Korean, Japanese kana
    text = remove_thai_characters(text)
    text = remove_khmer_characters(text)
    text = remove_chinese_characters(text)
    text = remove_bengali_characters(text)
    text = remove_indic_characters(text)
    text = remove_korean_characters(text)
    text = remove_japanese_kana(text)

    # Only remove Latin words if aggressive mode
    if aggressive:
        text = remove_latin_words(text)

    # Fix degraded placeholders
    text = fix_degraded_placeholders(text)

    # Drop "။!"/"။?" terminator-vs-punctuation artifacts
    text = fix_double_terminator_punct(text)

    # Replace/strip leaked Arabic-block punctuation (، → ၊); preserves Myanmar ၊/။
    text = fix_foreign_punctuation(text)

    # Replace English loanwords transliterated into Myanmar + delete hallucinations
    text = replace_loanwords(text)

    # Undo corruptions from old \b-based archaic word replacement (pre-existing)
    text = undo_archaic_corruptions(text)

    # Replace archaic Myanmar words with modern equivalents
    text = replace_archaic_words(text)

    # Remove consecutive duplicate lines (repetition loops from model)
    text = remove_consecutive_duplicates(text)

    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse excess blank lines
    text = _split_into_lines_if_needed(text)  # recover structure from collapsed text
    text = separate_heading_from_body(text)  # un-glue heading from first sentence (prevents data loss)
    text = fix_chapter_heading_format(text)
    text = remove_duplicate_headings(text)
    text = fix_merged_headings(text)  # Fix headings merged with content
    text = remove_placeholder_headings(text)  # Remove placeholder headings like ## အခန်းခေါင်းစဉ်
    text = remove_checkbox_artifacts(text)  # Remove checkbox artifacts
    text = remove_inline_markdown_artifacts(text)  # Remove ## and - markers mid-paragraph
    text = ensure_markdown_readability(text)  # proper paragraph breaks, heading spacing
    text = text.strip()

    # ── ALWAYS inject correct chapter heading (unconditional) ──
    # The LLM hallucinates headings like "Chapter 1" for every chapter
    # because source files start with the novel title, not a heading.
    # We ALWAYS remove any existing heading block and inject the correct one.
    if chapter:
        # Re-split in case an earlier step re-glued the heading to body text;
        # otherwise the removal below would delete the first sentence with it.
        text = separate_heading_from_body(text).strip()
        # Strip a LEADING heading block ("# အခန်း" + optional "##" subtitle) only
        # when it is the first non-empty line. CRITICAL: a "# အခန်း N" heading the
        # model hallucinated later in the body must NOT be used as a cut point — the
        # old code did `lines[heading_end:]`, deleting EVERY line before a mid/late
        # heading and wiping whole chapters (e.g. last chunk mistranslated into a
        # heading -> 25% coverage / empty output).
        lines = text.split('\n')
        heading_re = re.compile(r'^#\s+အခန်း\s+[၀-၉\d]+')
        first_idx = next((i for i, line in enumerate(lines) if line.strip()), None)
        if first_idx is not None and heading_re.match(lines[first_idx].strip()):
            heading_end = first_idx + 1
            if heading_end < len(lines) and re.match(r'^##\s+', lines[heading_end].strip()):
                heading_end += 1
            text = '\n'.join(lines[heading_end:]).strip()

        # Remove any OTHER stray chapter-heading lines hallucinated mid-body,
        # in place — never drop the surrounding content.
        text = '\n'.join(
            line for line in text.split('\n')
            if not heading_re.match(line.strip())
        ).strip()

        # Inject the CORRECT chapter heading with Myanmar numeral
        chapter_mm = _arabic_to_myanmar_num(chapter)
        text = f'# အခန်း {chapter_mm}\n\n{text}'

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

    def clean(self, text: str, chapter: int = 0) -> str:
        """
        Clean the raw LLM output.

        Args:
            text: Raw text from LLM
            chapter: Chapter number (for heading injection if missing)

        Returns:
            Cleaned text
        """
        return clean_output(text, aggressive=self.aggressive, chapter=chapter)
