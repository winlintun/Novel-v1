#!/usr/bin/env python3
"""
Test script for Chinese → English → Myanmar translation.

Two modes:
1. Sentence mode: Translate a single Chinese sentence
   Usage: python src/test_translate/test_ch_en_mm_translation.py --sentence "你的中文句子"

2. Chapter mode: Translate a full novel chapter (requires existing chapter file)
   Usage: python src/test_translate/test_ch_en_mm_translation.py --chapter 001

Features:
- Shows log file and displays log contents
- Reads and validates the translated output
- Integrates with Gemini reviewer workflow
"""

import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.file_handler import FileHandler
from src.utils.postprocessor import validate_output, detect_language_leakage
from src.utils.ollama_client import OllamaClient


def translate_sentence_cn_en_mm(chinese_text: str) -> dict[str, Any]:
    """
    Translate a single Chinese sentence using CN→EN→MM pipeline.
    
    Args:
        chinese_text: Chinese text to translate
        
    Returns:
        Dictionary with stage1 (EN), stage2 (MM), and validation results
    """
    print(f"\n{'='*60}")
    print("SENTENCE TRANSLATION MODE")
    print(f"{'='*60}")
    print(f"\n🇨🇳 Chinese Input:\n{chinese_text}")
    
    # Stage 1: Chinese → English
    print(f"\n{'='*60}")
    print("STAGE 1: Chinese → English")
    print(f"{'='*60}")
    print("Model: qwen2.5:14b (CN->EN)")
    
    client1 = OllamaClient(
        model="qwen2.5:14b",
        temperature=0.3,
        repeat_penalty=1.15,
        unload_on_cleanup=True
    )
    
    system_prompt_1 = """You are an expert Chinese-to-English literary translator.
Translate accurately while preserving names in pinyin (e.g., 罗青 → Luo Qing).
Output ONLY English translation."""
    
    prompt_1 = f"""Translate the following Chinese text to English:

CHINESE TEXT:
{chinese_text}

ENGLISH TRANSLATION:"""
    
    try:
        english_result = client1.chat(prompt=prompt_1, system_prompt=system_prompt_1)
        print(f"\n🇬🇧 English Output:\n{english_result.strip()}")
    except Exception as e:
        print(f"\n❌ Stage 1 FAILED: {e}")
        return {"success": False, "error": f"Stage 1: {e}"}
    finally:
        client1.cleanup()
    
    # Stage 2: English → Myanmar
    print(f"\n{'='*60}")
    print("STAGE 2: English → Myanmar")
    print(f"{'='*60}")
    print("Model: qwen:7b (EN->MM)")
    
    client2 = OllamaClient(
        model="qwen:7b",
        temperature=0.2,
        repeat_penalty=1.15,
        unload_on_cleanup=True
    )
    
    system_prompt_2 = """CRITICAL: Output ONLY Myanmar (Burmese) language using Myanmar Unicode script.

FORBIDDEN: English words, Chinese characters, Thai script, Latin alphabet.

You are an expert English-to-Myanmar literary translator specializing in Wuxia/Xianxia novels.

RULES:
1. Convert English SVO to Myanmar SOV sentence structure
2. Use natural Myanmar prose - literary for narrative, spoken for dialogue
3. For names in pinyin (Luo Qing, Xiao Rong), use the glossary below
4. Use 【?term?】 placeholder for unknown words
5. NO English words. NO Chinese characters.
6. Use formal tone: သည် for "is/am/are", ကို for object marker"""
    
    prompt_2 = f"""Translate the following English text to Myanmar using the glossary.

GLOSSARY (USE THESE EXACT TERMS):
CHARACTERS:
- Luo Qing → လော်ချင်း
- Xiao Rong Town → ရှောင်ရုံးမြို့
- Luo Village → လော်ကျေးရွာ

LOCATIONS:
- town → မြို့
- village → ရွာ/ကျေးရွာ
- mountain → တောင်

DESCRIPTIONS:
- twelve years old → အသက်ဆယ့်နှစ်နှစ်
- ordinary appearance → ပုံသဏ္ဍာန်အရိုးအစင်း
- poor household → ဆင်းရဲသော မိသားစု
- villager → ရွာသား

ENGLISH TEXT:
{english_result}

MYANMAR TRANSLATION (SOV structure, natural Myanmar):"""
    
    try:
        myanmar_result = client2.chat(prompt=prompt_2, system_prompt=system_prompt_2)
        print(f"\n🇲🇲 Myanmar Output:\n{myanmar_result.strip()}")
    except Exception as e:
        print(f"\n❌ Stage 2 FAILED: {e}")
        return {"success": False, "error": f"Stage 2: {e}"}
    finally:
        client2.cleanup()
    
    # Validate output
    validation = validate_output(myanmar_result, chapter=0)
    leakage = detect_language_leakage(myanmar_result)
    
    print(f"\n{'='*60}")
    print("VALIDATION RESULTS")
    print(f"{'='*60}")
    print(f"Status: {validation['status']}")
    print(f"Myanmar ratio: {validation.get('myanmar_ratio', 0):.2%}")
    print(f"Chinese chars: {leakage.get('chinese_chars', 0)}")
    print(f"English words: {leakage.get('latin_words', 0)}")
    
    return {
        "success": True,
        "chinese": chinese_text,
        "english": english_result.strip(),
        "myanmar": myanmar_result.strip(),
        "validation": validation,
        "leakage": leakage
    }


