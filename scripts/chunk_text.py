#!/usr/bin/env python3
"""
Chunk Chinese novel text into overlapping segments for translation.

This script splits cleaned text into chunks of 1000-2000 characters
with configurable overlap to preserve narrative continuity.

Usage:
    python scripts/chunk_text.py <input_file> <output_dir>
    python scripts/chunk_text.py working_data/clean/my_novel_clean.txt working_data/chunks/my_novel/
"""

import os
import sys
import re
import json
import logging
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
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise


def find_sentence_boundary(text, target_pos, max_search=200):
    """
    Find the nearest sentence boundary near the target position.
    Search backwards for punctuation marks that typically end sentences.
    """
    try:
        # Chinese sentence-ending punctuation
        sentence_endings = r'[。！？；\.!?;]'
        
        # Search backwards from target position
        search_start = max(0, target_pos - max_search)
        search_text = text[search_start:target_pos]
        
        # Find the rightmost sentence ending
        matches = list(re.finditer(sentence_endings, search_text))
        
        if matches:
            # Return position after the last sentence ending
            last_match = matches[-1]
            return search_start + last_match.end()
        
        # If no sentence boundary found, return target position
        return target_pos
        
    except Exception as e:
        logger.error(f"Error finding sentence boundary: {e}")
        return target_pos


def detect_chapters(text):
    """
    Detect chapter boundaries in Chinese novel text.
    Pattern: 第XXX章 (e.g., 第001章, 第002章)
    
    Returns:
        List of dictionaries with chapter info:
        [{'number': 1, 'title': '神仙群殴', 'start_pos': 100, 'end_pos': 5000}, ...]
    """
    try:
        # Pattern to match chapter headers: 第XXX章 [title]
        # Examples: 第001章 神仙群殴, 第002章 蟠龙山
        chapter_pattern = r'^第(\d+)章\s*(.*?)$'
        
        chapters = []
        lines = text.split('\n')
        current_chapter = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            match = re.match(chapter_pattern, line)
            
            if match:
                # Found a new chapter
                chapter_num = int(match.group(1))
                chapter_title = match.group(2).strip()
                
                # Calculate position in text
                pos = sum(len(lines[j]) + 1 for j in range(i))  # +1 for newline
                
                # If we had a previous chapter, set its end position
                if current_chapter:
                    current_chapter['end_pos'] = pos
                    chapters.append(current_chapter)
                
                # Start new chapter
                current_chapter = {
                    'number': chapter_num,
                    'title': chapter_title,
                    'start_pos': pos,
                    'end_pos': None  # Will be set when next chapter found or at end
                }
                logger.info(f"Detected Chapter {chapter_num}: {chapter_title}")
        
        # Don't forget the last chapter
        if current_chapter:
            current_chapter['end_pos'] = len(text)
            chapters.append(current_chapter)
        
        logger.info(f"Total chapters detected: {len(chapters)}")
        return chapters
        
    except Exception as e:
        logger.error(f"Error detecting chapters: {e}")
        return []


def extract_chapter_text(text, chapter):
    """Extract text for a specific chapter."""
    start = chapter['start_pos']
    end = chapter['end_pos']
    if end is None:
        end = len(text)
    return text[start:end].strip()


def split_text_by_chapters(text):
    """
    Split text into chapters.
    
    Returns:
        List of (chapter_info, chapter_text) tuples
    """
    chapters = detect_chapters(text)
    
    if not chapters:
        logger.warning("No chapters detected, treating entire text as one chapter")
        # Treat entire text as chapter 1
        chapters = [{
            'number': 1,
            'title': 'Chapter 1',
            'start_pos': 0,
            'end_pos': len(text)
        }]
    
    result = []
    for chapter in chapters:
        chapter_text = extract_chapter_text(text, chapter)
        if chapter_text:
            result.append((chapter, chapter_text))
    
    return result


