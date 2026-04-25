#!/usr/bin/env python3
"""
scripts/bootstrap_glossary.py
Semi-Automated Glossary Bootstrapping
Extracts proper nouns from Chinese text and creates initial glossary entries.
"""

import re
import json
import argparse
import logging
import shutil
from pathlib import Path
from collections import Counter
from typing import List, Tuple

# Add src to path for imports
import sys
sys.path.insert(0, '/home/wangyi/Desktop/Novel_Translation/novel_translation_project')

from src.utils.file_handler import FileHandler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_proper_nouns(
    chinese_text: str,
    min_length: int = 2,
    max_length: int = 4,
    min_count: int = 2
) -> List[Tuple[str, int]]:
    """
    Extract potential proper nouns from Chinese text.
    
    Uses heuristic: 2-4 character sequences that appear multiple times
    are likely proper nouns (names, places, terms).
    
    Args:
        chinese_text: Raw Chinese text to analyze
        min_length: Minimum characters for a candidate term
        max_length: Maximum characters for a candidate term
        min_count: Minimum occurrences to be considered significant
        
    Returns:
        List of (term, count) tuples sorted by frequency
    """
    # Chinese character range (CJK Unified Ideographs)
    chinese_char_range = r'\u4e00-\u9fff'
    
    # Pattern to match 2-4 character sequences
    pattern = f"[{chinese_char_range}]{{{min_length},{max_length}}}"
    
    # Find all candidates
    candidates = re.findall(pattern, chinese_text)
    
    # Count occurrences
    counter = Counter(candidates)
    
    # Filter by minimum count and return sorted list
    significant_terms = [
        (term, count) 
        for term, count in counter.most_common(100) 
        if count >= min_count
    ]
    
    return significant_terms


def detect_category(term: str) -> str:
    """
    Heuristic to detect term category based on patterns.
    
    Args:
        term: Chinese term to categorize
        
    Returns:
        Category: "character", "place", "level", or "item"
    """
    # Place indicators
    place_suffixes = ['城', '山', '谷', '洞', '府', '宫', '殿', '阁', '岛', '湖', '河', '林', '原', '地', '界', '域']
    # Cultivation level indicators
    level_suffixes = ['功', '法', '经', '诀', '术', '道', '境', '期', '层', '重', '阶', '级', '气', '元']
    # Item indicators
    item_suffixes = ['剑', '刀', '枪', '棍', '棒', '鞭', '索', '环', '珠', '玉', '石', '丹', '药', '符', '器', '宝', '甲', '衣', '袍', '冠', '带']
    
    # Check suffixes
    for suffix in place_suffixes:
        if term.endswith(suffix):
            return "place"
    for suffix in level_suffixes:
        if term.endswith(suffix):
            return "level"
    for suffix in item_suffixes:
        if term.endswith(suffix):
            return "item"
    
    # Default to character (most proper nouns are names)
    return "character"


def create_pending_glossary(terms: List[Tuple[str, int]], chapter_num: int = 1) -> dict:
    """
    Create a pending glossary dictionary matching project schema.
    
    Args:
        terms: List of (term, count) tuples
        chapter_num: Chapter number for extracted_from_chapter
        
    Returns:
        Pending glossary dict with {"pending_terms": [...]} structure
    """
    pending_terms = []
    
    for term, count in terms:
        category = detect_category(term)
        term_entry = {
            "source": term,
            "target": f"【?{term}?】",
            "category": category,
            "extracted_from_chapter": chapter_num,
            "status": "pending"
        }
        pending_terms.append(term_entry)
    
    return {"pending_terms": pending_terms}


def main() -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Bootstrap glossary from Chinese novel text"
    )
    parser.add_argument(
        "input_file",
        help="Path to Chinese text file (e.g., data/input/novel/chapter_001.md)"
    )
    parser.add_argument(
        "--novel-name",
        default="",
        help="Name of the novel for glossary metadata"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/glossary_pending.json",
        help="Output file path (default: data/glossary_pending.json)"
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=2,
        help="Minimum occurrences to include term (default: 2)"
    )
    parser.add_argument(
        "--max-terms",
        type=int,
        default=50,
        help="Maximum number of terms to extract (default: 50)"
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input_file)
    
    # Error handling for file operations
    try:
        if not input_path.exists():
            logger.error(f"File not found: {input_path}")
            return 1
        
        logger.info(f"Reading: {input_path}")
        # Use FileHandler for consistent file I/O (utf-8-sig encoding)
        chinese_text = FileHandler.read_text(str(input_path))
        
        if not chinese_text.strip():
            logger.error(f"File is empty: {input_path}")
            return 1
        
        # Validate Chinese content
        if not re.search(r'[\u4e00-\u9fff]', chinese_text):
            logger.error(f"No Chinese characters found in {input_path}")
            return 1
            
    except UnicodeDecodeError as e:
        logger.error(f"Encoding error reading {input_path}: {e}")
        return 1
    except PermissionError:
        logger.error(f"Permission denied: {input_path}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error reading file: {e}")
        return 1
    
    # Extract terms
    logger.info("Extracting proper nouns...")
    terms = extract_proper_nouns(
        chinese_text,
        min_count=args.min_count
    )[:args.max_terms]
    
    logger.info(f"Found {len(terms)} significant terms")
    
    # Create pending glossary
    pending_glossary = create_pending_glossary(terms, chapter_num=1)
    
    # Save using FileHandler for atomic writes with backup
    output_path = Path(args.output)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create backup if file exists
        if output_path.exists():
            backup_path = output_path.with_suffix('.json.bak')
            shutil.copy2(output_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
        
        # Use FileHandler for atomic JSON write
        FileHandler.write_json(str(output_path), pending_glossary)
        logger.info(f"Saved {len(pending_glossary['pending_terms'])} pending terms to: {output_path}")
        
    except PermissionError:
        logger.error(f"Permission denied writing to: {output_path}")
        return 1
    except Exception as e:
        logger.error(f"Error saving glossary: {e}")
        return 1
    
    # Summary
    logger.info(f"\nTop 10 terms:")
    for term, count in terms[:10]:
        logger.info(f"  {term}: {count} occurrences")
    
    print("\nNext steps:")
    print("1. Review glossary_pending.json")
    print("2. Add proper Myanmar translations for each term")
    print("3. Set 'verified: true' for approved terms")
    print("4. Move to data/glossary.json for production use")
    
    return 0


if __name__ == "__main__":
    exit(main())
