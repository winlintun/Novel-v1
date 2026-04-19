#!/usr/bin/env python3
"""
Preprocess Chinese novel text files for translation.

This script cleans raw Chinese text files by:
- Removing headers, footers, watermarks, and ad text
- Normalizing whitespace and line endings
- Enforcing UTF-8 encoding
- Detecting chapter boundaries

Usage:
    python scripts/preprocess_novel.py <input_file> <output_file>
    python scripts/preprocess_novel.py input_novels/my_novel.txt working_data/clean/my_novel_clean.txt
"""

import os
import sys
import re
import json
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
LOG_DIR = Path("working_data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Only add handlers if they don't exist (prevents duplicate logs when module reloads)
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(LOG_DIR / "preprocess.log", encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def setup_directories():
    """Create necessary directories if they don't exist."""
    try:
        Path("working_data/clean").mkdir(parents=True, exist_ok=True)
        Path("working_data/logs").mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create directories: {e}")
        raise


def remove_headers_footers(text):
    """Remove common headers, footers, watermarks, and ads."""
    # Common patterns to remove
    patterns = [
        # Website watermarks
        r'www\.\S+\.\w{2,4}',
        r'https?://\S+',
        # Chapter navigation links
        r'(上一章|下一章|返回目录|阅读目录|章节列表).*?\n',
        # Common ad phrases
        r'(请记住本书域名|本书首发|版权所有|未经许可|不得转载|盗版必究)',
        # App promotion text
        r'(下载.*?APP|关注.*?公众号|加入.*?书友群).*?\n',
        # Page numbers in various formats
        r'^\s*第?\s*\d+\s*[页页]\s*$',
        # Separators that are just noise
        r'^[\-=\*]{3,}\s*$',
    ]
    
    cleaned = text
    for pattern in patterns:
        try:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE)
        except Exception as e:
            logger.error(f"Error applying pattern {pattern}: {e}")
    
    return cleaned


def normalize_whitespace(text):
    """Normalize whitespace and line endings."""
    try:
        # Replace Windows line endings
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        
        # Remove zero-width characters and other invisible Unicode
        text = re.sub(r'[\u200B\u200C\u200D\uFEFF]', '', text)
        
        # Normalize multiple blank lines to single blank line
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove trailing whitespace from lines
        text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
        
        # Ensure text starts and ends cleanly
        text = text.strip()
        
        return text
    except Exception as e:
        logger.error(f"Error normalizing whitespace: {e}")
        raise


def detect_chapter_boundaries(text):
    """Detect and log chapter boundaries if present."""
    try:
        # Common Chinese chapter patterns
        chapter_patterns = [
            r'第[一二三四五六七八九十百千万亿\d]+章',
            r'Chapter\s+\d+',
            r'^\s*\d+\s*[、\.．]\s*',
        ]
        
        chapters_found = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            for pattern in chapter_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    chapters_found.append({
                        'line_number': i + 1,
                        'preview': line[:50].strip()
                    })
                    break
        
        return chapters_found
    except Exception as e:
        logger.error(f"Error detecting chapter boundaries: {e}")
        return []


def read_file_utf8(filepath):
    """Read a file and ensure it's UTF-8 encoded."""
    filepath = Path(filepath)
    
    try:
        # Try UTF-8 first
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        logger.warning(f"File {filepath} is not UTF-8, attempting to detect encoding...")
        
        # Try common Chinese encodings
        encodings_to_try = ['gb2312', 'gbk', 'gb18030', 'big5', 'utf-16', 'latin-1']
        
        for encoding in encodings_to_try:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    content = f.read()
                logger.info(f"Successfully read file using {encoding} encoding")
                return content
            except (UnicodeDecodeError, LookupError):
                continue
        
        # If all fail, try with errors='replace' on UTF-8
        logger.error(f"Could not determine encoding for {filepath}, using replacement characters")
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {filepath}: {e}")
        raise


def preprocess_novel(input_path, output_path):
    """Main preprocessing function."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    logger.info(f"Starting preprocessing of {input_path}")
    
    try:
        # Verify input exists
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Setup directories
        setup_directories()
        
        # Read input file
        logger.info("Reading input file...")
        text = read_file_utf8(input_path)
        original_length = len(text)
        logger.info(f"Original text length: {original_length} characters")
        
        # Remove headers/footers/watermarks
        logger.info("Removing headers, footers, and watermarks...")
        text = remove_headers_footers(text)
        
        # Normalize whitespace
        logger.info("Normalizing whitespace...")
        text = normalize_whitespace(text)
        
        # Detect chapter boundaries
        logger.info("Detecting chapter boundaries...")
        chapters = detect_chapter_boundaries(text)
        logger.info(f"Detected {len(chapters)} potential chapter boundaries")
        
        # Write cleaned file
        logger.info(f"Writing cleaned file to {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        # Log statistics
        cleaned_length = len(text)
        reduction = original_length - cleaned_length
        logger.info(f"Preprocessing complete:")
        logger.info(f"  - Original length: {original_length}")
        logger.info(f"  - Cleaned length: {cleaned_length}")
        logger.info(f"  - Reduction: {reduction} characters ({reduction/original_length*100:.1f}%)")
        logger.info(f"  - Chapters detected: {len(chapters)}")
        
        # Save chapter detection log
        if chapters:
            chapter_log_path = Path("working_data/logs") / f"{input_path.stem}_chapters.json"
            try:
                with open(chapter_log_path, 'w', encoding='utf-8') as f:
                    json.dump(chapters, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Error saving chapter log: {e}")
        
        return {
            'success': True,
            'original_length': original_length,
            'cleaned_length': cleaned_length,
            'chapters_detected': len(chapters),
            'output_path': str(output_path)
        }
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise
    except PermissionError as e:
        logger.error(f"Permission denied: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during preprocessing: {e}")
        raise


def main():
    """Command line entry point."""
    if len(sys.argv) < 3:
        print("Usage: python preprocess_novel.py <input_file> <output_file>")
        print("Example: python preprocess_novel.py input_novels/my_novel.txt working_data/clean/my_novel_clean.txt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    try:
        result = preprocess_novel(input_file, output_file)
        print(f"✓ Preprocessing complete: {result['cleaned_length']} characters")
        sys.exit(0)
    except Exception as e:
        print(f"✗ Preprocessing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