def split_into_chunks(text, chunk_size, chunk_overlap):
    """
    Split text into overlapping chunks.
    
    Args:
        text: The text to split
        chunk_size: Target size of each chunk in characters
        chunk_overlap: Number of characters to overlap between chunks
    
    Returns:
        List of chunk strings
    """
    try:
        chunks = []
        start = 0
        text_length = len(text)
        
        logger.info(f"Starting chunking: text length={text_length}, chunk_size={chunk_size}, overlap={chunk_overlap}")
        
        while start < text_length:
            # Calculate end position
            end = min(start + chunk_size, text_length)
            
            # If not at the end of text, find a sentence boundary
            if end < text_length:
                end = find_sentence_boundary(text, end)
            
            # Extract chunk
            chunk = text[start:end].strip()
            
            # Only add non-empty chunks
            if chunk:
                chunks.append(chunk)
                logger.debug(f"Created chunk {len(chunks)}: positions {start}-{end} ({len(chunk)} chars)")
            
            # Move start position, accounting for overlap
            next_start = end - chunk_overlap
            
            # Ensure we're making progress (prevent infinite loop on very short text)
            if next_start <= start:
                next_start = end
            
            start = next_start
            
            # Safety check: if we're near the end, just finish
            if start >= text_length - 50:  # Less than 50 chars remaining
                break
        
        logger.info(f"Created {len(chunks)} chunks from {text_length} characters")
        return chunks
        
    except Exception as e:
        logger.error(f"Error splitting text into chunks: {e}")
        raise


def save_chunks(chunks, output_dir, novel_name):
    """
    Save chunks as individual files.
    
    Args:
        chunks: List of chunk strings
        output_dir: Directory to save chunks
        novel_name: Name of the novel (used for filenames)
    """
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        
        for i, chunk in enumerate(chunks, 1):
            chunk_file = output_path / f"{novel_name}_chunk_{i:05d}.txt"
            
            try:
                with open(chunk_file, 'w', encoding='utf-8') as f:
                    f.write(chunk)
                saved_files.append(str(chunk_file))
                logger.debug(f"Saved chunk {i} to {chunk_file}")
            except Exception as e:
                logger.error(f"Error saving chunk {i}: {e}")
                raise
        
        # Save chunk metadata
        metadata = {
            'novel_name': novel_name,
            'total_chunks': len(chunks),
            'chunk_files': saved_files,
            'chunk_size_config': len(chunks[0]) if chunks else 0
        }
        
        metadata_file = output_path / f"{novel_name}_chunks.json"
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving chunk metadata: {e}")
            # Non-fatal, continue
        
        logger.info(f"Saved {len(saved_files)} chunks to {output_path}")
        return saved_files
        
    except Exception as e:
        logger.error(f"Error saving chunks: {e}")
        raise


def chunk_chapter(chapter, chapter_text, output_dir, novel_name, chunk_size, chunk_overlap):
    """
    Chunk a single chapter into smaller pieces.
    
    Returns:
        Dictionary with chapter chunking results
    """
    try:
        chapter_num = chapter['number']
        chapter_title = chapter['title']
        
        # Create chapter-specific output directory
        chapter_dir = Path(output_dir) / f"chapter_{chapter_num:03d}"
        chapter_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Processing Chapter {chapter_num}: {chapter_title}")
        logger.info(f"  Chapter text length: {len(chapter_text)} characters")
        
        # Split chapter into chunks
        chunks = split_into_chunks(chapter_text, chunk_size, chunk_overlap)
        
        if not chunks:
            logger.warning(f"  No chunks created for chapter {chapter_num}")
            return None
        
        # Save chunks
        saved_files = []
        for i, chunk in enumerate(chunks, 1):
            chunk_file = chapter_dir / f"{novel_name}_ch{chapter_num:03d}_chunk_{i:05d}.txt"
            try:
                with open(chunk_file, 'w', encoding='utf-8') as f:
                    f.write(chunk)
                saved_files.append(str(chunk_file))
                logger.debug(f"  Saved chunk {i} to {chunk_file}")
            except Exception as e:
                logger.error(f"  Error saving chunk {i}: {e}")
                raise
        
        # Save chapter metadata
        metadata = {
            'novel_name': novel_name,
            'chapter_number': chapter_num,
            'chapter_title': chapter_title,
            'total_chunks': len(chunks),
            'chunk_files': saved_files,
            'chapter_chars': len(chapter_text)
        }
        
        metadata_file = chapter_dir / f"chapter_{chapter_num:03d}_meta.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        logger.info(f"  Chapter {chapter_num}: {len(chunks)} chunks saved")
        
        return {
            'chapter_number': chapter_num,
            'chapter_title': chapter_title,
            'chapter_dir': str(chapter_dir),
            'total_chunks': len(chunks),
            'chunk_files': saved_files,
            'metadata_file': str(metadata_file)
        }
        
    except Exception as e:
        logger.error(f"Error chunking chapter {chapter['number']}: {e}")
        raise


