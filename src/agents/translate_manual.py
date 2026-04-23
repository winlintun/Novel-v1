#!/usr/bin/env python3
"""
Manual Chapter Translation - User controls each chapter translation

Usage:
    # Check status (shows which chapters are ready/pending/done)
    python translate_manual.py <novel_name> --status
    
    # Translate specific chapter
    python translate_manual.py <novel_name> --chapter 1
    
    # Translate next pending chapter
    python translate_manual.py <novel_name> --next
    
    # List all chapters
    python translate_manual.py <novel_name> --list

Examples:
    python translate_manual.py simple_data --status
    python translate_manual.py simple_data --chapter 1
    python translate_manual.py simple_data --next
"""

import os
import sys
import json
import time
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
    file_handler = logging.FileHandler(LOG_DIR / "translate_manual.log", encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def load_config():
    """Load configuration from config.json."""
    try:
        config_path = Path("config/config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {'model': 'qwen:7b'}


def get_chapter_status(novel_name, chinese_dir="chinese_chapters", output_dir="burmese_chapters"):
    """
    Get status of all chapters for a novel.
    
    Returns:
        Dictionary with chapter status info
    """
    try:
        # Load metadata
        metadata_file = Path(chinese_dir) / novel_name / f"{novel_name}_metadata.json"
        
        if not metadata_file.exists():
            return {'error': f'No chapters found for {novel_name}. Run: python scripts/extract_chapters.py {novel_name}'}
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        chapters = metadata['chapters']
        total = len(chapters)
        
        # Check which chapters are translated
        status_list = []
        completed = 0
        pending = 0
        
        for ch in chapters:
            ch_num = ch['chapter_number']
            ch_title = ch['chapter_title']
            chinese_file = ch['file']
            
            # Check if translated
            burmese_file = Path(output_dir) / novel_name / f"{novel_name}_chapter_{ch_num:03d}.md"
            is_done = burmese_file.exists()
            
            if is_done:
                completed += 1
                status = '✓ DONE'
            else:
                pending += 1
                status = '○ PENDING'
            
            status_list.append({
                'number': ch_num,
                'chapter_title': ch_title,
                'chinese_file': chinese_file,
                'burmese_file': str(burmese_file) if is_done else None,
                'status': status,
                'done': is_done
            })
        
        return {
            'novel_name': novel_name,
            'total_chapters': total,
            'completed': completed,
            'pending': pending,
            'chapters': status_list
        }
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {'error': str(e)}


def print_status(status_info):
    """Print chapter status in a nice format."""
    if 'error' in status_info:
        print(f"\n✗ {status_info['error']}")
        return
    
    print(f"\n{'='*60}")
    print(f"Novel: {status_info['novel_name']}")
    print(f"Progress: {status_info['completed']}/{status_info['total_chapters']} chapters")
    print(f"{'='*60}")
    print(f"\n{'Chapter':<10} {'Status':<12} {'Title'}")
    print(f"{'-'*60}")
    
    for ch in status_info['chapters']:
        print(f"{ch['number']:<10} {ch['status']:<12} {ch['chapter_title']}")
    
    print(f"{'='*60}\n")
    
    # Show next chapter to translate
    pending = [ch for ch in status_info['chapters'] if not ch['done']]
    if pending:
        next_ch = pending[0]
        print(f"Next chapter to translate: Chapter {next_ch['number']} - {next_ch['chapter_title']}")
        print(f"Command: python translate_manual.py {status_info['novel_name']} --chapter {next_ch['number']}")
    else:
        print("✓ All chapters translated!")
    print()


def translate_single_chapter(novel_name, chapter_num, config):
    """
    Translate a single chapter manually.
    
    Returns:
        Boolean indicating success
    """
    try:
        import ollama
        
        # Paths
        chinese_dir = Path("chinese_chapters") / novel_name
        output_dir = Path("burmese_chapters") / novel_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load metadata
        metadata_file = chinese_dir / f"{novel_name}_metadata.json"
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Find this chapter
        chapter_info = None
        for ch in metadata['chapters']:
            if ch['chapter_number'] == chapter_num:
                chapter_info = ch
                break
        
        if not chapter_info:
            logger.error(f"Chapter {chapter_num} not found")
            return False
        
        chapter_title = chapter_info['chapter_title']
        chinese_file = chapter_info['file']
        
        # Check if already translated
        output_file = output_dir / f"{novel_name}_chapter_{chapter_num:03d}.md"
        if output_file.exists():
            print(f"\n⚠ Chapter {chapter_num} is already translated!")
            print(f"File: {output_file}")
            response = input("Overwrite? (y/n): ")
            if response.lower() != 'y':
                print("Skipping.")
                return False
        
        # Read Chinese chapter
        print(f"\n{'='*60}")
        print(f"Translating Chapter {chapter_num}: {chapter_title}")
        print(f"{'='*60}")
        
        with open(chinese_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract content between --- markers
        parts = content.split('---')
        if len(parts) >= 3:
            chapter_content = parts[2].strip()
        else:
            chapter_content = content
        
        print(f"Chapter length: {len(chapter_content)} characters")
        print(f"Model: {config.get('model', 'qwen:7b')}")
        print(f"\nStarting translation... (this may take a few minutes)\n")
        
        # Translation prompt - STRICT Burmese only
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

Output ONLY the Burmese translation. No headers, no metadata, no source text."""
        
        # Call Ollama
        start_time = time.time()
        
        try:
            response = ollama.generate(
                model=config.get('model', 'qwen:7b'),
                system=system_prompt,
                prompt=f"Translate this Chinese chapter to Burmese:\n\n{chapter_content}",
                stream=False,
                options={
                    'temperature': 0.2,
                    'num_predict': -1,
                }
            )
            
            translated = response.get('response', '').strip()
            
            if not translated:
                logger.error("Empty translation received")
                return False
            
            elapsed = time.time() - start_time
            print(f"✓ Translation received: {len(translated)} characters")
            print(f"  Time: {elapsed:.1f} seconds")
            
            # Quality check
            myanmar_count = sum(1 for c in translated if 0x1000 <= ord(c) <= 0x109F)
            chinese_count = sum(1 for c in translated if 0x4E00 <= ord(c) <= 0x9FFF)
            myanmar_ratio = myanmar_count / len(translated) if translated else 0
            
            print(f"\nQuality Check:")
            print(f"  - Myanmar chars: {myanmar_count} ({myanmar_ratio:.1%})")
            print(f"  - Chinese chars: {chinese_count}")
            print(f"  - Sentence markers: {translated.count('။')}")
            
            if myanmar_ratio < 0.7 or chinese_count > 0:
                print(f"\n⚠ WARNING: Translation may have quality issues!")
                print(f"  Myanmar ratio should be ≥70%, Chinese chars should be 0")
            else:
                print(f"\n✓ Quality check passed")
            
            # Convert chapter number to Burmese
            burmese_digits = '၀၁၂၃၄၅၆၇၈၉'
            burmese_chapter_num = ''.join(burmese_digits[int(d)] for d in str(chapter_num))
            
            # Create markdown output
            md_content = f"""# {novel_name} - အခန်း {burmese_chapter_num}

---

{translated}

---
*ဤအခန်းကို OpenCode AI Chinese-to-Burmese Translator ဖြင့် ဘာသာပြန်ဆိုခဲ့သည်။*
*Translated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*Source: {novel_name} 第{chapter_num:03d}章 {chapter_title}*
"""
            
            # Save file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            print(f"\n✓ Saved: {output_file}")
            print(f"{'='*60}\n")
            
            # Show next chapter
            status = get_chapter_status(novel_name)
            pending = [ch for ch in status['chapters'] if not ch['done']]
            if pending:
                next_ch = pending[0]
                print(f"Next: Chapter {next_ch['number']} - {next_ch['chapter_title']}")
                print(f"Run: python translate_manual.py {novel_name} --chapter {next_ch['number']}")
            else:
                print("🎉 ALL CHAPTERS COMPLETE!")
            print()
            
            return True
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            print(f"\n✗ Translation failed: {e}")
            return False
            
    except ImportError:
        print("\n✗ Error: Ollama not installed. Run: pip install ollama")
        return False
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"\n✗ Error: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python translate_manual.py <novel_name> [options]")
        print("")
        print("Options:")
        print("  --status      Show chapter translation status")
        print("  --list        List all chapters")
        print("  --chapter N   Translate specific chapter number N")
        print("  --next        Translate next pending chapter")
        print("")
        print("Examples:")
        print("  python translate_manual.py simple_data --status")
        print("  python translate_manual.py simple_data --chapter 1")
        print("  python translate_manual.py simple_data --next")
        sys.exit(1)
    
    novel_name = sys.argv[1]
    
    # Check if chapters exist
    metadata_file = Path("chinese_chapters") / novel_name / f"{novel_name}_metadata.json"
    if not metadata_file.exists():
        print(f"\n✗ Chapters not found for '{novel_name}'")
        print(f"\nFirst, extract chapters:")
        print(f"  python scripts/extract_chapters.py {novel_name}")
        sys.exit(1)
    
    # Parse command
    if len(sys.argv) >= 3:
        command = sys.argv[2]
        
        if command == '--status':
            status = get_chapter_status(novel_name)
            print_status(status)
            
        elif command == '--list':
            status = get_chapter_status(novel_name)
            print_status(status)
            
        elif command == '--chapter':
            if len(sys.argv) < 4:
                print("✗ Error: --chapter requires a chapter number")
                print("Example: python translate_manual.py simple_data --chapter 1")
                sys.exit(1)
            
            try:
                chapter_num = int(sys.argv[3])
            except ValueError:
                print(f"✗ Error: Invalid chapter number: {sys.argv[3]}")
                sys.exit(1)
            
            config = load_config()
            success = translate_single_chapter(novel_name, chapter_num, config)
            sys.exit(0 if success else 1)
            
        elif command == '--next':
            # Find next pending chapter
            status = get_chapter_status(novel_name)
            
            if 'error' in status:
                print(f"✗ {status['error']}")
                sys.exit(1)
            
            pending = [ch for ch in status['chapters'] if not ch['done']]
            
            if not pending:
                print("\n✓ All chapters are already translated!")
                sys.exit(0)
            
            next_ch = pending[0]
            print(f"\nAuto-selecting next chapter: Chapter {next_ch['number']}")
            
            config = load_config()
            success = translate_single_chapter(novel_name, next_ch['number'], config)
            sys.exit(0 if success else 1)
            
        else:
            print(f"✗ Unknown command: {command}")
            print("Use --status, --list, --chapter, or --next")
            sys.exit(1)
    else:
        # Default: show status
        status = get_chapter_status(novel_name)
        print_status(status)


if __name__ == "__main__":
    main()