def run_chapter_translation(chapter_num: str, novel_name: str = "古道仙鸿") -> tuple[Optional[str], Optional[str], bool]:
    """
    Run the translation pipeline for a chapter.
    
    Args:
        chapter_num: Chapter number (e.g., "001")
        novel_name: Novel name (default: 古道仙鸿)
        
    Returns:
        Tuple of (log_file_path, output_file_path, success)
    """
    print(f"\n{'='*60}")
    print("CHAPTER TRANSLATION MODE")
    print(f"{'='*60}")
    print(f"Novel: {novel_name}")
    print(f"Chapter: {chapter_num}")
    print(f"Config: config/settings.pivot.yaml")
    print(f"Models: qwen2.5:14b (CN->EN) -> qwen:7b (EN->MM)")
    
    # Validate config exists
    config_path = Path("config/settings.pivot.yaml")
    if not config_path.exists():
        print(f"❌ Config not found: {config_path}")
        return None, None, False
    
    # Build command
    cmd = [
        "python", "-m", "src.main",
        "--config", str(config_path),
        "--novel", novel_name,
        "--chapter", chapter_num,
        "--unload-after-chapter"
    ]
    
    print(f"\nCommand: {' '.join(cmd)}")
    print("\n⏳ Running translation (this may take 10-30 minutes)...")
    
    try:
        # Run translation
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        # Log stderr if there are errors
        if result.returncode != 0 and result.stderr:
            print(f"\n⚠️  Translation stderr:\n{result.stderr[:500]}")
        
        # Find the log file
        log_dir = Path("logs")
        log_file = None
        if log_dir.exists():
            log_files = sorted(
                log_dir.glob("translation_*.log"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            if log_files:
                log_file = str(log_files[0])
        
        # Find output file
        output_dir = Path("data/output")
        output_file = None
        if output_dir.exists():
            output_files = list(output_dir.rglob(f"*chapter_{chapter_num}_mm.md"))
            if output_files:
                # Get the most recently modified
                output_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                output_file = str(output_files[0])
        
        success = result.returncode == 0 and output_file is not None
        
        if not success:
            print(f"\n❌ Translation failed!")
            print(f"Return code: {result.returncode}")
        
        return log_file, output_file, success
        
    except subprocess.TimeoutExpired:
        print("\n❌ Translation timed out after 1 hour")
        return None, None, False
    except Exception as e:
        print(f"\n❌ Translation failed: {e}")
        return None, None, False


def show_log_file(log_file: Optional[str], tail_lines: int = 50) -> None:
    """Display the log file contents."""
    print(f"\n{'='*60}")
    print("TRANSLATION LOG")
    print(f"{'='*60}")
    print(f"Log file: {log_file}")
    
    if not log_file:
        print("❌ No log file specified")
        return
    
    log_path = Path(log_file)
    if not log_path.exists():
        print("❌ Log file not found")
        return
    
    try:
        content = FileHandler.read_text(log_file)
        lines = content.splitlines()
        
        print(f"\nTotal lines: {len(lines)}")
        print(f"Showing last {tail_lines} lines:\n")
        print("-" * 60)
        
        for line in lines[-tail_lines:]:
            print(line)
        
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ Error reading log: {e}")


def check_output_file(output_file: Optional[str]) -> dict[str, Any]:
    """Read and validate the translated output file."""
    print(f"\n{'='*60}")
    print("OUTPUT FILE VALIDATION")
    print(f"{'='*60}")
    print(f"Output file: {output_file}")
    
    if not output_file:
        return {"valid": False, "error": "No output file specified"}
    
    output_path = Path(output_file)
    if not output_path.exists():
        return {"valid": False, "error": "File not found"}
    
    try:
        content = FileHandler.read_text(output_file)
        
        file_size = output_path.stat().st_size
        char_count = len(content)
        line_count = len(content.splitlines())
        
        print(f"\nFile size: {file_size:,} bytes")
        print(f"Characters: {char_count:,}")
        print(f"Lines: {line_count}")
        
        validation = validate_output(content, chapter=0)
        leakage = detect_language_leakage(content)
        
        print(f"\nValidation Results:")
        print(f"  Status: {validation['status']}")
        print(f"  Myanmar ratio: {validation.get('myanmar_ratio', 0):.2%}")
        print(f"  Chinese chars: {leakage.get('chinese_chars', 0)}")
        print(f"  English words: {leakage.get('latin_words', 0)}")
        
        print(f"\n{'='*60}")
        print("OUTPUT PREVIEW (first 1000 chars)")
        print(f"{'='*60}")
        print(content[:1000])
        print("\n... [truncated] ...")
        
        return {
            "valid": validation['status'] == "APPROVED",
            "status": validation['status'],
            "myanmar_ratio": validation.get('myanmar_ratio', 0),
            "content": content,
            "output_file": output_file,
            "leakage": leakage
        }
        
    except Exception as e:
        print(f"❌ Error reading output: {e}")
        return {"valid": False, "error": str(e)}


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(
        description="Test CN→EN→MM translation - sentence or chapter mode"
    )
    parser.add_argument(
        "--sentence", "-s",
        help="Translate a single Chinese sentence"
    )
    parser.add_argument(
        "--chapter", "-c",
        help="Chapter number to translate (e.g., 001)"
    )
    parser.add_argument(
        "--novel", "-n",
        default="古道仙鸿",
        help="Novel name for chapter mode (default: 古道仙鸿)"
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("CHINESE → ENGLISH → MYANMAR TRANSLATION TEST")
    print("="*60)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Sentence mode
    if args.sentence:
        result = translate_sentence_cn_en_mm(args.sentence)
        
        print(f"\n{'='*60}")
        print("FINAL RESULTS")
        print(f"{'='*60}")
        if result["success"]:
            print(f"\n🇨🇳 Chinese:\n{result['chinese']}")
            print(f"\n🇬🇧 English:\n{result['english']}")
            print(f"\n🇲🇲 Myanmar:\n{result['myanmar']}")
            print(f"\n✅ Translation complete!")
            return 0
        else:
            print(f"\n❌ Translation failed: {result.get('error', 'Unknown error')}")
            return 1
    
    # Chapter mode
    elif args.chapter:
        log_file, output_file, success = run_chapter_translation(args.chapter, args.novel)
        
        if not success:
            if log_file:
                show_log_file(log_file)
            print("\n❌ CHAPTER TRANSLATION FAILED")
            return 1
        
        if log_file:
            show_log_file(log_file, tail_lines=100)
        
        validation = check_output_file(output_file)
        
        print(f"\n{'='*60}")
        print("CHAPTER TRANSLATION SUMMARY")
        print(f"{'='*60}")
        print(f"Log file: {log_file}")
        print(f"Output file: {output_file}")
        print(f"Validation: {validation.get('status', 'UNKNOWN')}")
        print(f"Myanmar ratio: {validation.get('myanmar_ratio', 0):.2%}")
        
        if validation.get('valid'):
            print("\n✅ CHAPTER TRANSLATION PASSED!")
            return 0
        else:
            print("\n⚠️  CHAPTER TRANSLATION COMPLETED with warnings")
            return 0
    
    # No arguments - show help
    else:
        parser.print_help()
        print("\n\nExamples:")
        print("  # Translate a sentence:")
        print('  python src/test_translate/test_ch_en_mm_translation.py -s "罗青，十二岁，小戎镇罗家村村民。"')
        print("\n  # Translate a chapter:")
        print("  python src/test_translate/test_ch_en_mm_translation.py -c 001")
        return 0


if __name__ == "__main__":
    sys.exit(main())
