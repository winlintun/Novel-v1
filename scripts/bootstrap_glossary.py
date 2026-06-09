#!/usr/bin/env python3
"""
scripts/bootstrap_glossary.py
Semi-Automated Glossary Bootstrapping (DB-only)
Extracts proper nouns from Chinese/English source text and creates
initial glossary entries directly in the SQLite database.
"""

import re
import json
import argparse
import logging
from pathlib import Path
from collections import Counter
from typing import List, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.connection import DatabaseConnection
from src.db.schema import SchemaManager
from src.db.repositories.glossary_repo import GlossaryRepository
from src.db.repositories.novel_repo import NovelRepository
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
    
    # Insert terms directly into the database
    db = DatabaseConnection("data/novel_translation.db")
    schema = SchemaManager(db)
    schema.create_all()
    repo = GlossaryRepository(db)
    novel_repo = NovelRepository(db)
    
    novel_name = args.novel_name or Path(args.input_file).parent.name
    novel_id = f"novel_{novel_name.replace('-', '_').replace(' ', '_')}"
    if not novel_repo.exists(novel_id):
        novel_repo.create(novel_id, novel_name, "chinese")
    
    pending_glossary = create_pending_glossary(terms, chapter_num=1)
    inserted = 0
    for t in pending_glossary.get("pending_terms", []):
        try:
            existing = repo.get_term_by_source(novel_id, t["source"])
            if existing:
                continue
            repo.add_term(
                novel_id=novel_id,
                source_term=t["source"],
                target_term=t["target"],
                category=t["category"],
                status="pending",
                enforcement_level="soft",
                confidence=0.5,
            )
            inserted += 1
        except Exception as e:
            logger.warning(f"Failed to insert term '{t['source']}': {e}")
    
    db.close()
    
    logger.info(f"Inserted {inserted} pending terms into database for novel '{novel_name}'")
    
    # Summary
    logger.info(f"\nTop 10 terms:")
    for term, count in terms[:10]:
        logger.info(f"  {term}: {count} occurrences")
    
    print("\nNext steps:")
    print("1. Review pending terms via Web UI or CLI (--approve-glossary)")
    print("2. Add proper Myanmar translations for each term")
    print("3. Approve via: python -m src.main --novel <name> --approve-glossary")
    
    return 0


if __name__ == "__main__":
    exit(main())
