#!/usr/bin/env python3
"""
Phase 1: Split input novels into chapters and save as separate English .md files

This script:
1. Reads input_novels/*.txt files
2. Detects chapters using pattern:
   ============================================================
   Chapter X: [title]
   ============================================================
3. Saves each chapter as a separate .md file in english_chapters/ directory

Usage:
    python scripts/extract_chapters.py
    python scripts/extract_chapters.py <novel_name>
"""

import os
import sys
import re
import json
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
LOG_DIR = Path("working_data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    file_handler = logging.FileHandler(LOG_DIR / "extract_chapters.log", encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def detect_chapters(text):
    """
    Detect chapter boundaries using pattern:
    ============================================================
    Chapter X: [title]
    ============================================================
    
    Returns list of dicts with chapter info
    """
    chapters = []
    lines = text.split('\n')
    
    # Pattern to match chapter headers with === delimiters
    # Matches lines like "Chapter 1: Chapter 1 Gu Wen" or "Chapter 1 - Title" or "Chapter 1"
    chapter_title_pattern = r'^Chapter\s+(\d+)[:\s\-]+(.+)$'
    delimiter_pattern = r'^[=_\-]{20,}$'  # 20+ characters of =, _, or -
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for delimiter line
        if re.match(delimiter_pattern, line):
            # Check if next line is a chapter title
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                match = re.match(chapter_title_pattern, next_line, re.IGNORECASE)
                
                if match:
                    chapter_num = int(match.group(1))
                    chapter_title = match.group(2).strip()
                    
                    # Verify there's another delimiter after the title
                    if i + 2 < len(lines) and re.match(delimiter_pattern, lines[i + 2].strip()):
                        # Calculate position (start of the delimiter)
                        pos = sum(len(lines[j]) + 1 for j in range(i))
                        
                        chapters.append({
                            'number': chapter_num,
                            'title': chapter_title,
                            'line_number': i + 1,
                            'position': pos
                        })
                        logger.info(f"Detected Chapter {chapter_num}: {chapter_title}")
                        i += 3  # Skip the delimiter, title, and next delimiter
                        continue
        
        i += 1
    
    return chapters


def extract_chapter_content(text, chapter, next_chapter=None):
    """Extract content for a specific chapter."""
    start_pos = chapter['position']
    
    if next_chapter:
        end_pos = next_chapter['position']
    else:
        end_pos = len(text)
    
    content = text[start_pos:end_pos].strip()
    
    # Remove the chapter header (delimiter + title + delimiter) from content
    lines = content.split('\n')
    # Find where the actual content starts (after the second delimiter)
    delimiter_count = 0
    content_start = 0
    for j, line in enumerate(lines):
        if re.match(r'^[=_\-]{20,}$', line.strip()):
            delimiter_count += 1
            if delimiter_count == 2:
                content_start = j + 1
                break
    
    if content_start > 0:
        content = '\n'.join(lines[content_start:]).strip()
    
    return content


def save_chapter_as_markdown(novel_name, chapter, content, output_dir):
    """
    Save a chapter as a Markdown file.
    
    Returns:
        Path to saved file
    """
    try:
        chapter_num = chapter['number']
        chapter_title = chapter['title']
        
        # Create output directory
        novel_dir = Path(output_dir) / novel_name
        novel_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename: novel_chapter_001.md
        md_file = novel_dir / f"{novel_name}_chapter_{chapter_num:03d}.md"
        
        # Create markdown content
        md_content = f"""# {novel_name} - Chapter {chapter_num:03d}: {chapter_title}

---

{content}

---
*Source: {novel_name}*
*Chapter: Chapter {chapter_num:03d} - {chapter_title}*
*Extracted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        # Write file
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"Saved Chapter {chapter_num}: {md_file}")
        return str(md_file)
        
    except Exception as e:
        logger.error(f"Error saving chapter {chapter['number']}: {e}")
        raise


# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def extract_novel_chapters(novel_file, output_dir="chinese_chapters"):
    """
    Extract all chapters from a novel file.
    
    Args:
        novel_file: Path to input .txt file
        output_dir: Directory to save chapter .md files
    
    Returns:
        Dictionary with extraction results
    """
    try:
        novel_path = Path(novel_file)
        novel_name = novel_path.stem
        
        logger.info(f"=" * 60)
        logger.info(f"Extracting chapters from: {novel_name}")
        logger.info(f"=" * 60)
        
        # Read input file
        logger.info(f"Reading: {novel_path}")
        with open(novel_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        logger.info(f"Total text length: {len(text)} characters")
        
        # Detect chapters
        chapters = detect_chapters(text)
        
        if not chapters:
            logger.warning("No chapters detected! Treating entire file as one chapter.")
            chapters = [{
                'number': 1,
                'title': 'Full Text',
                'line_number': 1,
                'position': 0
            }]
        
        logger.info(f"Found {len(chapters)} chapters")
        
        # Extract and save each chapter
        saved_files = []
        for i, chapter in enumerate(chapters):
            next_chapter = chapters[i + 1] if i + 1 < len(chapters) else None
            content = extract_chapter_content(text, chapter, next_chapter)
            
            md_file = save_chapter_as_markdown(novel_name, chapter, content, output_dir)
            saved_files.append({
                'chapter_number': chapter['number'],
                'chapter_title': chapter['title'],
                'file': md_file,
                'characters': len(content)
            })
        
        # Save metadata
        metadata = {
            'novel_name': novel_name,
            'source_file': str(novel_file),
            'total_chapters': len(chapters),
            'extraction_date': datetime.now().isoformat(),
            'chapters': saved_files
        }
        
        metadata_file = Path(output_dir) / novel_name / f"{novel_name}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        logger.info(f"=" * 60)
        logger.info(f"✓ Extraction complete: {len(saved_files)} chapters saved")
        logger.info(f"Output: {Path(output_dir) / novel_name}")
        logger.info(f"=" * 60)
        
        return {
            'success': True,
            'novel_name': novel_name,
            'total_chapters': len(chapters),
            'chapter_files': saved_files,
            'metadata_file': str(metadata_file),
            'output_dir': str(Path(output_dir) / novel_name)
        }
        
    except Exception as e:
        logger.error(f"Error extracting chapters: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def extract_all_novels(input_dir="input_novels", output_dir="english_chapters"):
    """
    Extract chapters from all .txt files in input_novels/
    
    Returns:
        List of extraction results
    """
    input_path = Path(input_dir)
    
    if not input_path.exists():
        logger.error(f"Input directory not found: {input_path}")
        return []
    
    txt_files = list(input_path.glob("*.txt"))
    
    if not txt_files:
        logger.warning(f"No .txt files found in {input_path}")
        return []
    
    logger.info(f"Found {len(txt_files)} novel(s) to process")
    
    results = []
    for txt_file in txt_files:
        result = extract_novel_chapters(str(txt_file), output_dir)
        results.append(result)
    
    return results


def main():
    """Command line entry point."""
    if len(sys.argv) > 1:
        # Extract specific novel
        novel_name = sys.argv[1]
        input_file = Path("input_novels") / f"{novel_name}.txt"
        
        if not input_file.exists():
            print(f"✗ File not found: {input_file}")
            sys.exit(1)
        
        result = extract_novel_chapters(str(input_file))
        
        if result['success']:
            print(f"\n✓ Extracted {result['total_chapters']} chapters")
            for ch in result['chapter_files']:
                print(f"  - Chapter {ch['chapter_number']}: {ch['file']}")
            sys.exit(0)
        else:
            print(f"✗ Extraction failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
    else:
        # Extract all novels
        results = extract_all_novels()
        
        total_novels = len([r for r in results if r.get('success')])
        print(f"\n✓ Processed {total_novels} novel(s)")
        
        for result in results:
            if result.get('success'):
                print(f"  - {result['novel_name']}: {result['total_chapters']} chapters")


if __name__ == "__main__":
    main()
