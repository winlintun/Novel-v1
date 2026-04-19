#!/usr/bin/env python3
"""
Post-process translated Burmese text chunks.

This script fixes common Myanmar punctuation issues and ensures
consistent character name translations across all chunks.

Usage:
    python scripts/postprocess_translation.py <novel_name>
    python scripts/postprocess_translation.py my_novel
"""

import os
import sys
import json
import re
import logging
from pathlib import Path
from collections import defaultdict

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
    file_handler = logging.FileHandler(LOG_DIR / "postprocess.log", encoding='utf-8')
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


# Myanmar Unicode ranges
MYANMAR_CONSONANTS = r'[\u1000-\u1021]'
MYANMAR_MEDIALS = r'[\u103B-\u103E]'
MYANMAR_VOWEL_SIGNS = r'[\u102C-\u1032\u1036-\u103A]'
MYANMAR_TONE_MARKS = r'[\u1037\u1038]'
MYANMAR_DIGITS = r'[\u1040-\u1049]'
MYANMAR_PUNCTUATION = r'[\u104A\u104B]'

# Chinese character detection pattern
CHINESE_CHAR_PATTERN = re.compile(r'[\u4E00-\u9FFF]')


def fix_punctuation(text):
    """
    Fix common Myanmar punctuation issues.
    
    Issues fixed:
    - Replace Latin punctuation with Myanmar equivalents
    - Fix spacing around punctuation
    - Normalize paragraph breaks
    """
    try:
        original = text
        
        # Replace Latin punctuation with Myanmar equivalents
        replacements = [
            (r'\.', '။'),      # Period -> Myanmar sentence ender
            (r'\?', '၊'),      # Question mark -> Myanmar clause ender
            (r'!', '။'),       # Exclamation -> Myanmar sentence ender  
            (r',', '၊'),       # Comma -> Myanmar clause ender
            (r';', '၊'),       # Semicolon -> Myanmar clause ender
            (r'"', '"'),      # Double quote left
            (r'"', '"'),      # Double quote right
            (r'"', '"'),      # Straight double quote
            (r"'", "'"),      # Single quote left
            (r"'", "'"),      # Single quote right
            (r"'", "'"),      # Straight single quote
            (r'\(', ''),      # Parentheses -> Myanmar
            (r'\)', ''),      # Parentheses -> Myanmar
        ]
        
        for pattern, replacement in replacements:
            try:
                text = re.sub(pattern, replacement, text)
            except Exception as e:
                logger.error(f"Error applying punctuation replacement {pattern}: {e}")
        
        # Fix spacing: ensure space after sentence ender (if followed by Myanmar char)
        text = re.sub(r'။([^\s\n])', r'။ \1', text)
        
        # Normalize multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        
        # Normalize paragraph breaks (max 2 newlines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        changes = len(original) - len(text)
        if changes != 0:
            logger.debug(f"Punctuation fixes applied: {abs(changes)} character changes")
        
        return text
        
    except Exception as e:
        logger.error(f"Error fixing punctuation: {e}")
        return text


def remove_residual_chinese(text):
    """Remove any Chinese characters that may have slipped through."""
    try:
        original_length = len(text)
        
        # Find all Chinese characters
        chinese_chars = CHINESE_CHAR_PATTERN.findall(text)
        
        if chinese_chars:
            logger.warning(f"Found {len(chinese_chars)} residual Chinese characters: {set(chinese_chars)}")
            
            # Remove Chinese characters
            text = CHINESE_CHAR_PATTERN.sub('', text)
            
            # Clean up resulting double spaces
            text = re.sub(r' {2,}', ' ', text)
            
            removed = original_length - len(text)
            logger.info(f"Removed {removed} residual Chinese characters")
        
        return text
        
    except Exception as e:
        logger.error(f"Error removing residual Chinese: {e}")
        return text


def normalize_paragraph_spacing(text):
    """Ensure consistent paragraph spacing."""
    try:
        # Remove trailing whitespace from lines
        text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
        
        # Ensure single blank line between paragraphs
        lines = text.split('\n')
        result = []
        prev_empty = False
        
        for line in lines:
            stripped = line.strip()
            
            if stripped:
                result.append(line)
                prev_empty = False
            else:
                if not prev_empty:
                    result.append('')  # Keep one empty line
                prev_empty = True
        
        return '\n'.join(result)
        
    except Exception as e:
        logger.error(f"Error normalizing paragraph spacing: {e}")
        return text


