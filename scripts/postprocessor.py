#!/usr/bin/env python3
"""
Postprocessor - Punctuation fixes and character name consistency
"""

import json
import re
from pathlib import Path
from typing import Dict, Tuple


def fix_punctuation(text: str) -> str:
    """Fix Chinese punctuation to Myanmar equivalents."""
    replacements = {
        '。': '။',
        '，': '၊',
        '！': '!',
        '？': '?',
        '：': ':',
        '；': ';',
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '（': '(',
        '）': ')',
        '【': '[',
        '】': ']',
    }
    
    for chinese, myanmar in replacements.items():
        text = text.replace(chinese, myanmar)
    
    return text


def collapse_blank_lines(text: str) -> str:
    """Collapse 3+ blank lines to 2."""
    return re.sub(r'\n{3,}', '\n\n', text)


def strip_trailing_whitespace(text: str) -> str:
    """Strip trailing whitespace per line."""
    lines = text.split('\n')
    lines = [line.rstrip() for line in lines]
    return '\n'.join(lines)


def load_names_map(names_json_path: str) -> Dict[str, str]:
    """Load character name mappings from JSON."""
    if not Path(names_json_path).exists():
        return {}
    
    with open(names_json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def fix_character_names(text: str, names_map: Dict[str, str]) -> Tuple[str, Dict[str, int]]:
    """
    Replace character names with canonical Myanmar versions.
    Returns (fixed_text, fix_counts).
    """
    fix_counts = {}
    
    for chinese_name, myanmar_name in names_map.items():
        # Count occurrences before replacement
        count = text.count(chinese_name)
        if count > 0:
            text = text.replace(chinese_name, myanmar_name)
            fix_counts[chinese_name] = count
            print(f"  ✓ {chinese_name} → {myanmar_name} ({count} occurrences)")
    
    return text, fix_counts


def check_remaining_chinese(text: str) -> list:
    """Check for remaining Chinese characters in output."""
    # Pattern for Chinese characters
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    
    matches = []
    for line_num, line in enumerate(text.split('\n'), 1):
        found = chinese_pattern.findall(line)
        if found:
            matches.append((line_num, found))
    
    return matches


def remove_non_myanmar_characters(text: str) -> str:
    """Remove any characters that are not Myanmar script or common punctuation/numbers."""
    # Myanmar Unicode range: U+1000 to U+109F
    # Basic ASCII: U+0020 to U+007E
    # Plus common control characters like \n, \r, \t
    # We want to keep:
    # 1. Myanmar script (\u1000-\u109F)
    # 2. Basic printable ASCII (\u0020-\u007E)
    # 3. Newlines, returns, tabs (\n, \r, \t)
    
    # This regex matches anything that is NOT in the allowed ranges
    pattern = re.compile(r'[^\u1000-\u109F\u0020-\u007E\n\r\t]+')
    cleaned_text = pattern.sub('', text)
    
    # We should NOT use re.sub(r'\s+', ' ', cleaned_text) here as it collapses newlines
    # Instead, we just strip trailing whitespace from each line if needed, 
    # but that's already handled in strip_trailing_whitespace
    
    return cleaned_text

def normalize_myanmar_whitespace(text: str) -> str:
    """Normalize Myanmar zero-width spaces."""
    # Myanmar zero-width space (U+200B) cleanup
    text = text.replace('\u200b\u200b', '\u200b')  # Collapse double
    return text


def postprocess(text: str, names_json_path: str = "names.json") -> str:
    """
    Main postprocessing function.
    
    Steps:
    A) Punctuation fixes
    B) Character name consistency    # C) Check for remaining Chinese chars (for warning, not removal here as it's handled by remove_non_myanmar_characters)
    # D) Remove any remaining non-Myanmar characters
    # E) Normalize whitespace
    """
    print("Postprocessing...")
    
    # A) Punctuation fixes
    text = fix_punctuation(text)
    text = collapse_blank_lines(text)
    text = strip_trailing_whitespace(text)
    
    # B) Character name consistency
    names_map = load_names_map(names_json_path)
    if names_map:
        print("Fixing character names:")
        text, fix_counts = fix_character_names(text, names_map)
        if not fix_counts:
            print("  (no names to fix)")
    
    # C) Check for remaining Chinese characters
    remaining = check_remaining_chinese(text)
    if remaining:
        print(f"⚠ WARNING: {len(remaining)} lines with Chinese characters found:")
        for line_num, chars in remaining[:5]:  # Show first 5
            print(f"  Line {line_num}: {chars}")
        if len(remaining) > 5:
            print(f"  ... and {len(remaining) - 5} more lines")
    
    # D) Remove any remaining non-Myanmar characters
    text = remove_non_myanmar_characters(text)

    # E) Normalize Myanmar whitespace
    text = normalize_myanmar_whitespace(text)
    
    return text


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python postprocessor.py <input_file> [names.json]")
        sys.exit(1)
    
    names_path = sys.argv[2] if len(sys.argv) >= 3 else "names.json"
    
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        text = f.read()
    
    result = postprocess(text, names_path)
    
    # Save back
    with open(sys.argv[1], 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"✓ Postprocessed: {sys.argv[1]}")
