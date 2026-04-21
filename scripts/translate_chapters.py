#!/usr/bin/env python3
"""
Phase 2: Translate Chinese chapter .md files to Burmese one by one

This script:
1. Reads chinese_chapters/<novel>/chapter_XXX.md files
2. Translates one chapter at a time using Ollama
3. Saves translated chapter as burmese_chapters/<novel>/chapter_XXX.md
4. Continues to next chapter after each completion

Usage:
    python scripts/translate_chapters.py <novel_name>
    python scripts/translate_chapters.py simple_data
"""

import os
import sys
import json
import time
import logging
import signal
from pathlib import Path
from datetime import datetime

# Add project root to path so we can import modules
# This allows 'from scripts.translator import ...' to work when run from root
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import our modules
from scripts.translator import get_translator, get_system_prompt
from scripts.assembler import assemble
from scripts.chunker import auto_chunk
from scripts.glossary_manager import GlossaryManager

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
    file_handler = logging.FileHandler(LOG_DIR / "translate_chapters.log", encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle Ctrl+C for graceful shutdown."""
    global shutdown_requested
    if not shutdown_requested:
        logger.info("=" * 60)
        logger.info("Shutdown requested (Ctrl+C). Saving progress...")
        logger.info("=" * 60)
        shutdown_requested = True
    else:
        sys.exit(1)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def load_config():
    """Load configuration from config.json."""
    try:
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    
    return {
        'model': 'qwen:7b',
        'provider': 'ollama',
        'ai_backend': 'ollama',
        'request_timeout': 900,
        'myanmar_readability': {
            'min_myanmar_ratio': 0.7
        }
    }

def save_checkpoint(novel_name, chapter_num, status):
    """Save progress checkpoint."""
    checkpoint_dir = Path("working_data/checkpoints")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    checkpoint_file = checkpoint_dir / f"{novel_name}_translation.json"
    
    checkpoint_data = {
        'novel_name': novel_name,
        'current_chapter': chapter_num,
        'status': status,
        'last_updated': datetime.now().isoformat()
    }
    
    with open(checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(checkpoint_data, f, indent=2)
    
    logger.info(f"Checkpoint saved: Chapter {chapter_num} - {status}")

def load_checkpoint(novel_name):
    """Load progress checkpoint."""
    checkpoint_file = Path("working_data/checkpoints") / f"{novel_name}_translation.json"
    
    if checkpoint_file.exists():
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    return None

def translate_chapter(novel_name, chapter_num, input_file, output_dir, config):
    """
    Translate a single chapter using the shared translator and assembler.
    Uses per-novel glossary for character name consistency.
    """
    try:
        input_path = Path(input_file)
        if not input_path.exists():
            logger.error(f"Chapter file not found: {input_path}")
            return False
        
        logger.info(f"=" * 60)
        logger.info(f"Translating {novel_name} - Chapter {chapter_num}")
        logger.info(f"=" * 60)
        
        # 1. Read Chinese chapter
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract content between --- if present
        parts = content.split('---')
        # If it has front matter, actual content is after the second ---
        chapter_content = parts[2].strip() if len(parts) >= 3 else content
        
        # 2. Initialize glossary manager for this novel
        glossary = GlossaryManager(novel_name)
        logger.info(f"Glossary loaded: {len(glossary.names)} names")
        
        # 3. Get translator with novel-specific glossary
        model_name = config.get('ai_backend', os.getenv('AI_MODEL', 'ollama'))
        translator = get_translator(model_name)
        system_prompt = get_system_prompt(glossary_manager=glossary)
        
        # 3. Translate with chunking and rolling context
        chunks = auto_chunk(chapter_content, max_chars=1200, overlap_chars=0)
        
        translated_chunks = []
        previous_translation = None
        is_nllb = "nllb" in translator.name.lower()
        
        for i, chunk in enumerate(chunks, 1):
            if shutdown_requested:
                logger.info("Shutdown requested mid-chapter...")
                return False
                
            logger.info(f"Translating chunk {i}/{len(chunks)}")
            
            # Build contextualized prompt for LLM-based models
            user_content = f"CHAPTER {chapter_num}\n\n"
            if previous_translation and i > 1 and not is_nllb:
                # Rolling Context: provide previous translation snippet for consistency
                context_snippet = previous_translation[-1200:] if len(previous_translation) > 1200 else previous_translation
                user_content += f"PREVIOUS CONTEXT (for consistency):\n{context_snippet}\n\n---\n\n"
            
            user_content += f"CURRENT TEXT TO TRANSLATE:\n{chunk}"
            
            # Translate this chunk
            result = translator.translate(user_content, system_prompt)
            
            # Save for final assembly and for next chunk context
            translated_chunks.append(result)
            previous_translation = result
            
            # Apply delay between chunks (Skip for local Ollama)
            if "ollama" not in translator.name.lower() and i < len(chunks):
                delay = float(os.getenv("REQUEST_DELAY", "0.5"))
                if delay > 0:
                    time.sleep(delay)
            
        translated = '\n\n'.join(translated_chunks)
        
        # 4. Assemble to books/ structure
        book_id = novel_name
        output_book_dir = Path("books") / book_id
        chapters_dir = output_book_dir / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = chapters_dir / f"chapter_{chapter_num:03d}.md"
        
        assemble(
            original_title=f"Chapter {chapter_num}",
            chapter_number=chapter_num, # Fixed: was chapter_number
            model_name=translator.name,
            translated_content=translated,
            output_path=str(output_file),
            book_id=book_id
        )
        
        # 5. Update glossary with potential new names from this chapter
        logger.info("Updating glossary with new names from this chapter...")
        new_mappings = glossary.update_from_translation(chapter_content, translated, chapter_num)
        if new_mappings:
            logger.info(f"Found {len(new_mappings)} potential new names to review")
        glossary.metadata["chapter_count"] = max(glossary.metadata.get("chapter_count", 0), chapter_num)
        glossary.save()
        logger.info(f"Glossary saved: {len(glossary.names)} total names")
        
        # Save checkpoint
        save_checkpoint(novel_name, chapter_num, 'completed')
        
        return True
        
    except Exception as e:
        logger.error(f"Error translating chapter {chapter_num}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def translate_novel_chapters(novel_name, chinese_dir="chinese_chapters", output_dir="burmese_chapters"):
    """
    Translate all chapters of a novel one by one.
    """
    try:
        config = load_config()
        
        # Determine source directory (some scripts use english_chapters, some chinese_chapters)
        src_dir = Path(chinese_dir) / novel_name
        if not src_dir.exists():
            # Fallback to english_chapters
            src_dir = Path("english_chapters") / novel_name
            
        if not src_dir.exists():
            logger.error(f"Source directory not found: {src_dir}")
            return {'success': False, 'error': f'Source directory for {novel_name} not found'}
        
        # Load metadata
        metadata_file = src_dir / f"{novel_name}_metadata.json"
        
        if not metadata_file.exists():
            logger.error(f"Metadata file not found: {metadata_file}")
            # Try to find all .md files if metadata is missing
            md_files = sorted(src_dir.glob("*_chapter_*.md"))
            if not md_files:
                return {'success': False, 'error': 'Metadata and chapter files not found'}
            
            chapters = []
            for f in md_files:
                # Extract chapter number from filename
                match = re.search(r'chapter_(\d+)', f.name)
                num = int(match.group(1)) if match else 1
                chapters.append({
                    'chapter_number': num,
                    'file': str(f)
                })
            total_chapters = len(chapters)
        else:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            total_chapters = metadata.get('total_chapters', len(metadata.get('chapters', [])))
            chapters = metadata['chapters']
        
        logger.info(f"=" * 60)
        logger.info(f"Starting translation: {novel_name}")
        logger.info(f"Source: {src_dir}")
        logger.info(f"Total chapters: {total_chapters}")
        logger.info(f"=" * 60)
        
        # Load checkpoint to resume
        checkpoint = load_checkpoint(novel_name)
        start_chapter = 1
        
        if checkpoint:
            start_chapter = checkpoint.get('current_chapter', 0) + 1
            logger.info(f"Resuming from Chapter {start_chapter}")
        
        # Translate each chapter
        completed = 0
        failed = 0
        
        for chapter_info in chapters:
            if shutdown_requested:
                logger.info("Shutdown requested, stopping...")
                break
            
            chapter_num = chapter_info['chapter_number']
            
            # Skip already completed chapters
            if chapter_num < start_chapter:
                completed += 1
                continue
            
            input_file = chapter_info['file']
            
            # Translate this chapter
            success = translate_chapter(
                novel_name, chapter_num, input_file, output_dir, config
            )
            
            if success:
                completed += 1
                logger.info(f"✓ Chapter {chapter_num}/{total_chapters} complete")
            else:
                failed += 1
                logger.error(f"✗ Chapter {chapter_num}/{total_chapters} failed")
            
            # Progress summary
            logger.info(f"Progress: {completed}/{total_chapters} chapters done")
        
        return {
            'success': True,
            'novel_name': novel_name,
            'total_chapters': total_chapters,
            'completed': completed,
            'failed': failed,
            'output_dir': "books/" + novel_name
        }
        
    except Exception as e:
        logger.error(f"Error in translate_novel_chapters: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}

import re

def main():
    """Command line entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/translate_chapters.py <novel_name>")
        sys.exit(1)
    
    novel_name = sys.argv[1]
    
    result = translate_novel_chapters(novel_name)
    
    if result['success']:
        print(f"\n✓ Translation complete: {result['completed']}/{result['total_chapters']} chapters")
        print(f"Output: {result['output_dir']}")
        sys.exit(0)
    else:
        print(f"\n✗ Translation failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
