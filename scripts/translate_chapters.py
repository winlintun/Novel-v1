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
from datetime import datetime, timedelta

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
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {
            'model': 'qwen:7b',
            'request_timeout': 900,
            'myanmar_readability': {
                'min_myanmar_ratio': 0.7
            }
        }


def translate_text_with_ollama(text, config, max_retries=3):
    """
    Translate Chinese text to Burmese using Ollama.
    
    Args:
        text: Chinese text to translate
        config: Configuration dict
        max_retries: Number of retry attempts
    
    Returns:
        Tuple of (translated_text, success_boolean)
    """
    try:
        import ollama
        
        model = config.get('model', 'qwen:7b')
        
        # Build the prompt - STRICT instructions for Burmese output only
        system_prompt = """You are a professional literary translator.
CRITICAL INSTRUCTIONS:
1. Translate Chinese text to Burmese (Myanmar script) ONLY
2. Output ONLY Burmese characters (Unicode U+1000-U+109F)
3. NO English words
4. NO Chinese characters (U+4E00-U+9FFF)
5. NO explanations, notes, or commentary
6. NO romanization or transliteration
7. Use Myanmar sentence ending marker (။) at end of sentences
8. Maintain literary style and flow

Failure to follow these instructions will result in rejected output."""
        
        user_prompt = f"Translate this Chinese chapter to Burmese:\n\n{text}"
        
        logger.info(f"Calling Ollama model: {model}")
        logger.info(f"Input length: {len(text)} characters")
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Translation attempt {attempt}/{max_retries}")
                
                response = ollama.generate(
                    model=model,
                    system=system_prompt,
                    prompt=user_prompt,
                    stream=False,
                    options={
                        'temperature': 0.2,
                        'num_predict': -1,
                    }
                )
                
                translated = response.get('response', '').strip()
                
                if translated:
                    logger.info(f"Translation received: {len(translated)} characters")
                    return translated, True
                else:
                    logger.warning(f"Empty response on attempt {attempt}")
                    
            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
        
        return "", False
        
    except ImportError:
        logger.error("Ollama not installed. Run: pip install ollama")
        return "", False
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return "", False


def check_myanmar_quality(text, min_ratio=0.7):
    """
    Check if translated text has sufficient Myanmar characters.
    
    Returns:
        Tuple of (passed, myanmar_ratio, chinese_count)
    """
    if not text:
        return False, 0.0, 0
    
    total_chars = len(text)
    
    # Count Myanmar characters (U+1000-U+109F)
    myanmar_count = sum(1 for c in text if 0x1000 <= ord(c) <= 0x109F)
    
    # Count Chinese characters (U+4E00-U+9FFF)
    chinese_count = sum(1 for c in text if 0x4E00 <= ord(c) <= 0x9FFF)
    
    # Calculate Myanmar ratio
    myanmar_ratio = myanmar_count / total_chars if total_chars > 0 else 0
    
    # Check sentence ending markers
    sentence_markers = text.count('။')
    
    logger.info(f"Quality check:")
    logger.info(f"  - Myanmar ratio: {myanmar_ratio:.1%} (min: {min_ratio:.0%})")
    logger.info(f"  - Chinese chars: {chinese_count} (max: 0)")
    logger.info(f"  - Sentence markers: {sentence_markers}")
    
    passed = myanmar_ratio >= min_ratio and chinese_count == 0 and sentence_markers > 0
    
    return passed, myanmar_ratio, chinese_count


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
    Translate a single chapter.
    
    Args:
        novel_name: Name of the novel
        chapter_num: Chapter number
        input_file: Path to Chinese chapter .md file
        output_dir: Directory to save translated chapter
        config: Configuration dict
    
    Returns:
        Boolean indicating success
    """
    try:
        input_path = Path(input_file)
        
        if not input_path.exists():
            logger.error(f"Chapter file not found: {input_path}")
            return False
        
        logger.info(f"=" * 60)
        logger.info(f"Translating Chapter {chapter_num}")
        logger.info(f"=" * 60)
        
        # Read Chinese chapter
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract just the content (not the markdown headers)
        # Find content between --- markers
        parts = content.split('---')
        if len(parts) >= 3:
            chapter_content = parts[2].strip()
        else:
            chapter_content = content
        
        logger.info(f"Chapter content: {len(chapter_content)} characters")
        
        # Translate
        start_time = time.time()
        translated, success = translate_text_with_ollama(chapter_content, config)
        
        if not success or not translated:
            logger.error(f"Translation failed for Chapter {chapter_num}")
            return False
        
        elapsed = time.time() - start_time
        logger.info(f"Translation completed in {elapsed:.1f}s")
        
        # Check quality
        min_ratio = config.get('myanmar_readability', {}).get('min_myanmar_ratio', 0.7)
        passed, ratio, chinese_count = check_myanmar_quality(translated, min_ratio)
        
        if not passed:
            logger.warning(f"Quality check FAILED for Chapter {chapter_num}")
            logger.warning(f"  Myanmar ratio: {ratio:.1%}, Chinese chars: {chinese_count}")
            # Continue anyway but log the issue
        else:
            logger.info(f"✓ Quality check PASSED")
        
        # Create output directory
        output_path = Path(output_dir) / novel_name
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save translated chapter
        output_file = output_path / f"{novel_name}_chapter_{chapter_num:03d}.md"
        
        # Convert chapter number to Burmese
        burmese_digits = '၀၁၂၃၄၅၆၇၈၉'
        burmese_chapter_num = ''.join(burmese_digits[int(d)] for d in str(chapter_num))
        
        md_content = f"""# {novel_name} - အခန်း {burmese_chapter_num}