def chunk_text(input_file, output_dir, chunk_size=None, chunk_overlap=None, chapter_based=True):
    """
    Main chunking function.
    
    Args:
        input_file: Path to cleaned text file
        output_dir: Directory to save chunk files
        chunk_size: Chunk size (uses config if None)
        chunk_overlap: Overlap size (uses config if None)
        chapter_based: If True, split by chapters first, then chunk each chapter
    
    Returns:
        Dictionary with chunking results
    """
    try:
        input_path = Path(input_file)
        
        # Load config for defaults
        config = load_config()
        
        if chunk_size is None:
            chunk_size = config.get('chunk_size', 1500)
        if chunk_overlap is None:
            chunk_overlap = config.get('chunk_overlap', 100)
        
        logger.info(f"Chunking parameters: size={chunk_size}, overlap={chunk_overlap}, chapter_based={chapter_based}")
        
        # Verify input exists
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Read input file
        logger.info(f"Reading input file: {input_path}")
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception as e:
            logger.error(f"Error reading input file: {e}")
            raise
        
        if not text.strip():
            raise ValueError("Input file is empty")
        
        # Generate novel name from filename
        novel_name = input_path.stem.replace('_clean', '')
        
        # Create output subdirectory for this novel
        novel_output_dir = Path(output_dir) / novel_name
        novel_output_dir.mkdir(parents=True, exist_ok=True)
        
        if chapter_based:
            # Split by chapters first
            logger.info("Detecting chapters...")
            chapters_data = split_text_by_chapters(text)
            
            if not chapters_data:
                logger.warning("No chapters found, falling back to regular chunking")
                chapter_based = False
            else:
                logger.info(f"Found {len(chapters_data)} chapters")
                
                # Process each chapter
                chapter_results = []
                all_chunk_files = []
                
                for chapter, chapter_text in chapters_data:
                    result = chunk_chapter(
                        chapter, chapter_text, novel_output_dir, 
                        novel_name, chunk_size, chunk_overlap
                    )
                    if result:
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
                
                metadata_file = novel_output_dir / f"{novel_name}_chapters.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(overall_metadata, f, ensure_ascii=False, indent=2)
                
                result = {
                    'success': True,
                    'novel_name': novel_name,
                    'total_chapters': len(chapter_results),
                    'total_chunks': overall_metadata['total_chunks'],
                    'output_dir': str(novel_output_dir),
                    'chapter_dirs': [r['chapter_dir'] for r in chapter_results],
                    'chunk_files': all_chunk_files,
                    'chapter_based': True,
                    'metadata_file': str(metadata_file)
                }
                
                logger.info(f"Chapter-based chunking complete:")
                logger.info(f"  - Total chapters: {result['total_chapters']}")
                logger.info(f"  - Total chunks: {result['total_chunks']}")
                logger.info(f"  - Output directory: {result['output_dir']}")
                
                return result
        
        # Regular chunking (not chapter-based)
        if not chapter_based:
            chunks = split_into_chunks(text, chunk_size, chunk_overlap)
            
            if not chunks:
                raise ValueError("No chunks were created")
            
            # Save chunks
            saved_files = save_chunks(chunks, novel_output_dir, novel_name)
            
            # Log statistics
            avg_chunk_size = sum(len(c) for c in chunks) / len(chunks)
            min_chunk_size = min(len(c) for c in chunks)
            max_chunk_size = max(len(c) for c in chunks)
            
            result = {
                'success': True,
                'novel_name': novel_name,
                'total_chunks': len(chunks),
                'output_dir': str(novel_output_dir),
                'chunk_files': saved_files,
                'chapter_based': False,
                'statistics': {
                    'avg_chunk_size': round(avg_chunk_size, 1),
                    'min_chunk_size': min_chunk_size,
                    'max_chunk_size': max_chunk_size,
                    'total_input_chars': len(text)
                }
            }
            
            logger.info(f"Regular chunking complete:")
            logger.info(f"  - Total chunks: {result['total_chunks']}")
            logger.info(f"  - Average chunk size: {result['statistics']['avg_chunk_size']} chars")
            logger.info(f"  - Output directory: {result['output_dir']}")
            
            return result
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during chunking: {e}")
        raise


def main():
    """Command line entry point."""
    if len(sys.argv) < 3:
        print("Usage: python chunk_text.py <input_file> <output_dir>")
        print("Example: python chunk_text.py working_data/clean/my_novel_clean.txt working_data/chunks/")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_dir = sys.argv[2]
    
    try:
        result = chunk_text(input_file, output_dir)
        print(f"✓ Created {result['total_chunks']} chunks")
        sys.exit(0)
    except Exception as e:
        print(f"✗ Chunking failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
