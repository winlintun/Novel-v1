#!/usr/bin/env python3
"""
Test script for Chinese → English → Myanmar novel chapter translation.
Uses the full pipeline with config/settings.pivot.yaml

Features:
1. Translates a novel chapter using CN→EN→MM pivot workflow
2. Shows log file location and displays log contents
3. Reads and validates the translated output file
4. Runs Gemini reviewer to check and fix issues

Usage:
    python src/test_translate/test_ch_en_mm_translation.py --chapter 001
    python src/test_translate/test_ch_en_mm_translation.py --chapter 001 --novel 古道仙鸿
"""

import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.file_handler import FileHandler
from src.utils.postprocessor import validate_output, detect_language_leakage


def run_translation(chapter_num: str, novel_name: str = "古道仙鸿") -> tuple[Optional[str], Optional[str], bool]:
    """
    Run the translation pipeline for a chapter.
    
    Args:
        chapter_num: Chapter number (e.g., "001")
        novel_name: Novel name (default: 古道仙鸿)
        
    Returns:
        Tuple of (log_file_path, output_file_path, success)
    """
    print(f"\n{'='*60}")
    print("STARTING TRANSLATION PIPELINE")
    print(f"{'='*60}")
    print(f"Novel: {novel_name}")
    print(f"Chapter: {chapter_num}")
    print(f"Config: config/settings.pivot.yaml")
    print(f"Models: qwen2.5:14b (CN→EN) → qwen:7b (EN→MM)")
    
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
    """
    Display the log file contents.
    
    Args:
        log_file: Path to log file
        tail_lines: Number of lines to show from end
    """
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
        # Use FileHandler for consistent encoding
        content = FileHandler.read_text(log_file)
        lines = content.splitlines()
        
        print(f"\nTotal lines: {len(lines)}")
        print(f"Showing last {tail_lines} lines:\n")
        print("-" * 60)
        
        # Show last N lines
        for line in lines[-tail_lines:]:
            print(line)
        
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ Error reading log: {e}")


def check_output_file(output_file: Optional[str]) -> dict[str, Any]:
    """
    Read and validate the translated output file.
    
    Args:
        output_file: Path to output file
        
    Returns:
        Dictionary with validation results
    """
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
        # Use FileHandler for consistent encoding
        content = FileHandler.read_text(output_file)
        
        # File stats
        file_size = output_path.stat().st_size
        char_count = len(content)
        line_count = len(content.splitlines())
        
        print(f"\nFile size: {file_size:,} bytes")
        print(f"Characters: {char_count:,}")
        print(f"Lines: {line_count}")
        
        # Validate Myanmar content
        validation = validate_output(content, chapter_num=0)
        leakage = detect_language_leakage(content)
        
        print(f"\nValidation Results:")
        print(f"  Status: {validation['status']}")
        print(f"  Myanmar ratio: {validation.get('myanmar_ratio', 0):.2%}")
        print(f"  Chinese chars: {leakage.get('chinese_chars', 0)}")
        print(f"  English words: {leakage.get('latin_words', 0)}")
        print(f"  Thai chars: {leakage.get('thai_chars', 0)}")
        
        # Show preview
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


def run_gemini_reviewer(output_file: str) -> str:
    """
    Run Gemini reviewer on the output file.
    
    Args:
        output_file: Path to translated output file
        
    Returns:
        Review result
    """
    print(f"\n{'='*60}")
    print("GEMINI REVIEWER")
    print(f"{'='*60}")
    print(f"Preparing review for: {output_file}")
    print("\n⚠️  According to .gemini/agents/gemini-reviewer.md:")
    print("   Run: gemini run 'Review the changes I just made'")
    
    return "READY_FOR_GEMINI_REVIEW"


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(
        description="Test CN→EN→MM translation for novel chapters"
    )
    parser.add_argument(
        "--chapter", "-c",
        default="001",
        help="Chapter number (default: 001)"
    )
    parser.add_argument(
        "--novel", "-n",
        default="古道仙鸿",
        help="Novel name (default: 古道仙鸿)"
    )
    parser.add_argument(
        "--skip-review",
        action="store_true",
        help="Skip Gemini review step"
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("NOVEL CHAPTER TRANSLATION TEST")
    print("Chinese → English → Myanmar")
    print("="*60)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Run translation
    log_file, output_file, success = run_translation(args.chapter, args.novel)
    
    if not success:
        if log_file:
            show_log_file(log_file)
        print("\n❌ TRANSLATION FAILED")
        return 1
    
    # Step 2: Show log file
    if log_file:
        show_log_file(log_file, tail_lines=100)
    
    # Step 3: Check output file
    validation = check_output_file(output_file)
    
    # Step 4: Run Gemini reviewer (if requested)
    if not args.skip_review and output_file:
        run_gemini_reviewer(output_file)
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Log file: {log_file}")
    print(f"Output file: {output_file}")
    print(f"Validation: {validation.get('status', 'UNKNOWN')}")
    print(f"Myanmar ratio: {validation.get('myanmar_ratio', 0):.2%}")
    
    if validation.get('valid'):
        print("\n✅ TEST PASSED - Translation looks good!")
        return 0
    else:
        print("\n⚠️  TEST COMPLETED with warnings")
        print("   Check log file and output for details")
        return 0


if __name__ == "__main__":
    sys.exit(main())
