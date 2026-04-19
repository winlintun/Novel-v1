#!/usr/bin/env python3
"""
Preprocessor - Clean raw .txt input files
"""

import re
from pathlib import Path
from typing import Tuple

# Common web-novel noise patterns
NOISE_PATTERNS = [
    r'本章完',
    r'求收藏',
    r'推荐票',
    r'求推荐',
    r'求订阅',
    r'求月票',
    r'求打赏',
    r'新书推荐',
    r'温馨提示',
    r'本章结束',
    r'未完待续',
    r'下章预告',
    r'作者的话',
    r'PS[：:]',
    r'ps[：:]',
    r'ＰＳ[：:]',
    r'【本书首发】',
    r'【追书帮】',
    r'【.*?(?:中文网|小说网|阅读网)】',
]


def detect_encoding(filepath: str) -> Tuple[str, str]:
    """Detect and return file encoding."""
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'utf-16', 'big5']
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            return encoding, content
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    # Fallback to utf-8 with error handling
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    return 'utf-8 (with errors)', content


def remove_noise(text: str) -> Tuple[str, int]:
    """Remove common web-novel noise patterns."""
    original_lines = text.split('\n')
    cleaned_lines = []
    noise_count = 0
    
    for line in original_lines:
        original_line = line
        is_noise = False
        
        # Check against noise patterns
        for pattern in NOISE_PATTERNS:
            if re.search(pattern, line):
                is_noise = True
                noise_count += 1
                break
        
        if not is_noise:
            cleaned_lines.append(line)
        else:
            noise_count += 1
    
    return '\n'.join(cleaned_lines), noise_count


def collapse_blank_lines(text: str) -> str:
    """Collapse 3+ consecutive blank lines to 2."""
    # Replace 3 or more newlines with 2
    return re.sub(r'\n{3,}', '\n\n', text)


def remove_duplicate_title(text: str) -> Tuple[str, int]:
    """Remove repeated chapter title lines, keep first only."""
    lines = text.split('\n')
    if not lines:
        return text, 0
    
    # Pattern for Chinese chapter titles
    title_pattern = r'^第[一二三四五六七八九十百千零\d]+章'
    
    first_title = None
    removed = 0
    result_lines = []
    
    for line in lines:
        stripped = line.strip()
        if re.match(title_pattern, stripped):
            if first_title is None:
                first_title = stripped
                result_lines.append(line)
            else:
                # Skip duplicate titles
                removed += 1
                continue
        else:
            result_lines.append(line)
    
    return '\n'.join(result_lines), removed


def preprocess(filepath: str) -> str:
    """
    Main preprocessing function.
    
    Steps:
    1. Detect and fix encoding
    2. Normalize line endings (CRLF → LF)
    3. Remove common web-novel noise
    4. Remove duplicate titles
    5. Collapse excessive blank lines
    6. Strip whitespace
    """
    print(f"Preprocessing: {filepath}")
    
    # Step 1 & 2: Detect encoding and read
    encoding, content = detect_encoding(filepath)
    original_length = len(content)
    original_lines = content.count('\n') + 1
    
    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Step 3: Remove noise
    content, noise_removed = remove_noise(content)
    
    # Step 4: Remove duplicate titles
    content, titles_removed = remove_duplicate_title(content)
    
    # Step 5: Collapse blank lines
    content = collapse_blank_lines(content)
    
    # Step 6: Strip whitespace per line
    lines = content.split('\n')
    lines = [line.strip() for line in lines]
    content = '\n'.join(lines)
    
    # Calculate stats
    final_length = len(content)
    final_lines = content.count('\n') + 1
    lines_removed = original_lines - final_lines
    
    # Print report
    print("┌──────────────────────────────────┐")
    print("│ Preprocessor Report              │")
    print(f"│ Encoding detected : {encoding:<14} │")
    print(f"│ Lines removed     : {lines_removed:<14} │")
    print(f"│ Noise patterns    : {noise_removed:<14} │")
    print(f"│ Final char count  : {final_length:,}{' ' * (14 - len(str(final_length)))} │")
    print("└──────────────────────────────────┘")
    
    return content


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python preprocessor.py <input_file>")
        sys.exit(1)
    
    result = preprocess(sys.argv[1])
    
    # Save to stdout or file
    if len(sys.argv) >= 3:
        with open(sys.argv[2], 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"Saved to: {sys.argv[2]}")
    else:
        print(result)
