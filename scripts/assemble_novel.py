#!/usr/bin/env python3
"""
Assemble translated Burmese chunks into a final formatted Markdown file.

This script merges all post-processed translated chunks into a single
well-formatted Markdown document with proper Burmese chapter headings.

Usage:
    python scripts/assemble_novel.py <novel_name>
    python scripts/assemble_novel.py my_novel
"""

import os
import sys
import json
import re
import logging
from pathlib import Path
from datetime import datetime

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
    file_handler = logging.FileHandler(LOG_DIR / "assemble.log", encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def load_config():
    """Load configuration from config.json."""
    try:
        config_path = Path("config/config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Config file not found: config/config.json")
        return {}
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}


# Burmese numerals for chapter headings
BURMESE_DIGITS = '၀၁၂၃၄၅၆၇၈၉'

def to_burmese_number(n):
    """Convert an integer to Burmese numerals."""
    try:
        result = ''
        for digit in str(n):
            result += BURMESE_DIGITS[int(digit)]
        return result
    except Exception as e:
        logger.error(f"Error converting number to Burmese: {e}")
        return str(n)


def extract_chapter_info(chunks_dir, novel_name):
    """Extract chapter information from chunk files if available."""
    try:
        # Look for chunk metadata
        metadata_file = chunks_dir / f"{novel_name}_chunks.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        logger.error(f"Error extracting chapter info: {e}")
        return None