def postprocess_chunk(text, chunk_name=None):
    """
    Apply all post-processing steps to a text chunk.
    
    Args:
        text: The translated Burmese text
        chunk_name: Optional name for logging
        
    Returns:
        Post-processed text
    """
    try:
        if chunk_name:
            logger.info(f"Post-processing chunk: {chunk_name}")
        
        original_length = len(text)
        
        # Step 1: Fix punctuation
        text = fix_punctuation(text)
        
        # Step 2: Remove residual Chinese characters
        text = remove_residual_chinese(text)
        
        # Step 3: Normalize paragraph spacing
        text = normalize_paragraph_spacing(text)
        
        final_length = len(text)
        change = original_length - final_length
        
        if chunk_name:
            if change != 0:
                logger.info(f"Post-processing complete: {abs(change)} characters {'removed' if change > 0 else 'added'}")
            else:
                logger.info(f"Post-processing complete: no length change")
        
        return text
        
    except Exception as e:
        logger.error(f"Error during post-processing: {e}")
        return text


def postprocess_novel(novel_name, translated_dir=None, output_dir=None):
    """
    Post-process all translated chunks for a novel.
    
    Args:
        novel_name: Name of the novel
        translated_dir: Directory containing translated chunks
        output_dir: Directory to save post-processed chunks
        
    Returns:
        Dictionary with processing results
    """
    try:
        if translated_dir is None:
            translated_dir = Path("working_data/translated_chunks") / novel_name
        else:
            translated_dir = Path(translated_dir)
        
        if output_dir is None:
            output_dir = Path("working_data/translated_chunks") / novel_name
        else:
            output_dir = Path(output_dir)
        
        logger.info(f"Post-processing novel: {novel_name}")
        logger.info(f"Input directory: {translated_dir}")
        
        # Find all translated chunks
        try:
            chunk_files = sorted(translated_dir.glob(f"{novel_name}_chunk_*.txt"))
        except Exception as e:
            logger.error(f"Error finding chunk files: {e}")
            raise
        
        if not chunk_files:
            raise FileNotFoundError(f"No translated chunks found for {novel_name}")
        
        logger.info(f"Found {len(chunk_files)} chunks to post-process")
        
        processed_count = 0
        errors = []
        
        for chunk_file in chunk_files:
            try:
                # Read translated chunk
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                # Post-process
                processed_text = postprocess_chunk(text, chunk_file.name)
                
                # Write back (overwrite with post-processed version)
                output_file = output_dir / chunk_file.name
                output_dir.mkdir(parents=True, exist_ok=True)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(processed_text)
                
                processed_count += 1
                logger.info(f"Post-processed chunk {processed_count}/{len(chunk_files)}: {chunk_file.name}")
                
            except Exception as e:
                error_msg = f"Error processing {chunk_file.name}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        result = {
            'success': len(errors) == 0,
            'novel_name': novel_name,
            'total_chunks': len(chunk_files),
            'processed': processed_count,
            'errors': errors
        }
        
        logger.info(f"Post-processing complete: {processed_count}/{len(chunk_files)} chunks processed")
        
        if errors:
            logger.warning(f"Encountered {len(errors)} errors during post-processing")
        
        return result
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error post-processing novel: {e}")
        raise


def main():
    """Command line entry point."""
    if len(sys.argv) < 2:
        print("Usage: python postprocess_translation.py <novel_name>")
        print("Example: python postprocess_translation.py my_novel")
        sys.exit(1)
    
    novel_name = sys.argv[1]
    
    try:
        result = postprocess_novel(novel_name)
        
        if result['success']:
            print(f"✓ Post-processing complete: {result['processed']}/{result['total_chunks']} chunks")
            sys.exit(0)
        else:
            print(f"⚠ Post-processing completed with {len(result['errors'])} errors")
            for error in result['errors'][:3]:  # Show first 3 errors
                print(f"  - {error}")
            sys.exit(1)
            
    except Exception as e:
        print(f"✗ Post-processing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
