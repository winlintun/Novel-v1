#!/usr/bin/env python3
"""
Chunk Chinese novel text by paragraph boundaries (no overlap).

This script splits text into chunks at paragraph boundaries,
with configurable max chunk size. No overlap between chunks.

Usage:
    python scripts/chunk_paragraph.py <input_file_or_dir> <output_dir>
    python scripts/chunk_paragraph.py chinese_chapters/古道仙鸿 working_data/chunks/
"""

import os
import sys
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple

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
    file_handler = logging.FileHandler(LOG_DIR / "chunk.log", encoding='utf-8')
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
        return {'chunk_size': 1500}
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {'chunk_size': 1500}


def split_into_paragraphs(text: str) -> List[str]:
    """
    Split text into paragraphs.
    Paragraphs are separated by one or more blank lines.
    """
    # Split on one or more newlines
    paragraphs = re.split(r'\n\s*\n', text)
    # Clean and filter empty paragraphs
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    return paragraphs


def chunk_by_paragraphs(paragraphs: List[str], max_chunk_size: int) -> List[str]:
    """
    Group paragraphs into chunks without exceeding max_chunk_size.
    Each chunk contains complete paragraphs (no splitting within paragraphs).
    No overlap between chunks.
    
    Args:
        paragraphs: List of paragraph strings
        max_chunk_size: Maximum characters per chunk
        
    Returns:
        List of chunk strings
    """
    chunks = []
    current_chunk = []
    current_size = 0
    
    for paragraph in paragraphs:
        para_size = len(paragraph)
        
        # If a single paragraph exceeds max size, we have to split it at sentence boundaries
        if para_size > max_chunk_size:
            # First save current chunk if any
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            # Split oversized paragraph at sentence boundaries
            para_chunks = split_large_paragraph(paragraph, max_chunk_size)
            chunks.extend(para_chunks)
            continue
        
        # Check if adding this paragraph would exceed the limit
        # Add 2 for the '\n\n' separator
        projected_size = current_size + (2 if current_chunk else 0) + para_size
        
        if projected_size <= max_chunk_size:
            # Add to current chunk
            current_chunk.append(paragraph)
            current_size = projected_size
        else:
            # Save current chunk and start new one
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            current_chunk = [paragraph]
            current_size = para_size
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks


def split_large_paragraph(paragraph: str, max_size: int) -> List[str]:
    """
    Split a large paragraph at sentence boundaries.
    
    Args:
        paragraph: The paragraph to split
        max_size: Maximum size for each piece
        
    Returns:
        List of sentence-group chunks
    """
    # Chinese sentence endings
    sentence_endings = r'[。！？；\.!?;]'
    
    # Split into sentences
    sentences = re.split(f'({sentence_endings})', paragraph)
    # Recombine sentences with their ending punctuation
    combined = []
    i = 0
    while i < len(sentences):
        if i + 1 < len(sentences) and re.match(sentence_endings, sentences[i + 1]):
            combined.append(sentences[i] + sentences[i + 1])
            i += 2
        else:
            if sentences[i].strip():
                combined.append(sentences[i])
            i += 1
    
    # Group sentences into chunks
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in combined:
        sent_size = len(sentence)
        projected_size = current_size + (1 if current_chunk else 0) + sent_size
        
        if projected_size <= max_size:
            current_chunk.append(sentence)
            current_size = projected_size
        else:
            if current_chunk:
                chunks.append(''.join(current_chunk))
            current_chunk = [sentence]
            current_size = sent_size
    
    if current_chunk:
        chunks.append(''.join(current_chunk))
    
    return chunks