def generate_yaml_front_matter(novel_name, chapter_info, total_chunks, config):
    """Generate YAML front matter for the Markdown file."""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Estimate chapter count (rough approximation: 1 chapter per 10 chunks)
        estimated_chapters = max(1, total_chunks // 10)
        
        front_matter = f"""---
title: "{novel_name} (မြန်မာဘာသာပြန်)"
source_title: "{novel_name}"
language: Burmese (Myanmar Script)
source_language: Chinese
translated_date: {today}
font_recommendation: "Padauk, Noto Sans Myanmar"
total_chapters: {estimated_chapters}
total_chunks: {total_chunks}
translation_model: {config.get('model', 'qwen3:7b')}
---

"""
        return front_matter
        
    except Exception as e:
        logger.error(f"Error generating YAML front matter: {e}")
        return f"---\ntitle: \"{novel_name}\"\n---\n\n"


def generate_novel_title(novel_name):
    """Generate the novel title in Burmese format."""
    try:
        # Convert novel name to a Burmese-friendly title
        # For now, use the novel name as-is (it may be preserved Chinese or already Burmese)
        return f"# {novel_name} (မြန်မာဘာသာပြန်)\n\n---\n\n"
    except Exception as e:
        logger.error(f"Error generating novel title: {e}")
        return f"# {novel_name}\n\n"


def generate_chapter_header(chapter_num):
    """Generate a chapter header in Burmese format."""
    try:
        burmese_num = to_burmese_number(chapter_num)
        
        # Chapter titles in Burmese
        if chapter_num == 1:
            return f"## အခန်း {burmese_num} — နိဒါန်းပျိုး\n\n"
        else:
            return f"## အခန်း {burmese_num}\n\n"
            
    except Exception as e:
        logger.error(f"Error generating chapter header: {e}")
        return f"## အခန်း {chapter_num}\n\n"


def load_translated_chunks(translated_dir, novel_name):
    """
    Load all translated chunks for a novel in correct order.
    
    Returns:
        List of (chunk_number, chunk_text) tuples, sorted by chunk number
    """
    try:
        # Find all translated chunk files
        pattern = f"{novel_name}_chunk_*.txt"
        chunk_files = list(translated_dir.glob(pattern))
        
        if not chunk_files:
            logger.error(f"No translated chunks found for {novel_name} in {translated_dir}")
            return []
        
        logger.info(f"Found {len(chunk_files)} translated chunk files")
        
        # Parse chunk numbers and sort
        chunks = []
        for chunk_file in chunk_files:
            try:
                # Extract chunk number from filename (e.g., novel_chunk_00001.txt -> 1)
                match = re.search(r'_chunk_(\d+)\.txt$', chunk_file.name)
                if match:
                    chunk_num = int(match.group(1))
                    
                    with open(chunk_file, 'r', encoding='utf-8') as f:
                        text = f.read()
                    
                    chunks.append((chunk_num, text))
                else:
                    logger.warning(f"Could not parse chunk number from {chunk_file.name}")
                    
            except Exception as e:
                logger.error(f"Error loading chunk file {chunk_file}: {e}")
        
        # Sort by chunk number
        chunks.sort(key=lambda x: x[0])
        
        logger.info(f"Successfully loaded {len(chunks)} chunks in order")
        return chunks
        
    except Exception as e:
        logger.error(f"Error loading translated chunks: {e}")
        return []


def assemble_novel_content(chunks, estimated_chapters_per_chunk=10):
    """
    Assemble chunks into formatted novel content with chapter breaks.
    
    Args:
        chunks: List of (chunk_number, chunk_text) tuples
        estimated_chapters_per_chunk: Approximate chunks per chapter
        
    Returns:
        Assembled novel content as string
    """
    try:
        content_parts = []
        current_chapter = 0
        
        for i, (chunk_num, chunk_text) in enumerate(chunks):
            # Determine if this should start a new chapter
            # Every N chunks or if chunk text contains clear chapter indicators
            estimated_chapter = (chunk_num - 1) // estimated_chapters_per_chunk + 1
            
            if estimated_chapter > current_chapter:
                # Add chapter separator (except before first chapter)
                if current_chapter > 0:
                    content_parts.append("\n---\n\n")
                
                # Add new chapter header
                current_chapter = estimated_chapter
                content_parts.append(generate_chapter_header(current_chapter))
            
            # Add paragraph breaks to chunk text if needed
            paragraphs = chunk_text.split('\n')
            formatted_paragraphs = []
            
            for para in paragraphs:
                para = para.strip()
                if para:
                    formatted_paragraphs.append(para)
                    formatted_paragraphs.append('')  # Blank line after paragraph
            
            # Join paragraphs and add to content
            formatted_chunk = '\n'.join(formatted_paragraphs).strip()
            content_parts.append(formatted_chunk)
            content_parts.append('\n\n')
            
            logger.debug(f"Added chunk {chunk_num} to chapter {current_chapter}")
        
        return ''.join(content_parts)
        
    except Exception as e:
        logger.error(f"Error assembling novel content: {e}")
        return ""


def assemble_novel(novel_name, translated_dir=None, output_dir=None, source_file=None):
    """
    Assemble all translated chunks into a final Markdown file.
    
    Args:
        novel_name: Name of the novel
        translated_dir: Directory containing translated chunks
        output_dir: Directory to save final Markdown file
        source_file: Optional path to source file for metadata
        
    Returns:
        Dictionary with assembly results
    """
    try:
        # Setup paths
        if translated_dir is None:
            translated_dir = Path("working_data/translated_chunks") / novel_name
        else:
            translated_dir = Path(translated_dir)
        
        if output_dir is None:
            output_dir = Path("translated_novels")
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Assembling novel: {novel_name}")
        logger.info(f"Input directory: {translated_dir}")
        
        # Load config
        config = load_config()
        
        # Load all translated chunks
        chunks = load_translated_chunks(translated_dir, novel_name)
        
        if not chunks:
            raise FileNotFoundError(f"No translated chunks found for {novel_name}")
        
        # Get chapter info
        chunks_dir = Path("working_data/chunks") / novel_name
        chapter_info = extract_chapter_info(chunks_dir, novel_name)
        
        # Generate YAML front matter
        front_matter = generate_yaml_front_matter(
            novel_name, chapter_info, len(chunks), config
        )
        
        # Generate novel title
        title = generate_novel_title(novel_name)
        
        # Assemble content
        content = assemble_novel_content(chunks)
        
        # Combine all parts
        final_text = front_matter + title + content
        
        # Write output file
        output_file = output_dir / f"{novel_name}_burmese.md"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(final_text)
            logger.info(f"Saved final novel to: {output_file}")
        except Exception as e:
            logger.error(f"Error writing output file: {e}")
            raise
        
        # File statistics
        file_size = output_file.stat().st_size
        char_count = len(final_text)
        
        result = {
            'success': True,
            'novel_name': novel_name,
            'output_file': str(output_file),
            'total_chunks': len(chunks),
            'file_size_bytes': file_size,
            'character_count': char_count
        }
        
        logger.info(f"Assembly complete:")
        logger.info(f"  - Total chunks: {result['total_chunks']}")
        logger.info(f"  - Output file: {result['output_file']}")
        logger.info(f"  - File size: {file_size:,} bytes")
        logger.info(f"  - Character count: {char_count:,}")
        
        return result
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error assembling novel: {e}")
        raise


def main():
    """Command line entry point."""
    if len(sys.argv) < 2:
        print("Usage: python assemble_novel.py <novel_name>")
        print("Example: python assemble_novel.py my_novel")
        sys.exit(1)
    
    novel_name = sys.argv[1]
    
    try:
        result = assemble_novel(novel_name)
        
        print(f"✓ Assembly complete: {result['output_file']}")
        print(f"  - {result['total_chunks']} chunks assembled")
        print(f"  - {result['character_count']:,} characters")
        sys.exit(0)
        
    except Exception as e:
        print(f"✗ Assembly failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
