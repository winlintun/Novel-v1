#!/usr/bin/env python3
"""
Master script for two-phase chapter-based translation

Phase 1: Extract chapters from input novels and save as Chinese .md files
Phase 2: Translate each chapter .md file to Burmese one by one

Usage:
    python translate_novel.py <novel_name>
    python translate_novel.py simple_data
    
Or process all novels:
    python translate_novel.py --all
"""

import os
import sys
import subprocess
from pathlib import Path


def run_phase_1_extract(novel_name=None):
    """Run Phase 1: Extract chapters."""
    print("=" * 60)
    print("PHASE 1: Extracting chapters from input novel")
    print("=" * 60)
    
    if novel_name:
        cmd = [sys.executable, "scripts/extract_chapters.py", novel_name]
    else:
        cmd = [sys.executable, "scripts/extract_chapters.py"]
    
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode == 0


def run_phase_2_translate(novel_name):
    """Run Phase 2: Translate chapters."""
    print("\n" + "=" * 60)
    print(f"PHASE 2: Translating chapters for {novel_name}")
    print("=" * 60)
    
    cmd = [sys.executable, "scripts/translate_chapters.py", novel_name]
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    return result.returncode == 0


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python translate_novel.py <novel_name>")
        print("       python translate_novel.py --all")
        print("")
        print("Examples:")
        print("  python translate_novel.py simple_data")
        print("  python translate_novel.py 古道仙鸿")
        sys.exit(1)
    
    if sys.argv[1] == '--all':
        # Process all novels in input_novels/
        input_dir = Path("input_novels")
        if not input_dir.exists():
            print("✗ input_novels/ directory not found")
            sys.exit(1)
        
        txt_files = list(input_dir.glob("*.txt"))
        
        if not txt_files:
            print("✗ No .txt files found in input_novels/")
            sys.exit(1)
        
        print(f"Found {len(txt_files)} novel(s) to process\n")
        
        # Phase 1: Extract all
        print("=" * 60)
        print("PHASE 1: Extracting chapters from all novels")
        print("=" * 60)
        
        for txt_file in txt_files:
            novel_name = txt_file.stem
            print(f"\n>>> Extracting: {novel_name}")
            cmd = [sys.executable, "scripts/extract_chapters.py", novel_name]
            result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
            
            if result.returncode != 0:
                print(f"✗ Extraction failed for {novel_name}")
                continue
        
        # Phase 2: Translate all
        print("\n" + "=" * 60)
        print("PHASE 2: Translating all novels")
        print("=" * 60)
        
        for txt_file in txt_files:
            novel_name = txt_file.stem
            print(f"\n>>> Translating: {novel_name}")
            cmd = [sys.executable, "scripts/translate_chapters.py", novel_name]
            result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
            
            if result.returncode != 0:
                print(f"✗ Translation failed for {novel_name}")
                continue
        
        print("\n" + "=" * 60)
        print("✓ All novels processed")
        print("=" * 60)
        
    else:
        # Process specific novel
        novel_name = sys.argv[1]
        input_file = Path("input_novels") / f"{novel_name}.txt"
        
        if not input_file.exists():
            print(f"✗ Novel not found: {input_file}")
            sys.exit(1)
        
        print(f"Processing novel: {novel_name}\n")
        
        # Phase 1: Extract chapters
        if not run_phase_1_extract(novel_name):
            print(f"✗ Phase 1 failed for {novel_name}")
            sys.exit(1)
        
        # Phase 2: Translate chapters
        if not run_phase_2_translate(novel_name):
            print(f"✗ Phase 2 failed for {novel_name}")
            sys.exit(1)
        
        print("\n" + "=" * 60)
        print(f"✓ Novel complete: {novel_name}")
        print("=" * 60)


if __name__ == "__main__":
    main()