def chunk_text_file(input_file: Path, output_dir: Path, max_chunk_size: int = 1500) -> Dict:
    """
    Chunk a single text file by paragraphs.
    
    Returns:
        Dictionary with chunking results
    """
    logger.info(f"Processing: {input_file}")
    
    # Read file
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    if not text.strip():
        logger.warning(f"Empty file: {input_file}")
        return {'success': False, 'error': 'Empty file'}
    
    # Split into paragraphs
    paragraphs = split_into_paragraphs(text)
    logger.info(f"  Found {len(paragraphs)} paragraphs")
    
    # Chunk by paragraphs
    chunks = chunk_by_paragraphs(paragraphs, max_chunk_size)
    logger.info(f"  Created {len(chunks)} chunks")
    
    # Save chunks
    novel_name = input_file.stem
    file_output_dir = output_dir / novel_name
    file_output_dir.mkdir(parents=True, exist_ok=True)
    
    chunk_files = []
    for i, chunk in enumerate(chunks, 1):
        chunk_file = file_output_dir / f"{novel_name}_chunk_{i:05d}.txt"
        with open(chunk_file, 'w', encoding='utf-8') as f:
            f.write(chunk)
        chunk_files.append(str(chunk_file))
    
    # Save metadata
    metadata = {
        'source_file': str(input_file),
        'novel_name': novel_name,
        'total_paragraphs': len(paragraphs),
        'total_chunks': len(chunks),
        'chunk_files': chunk_files,
        'max_chunk_size': max_chunk_size,
        'overlap': 0
    }
    
    metadata_file = file_output_dir / f"{novel_name}_chunks.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"  Saved to: {file_output_dir}")
    
    return {
        'success': True,
        'novel_name': novel_name,
        'total_chunks': len(chunks),
        'output_dir': str(file_output_dir),
        'chunk_files': chunk_files,
        'metadata_file': str(metadata_file)
    }


def chunk_novel_chapters(novel_dir: Path, output_dir: Path, max_chunk_size: int = 1500) -> Dict:
    """
    Chunk all chapters of a novel.
    
    Args:
        novel_dir: Directory containing chapter .md files
        output_dir: Directory to save chunks
        max_chunk_size: Maximum chunk size in characters
        
    Returns:
        Dictionary with chunking results for all chapters
    """
    novel_name = novel_dir.name
    logger.info(f"="*60)
    logger.info(f"Chunking novel: {novel_name}")
    logger.info(f"="*60)
    
    # Find all chapter files
    chapter_files = sorted(novel_dir.glob("*.md"))
    if not chapter_files:
        logger.warning(f"No chapter files found in {novel_dir}")
        return {'success': False, 'error': 'No chapters found'}
    
    logger.info(f"Found {len(chapter_files)} chapters")
    
    all_chunk_files = []
    chapter_results = []
    
    for chapter_file in chapter_files:
        result = chunk_text_file(chapter_file, output_dir, max_chunk_size)
        if result['success']:
            chapter_results.append(result)
            all_chunk_files.extend(result['chunk_files'])
    
    # Save overall metadata
    overall_metadata = {
        'novel_name': novel_name,
        'total_chapters': len(chapter_results),
        'total_chunks': sum(r['total_chunks'] for r in chapter_results),
        'chapters': chapter_results,
        'all_chunk_files': all_chunk_files
    }
    
    novel_output_dir = output_dir / novel_name
    novel_output_dir.mkdir(parents=True, exist_ok=True)
    
    overall_metadata_file = novel_output_dir / f"{novel_name}_all_chunks.json"
    with open(overall_metadata_file, 'w', encoding='utf-8') as f:
        json.dump(overall_metadata, f, indent=2)
    
    logger.info(f"="*60)
    logger.info(f"Chunking complete: {len(chapter_results)} chapters, {overall_metadata['total_chunks']} total chunks")
    logger.info(f"="*60)
    
    return {
        'success': True,
        'novel_name': novel_name,
        'total_chapters': len(chapter_results),
        'total_chunks': overall_metadata['total_chunks'],
        'output_dir': str(novel_output_dir),
        'chunk_files': all_chunk_files,
        'metadata_file': str(overall_metadata_file),
        'chapter_results': chapter_results
    }


def main():
    """Command line entry point."""
    if len(sys.argv) < 3:
        print("Usage: python chunk_paragraph.py <input_file_or_dir> <output_dir>")
        print("Example: python chunk_paragraph.py chinese_chapters/古道仙鸿 working_data/chunks/")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    
    config = load_config()
    max_chunk_size = config.get('chunk_size', 1500)
    
    try:
        if input_path.is_dir():
            result = chunk_novel_chapters(input_path, output_dir, max_chunk_size)
        else:
            result = chunk_text_file(input_path, output_dir, max_chunk_size)
        
        if result['success']:
            print(f"✓ Created {result['total_chunks']} chunks")
            sys.exit(0)
        else:
            print(f"✗ Chunking failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ Chunking failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