---

{translated}

---
*ဤအခန်းကို OpenCode AI Chinese-to-Burmese Translator ဖြင့် ဘာသာပြန်ဆိုခဲ့သည်။*
*Translated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"✓ Saved translated chapter: {output_file}")
        
        # Save checkpoint
        save_checkpoint(novel_name, chapter_num, 'completed')
        
        return True
        
    except Exception as e:
        logger.error(f"Error translating chapter {chapter_num}: {e}")
        return False


def translate_novel_chapters(novel_name, chinese_dir="chinese_chapters", output_dir="burmese_chapters"):
    """
    Translate all chapters of a novel one by one.
    
    Args:
        novel_name: Name of the novel
        chinese_dir: Directory containing Chinese chapter .md files
        output_dir: Directory to save translated chapters
    
    Returns:
        Dictionary with translation results
    """
    try:
        config = load_config()
        
        # Load metadata
        metadata_file = Path(chinese_dir) / novel_name / f"{novel_name}_metadata.json"
        
        if not metadata_file.exists():
            logger.error(f"Metadata file not found: {metadata_file}")
            return {'success': False, 'error': 'Metadata not found'}
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        total_chapters = metadata['total_chapters']
        chapters = metadata['chapters']
        
        logger.info(f"=" * 60)
        logger.info(f"Starting translation: {novel_name}")
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
                logger.info(f"Chapter {chapter_num} already done, skipping")
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
                # Continue with next chapter
            
            # Progress summary
            logger.info(f"Progress: {completed}/{total_chapters} chapters done")
        
        # Final summary
        logger.info(f"=" * 60)
        logger.info(f"Translation complete: {novel_name}")
        logger.info(f"  - Completed: {completed}")
        logger.info(f"  - Failed: {failed}")
        logger.info(f"  - Total: {total_chapters}")
        logger.info(f"=" * 60)
        
        return {
            'success': True,
            'novel_name': novel_name,
            'total_chapters': total_chapters,
            'completed': completed,
            'failed': failed,
            'output_dir': str(Path(output_dir) / novel_name)
        }
        
    except Exception as e:
        logger.error(f"Error in translate_novel_chapters: {e}")
        return {'success': False, 'error': str(e)}


def main():
    """Command line entry point."""
    if len(sys.argv) < 2:
        print("Usage: python translate_chapters.py <novel_name>")
        print("Example: python translate_chapters.py simple_data")
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
